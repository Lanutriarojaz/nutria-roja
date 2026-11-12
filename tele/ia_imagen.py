"""Decorados y personajes pintados por IA (FLUX en Cloudflare Workers AI, plan gratis) y recortados con rembg.
Cada episodio tiene los suyos: un decorado por escena y un personaje por cada papel. Si algo falla, el motor vuelve
a los dibujos por código (no se queda sin vídeo)."""
import base64
import hashlib
import io
import os
import time

import requests
from PIL import Image, ImageFilter

MODELO = '@cf/black-forest-labs/flux-1-schnell'
ESTILO = ('2D adult animated sitcom cartoon style, thick black outlines, flat bold saturated colors, cel shading, '
          'expressive slightly grotesque but likable designs, absurd sci-fi television look, '
          'no text, no letters, no words, no logos, no watermark, no captions')
ESTILO_DECORADO = (' Wide shot of the empty set, no people, no characters, centered composition with the important elements in the '
                   'middle third, room in the lower half for characters to stand, cinematic lighting. ')
ESTILO_PERSONAJE = (' Full body character, standing, facing the camera, the whole body visible from head to feet with margin, '
                    'centered, isolated on a plain flat light grey background, no other objects. ')

_SESION = None


class SinImagenes(RuntimeError):
    pass


def _cf():
    cta, tok = os.environ.get('CLOUDFLARE_ACCOUNT_ID'), os.environ.get('CLOUDFLARE_API_TOKEN')
    if not cta or not tok:
        raise SinImagenes('Faltan las claves de Cloudflare')
    return f'https://api.cloudflare.com/client/v4/accounts/{cta}/ai/run/{MODELO}', {'Authorization': f'Bearer {tok}'}


def generar(prompt, ruta, semilla=0):
    """Pide una imagen a FLUX (1024x1024) y la guarda. Reutiliza la que ya exista (caché por contenido)."""
    if os.path.exists(ruta):
        return ruta
    url, cab = _cf()
    ultimo = ''
    for intento in range(4):
        try:
            r = requests.post(url, headers=cab, json={'prompt': prompt[:2000], 'steps': 8}, timeout=120)
            if r.status_code == 200:
                if r.headers.get('content-type', '').startswith('image'):
                    datos = r.content
                else:
                    datos = base64.b64decode((r.json().get('result') or {}).get('image') or '')
                if len(datos) > 5000:
                    Image.open(io.BytesIO(datos)).convert('RGB').save(ruta)
                    return ruta
                ultimo = 'imagen vacía'
            else:
                ultimo = f'{r.status_code} {r.text[:150]}'
                if r.status_code in (401, 403):
                    break
        except requests.RequestException as e:
            ultimo = repr(e)[:150]
        time.sleep(4 * (intento + 1))
    raise SinImagenes(f'FLUX no ha generado la imagen: {ultimo}')


def recortar(ruta, salida):
    """Quita el fondo del personaje y lo recorta a su silueta. Comprueba que el recorte tenga sentido."""
    global _SESION
    if os.path.exists(salida):
        return Image.open(salida)
    from rembg import new_session, remove
    if _SESION is None:
        _SESION = new_session('isnet-anime')
    im = remove(Image.open(ruta).convert('RGB'), session=_SESION).convert('RGBA')
    a = im.getchannel('A').point(lambda v: 0 if v < 40 else v)
    im.putalpha(a.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8)))
    caja = im.getchannel('A').point(lambda v: 255 if v > 100 else 0).getbbox()
    if not caja:
        raise SinImagenes('El recorte ha salido vacío')
    im = im.crop(caja)
    lleno = sum(1 for v in im.getchannel('A').resize((64, 64)).tobytes() if v > 128) / 4096
    alto_rel = (caja[3] - caja[1]) / 1024
    if lleno < 0.12 or alto_rel < 0.35:
        raise SinImagenes(f'Recorte raro (relleno {lleno:.2f}, alto {alto_rel:.2f})')
    im.save(salida)
    return im


GESTO_MODELO = '@cf/black-forest-labs/flux-2-klein-4b'    # ~110 neuronas por edición (los otros FLUX.2 cuestan 15-20 veces más)
GESTOS = {
    'boca': 'with the mouth wide open as if talking, same expression otherwise',
    'enfado': 'furious: angry eyebrows, shouting with the mouth wide open, clenched fists',
    'miedo': 'terrified: huge eyes, trembling, hands near the face, mouth open in fear',
    'risa': 'laughing hysterically with the eyes closed and the mouth wide open',
}


def gesto(base, ruta, cambio):
    """Edita el personaje con FLUX.2 klein: el mismo personaje (diseño, colores, ropa), con otro gesto."""
    if os.path.exists(ruta):
        return ruta
    cta, tok = os.environ.get('CLOUDFLARE_ACCOUNT_ID'), os.environ.get('CLOUDFLARE_API_TOKEN')
    if not cta or not tok:
        raise SinImagenes('Faltan las claves de Cloudflare')
    buf = io.BytesIO(); Image.open(base).convert('RGB').resize((512, 512)).save(buf, 'PNG')
    texto = (f'The exact same character, same design, same colors, same clothes, same proportions, same full body framing, but {cambio}. '
             'Plain flat light grey background, 2D cartoon, thick black outlines, no text.')
    ultimo = ''
    for intento in range(3):
        try:
            r = requests.post(f'https://api.cloudflare.com/client/v4/accounts/{cta}/ai/run/{GESTO_MODELO}',
                              headers={'Authorization': f'Bearer {tok}'}, timeout=120,
                              files={'input_image_0': ('base.png', buf.getvalue(), 'image/png')},
                              data={'prompt': texto, 'width': '768', 'height': '768', 'steps': '4'})
            if r.status_code == 200:
                datos = r.content if r.headers.get('content-type', '').startswith('image') else \
                    base64.b64decode((r.json().get('result') or {}).get('image') or '')
                if len(datos) > 5000:
                    Image.open(io.BytesIO(datos)).convert('RGB').save(ruta)
                    return ruta
            ultimo = f'{r.status_code} {r.text[:120]}'
            if r.status_code in (401, 403, 429):
                break
        except requests.RequestException as e:
            ultimo = repr(e)[:120]
        time.sleep(3 * (intento + 1))
    raise SinImagenes(f'Gesto no generado: {ultimo}')


def tiene_texto(ruta):
    """Gemini mira la imagen: ¿hay letras, números o carteles legibles? (si no se puede preguntar, se da por buena)."""
    claves = [os.environ.get(k) for k in ('GEMINI_API_KEY_3', 'GEMINI_API_KEY_2', 'GEMINI_API_KEY') if os.environ.get(k)]
    if not claves:
        return False
    buf = io.BytesIO(); Image.open(ruta).convert('RGB').resize((512, 512)).save(buf, 'JPEG', quality=85)
    cuerpo = {'contents': [{'parts': [
        {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
        {'text': 'Does this image contain any readable text, letters, words or numbers (signs, labels, clocks with digits, captions)? '
                 'Answer only YES or NO.'}]}]}
    for k in claves:
        for modelo in ('gemini-flash-lite-latest', 'gemini-flash-latest'):
            try:
                r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent',
                                  params={'key': k}, json=cuerpo, timeout=60)
                if r.status_code == 200:
                    txt = r.json()['candidates'][0]['content']['parts'][0].get('text', '')
                    return txt.strip().upper().startswith('Y')
            except Exception:
                pass
    return False


def _semilla(texto):
    return int(hashlib.sha1(texto.encode()).hexdigest()[:8], 16)


def preparar(g, s, carpeta):
    """Genera y recorta todo lo del episodio. Devuelve {'decorados': [ruta por escena], 'personajes': {id: RGBA}}."""
    d = os.environ.get('TELE_IA_CACHE') or os.path.join(carpeta, 'ia'); os.makedirs(d, exist_ok=True)
    genero = s.get('formato', '')
    decorados, hechos = [], {}
    for i, e in enumerate(g['escenas']):
        desc = (e.get('decorado') or '').strip() or e.get('plano', '')
        clave = desc.lower()[:200]
        if clave in hechos:                                   # misma descripción → mismo decorado (raccord)
            decorados.append(hechos[clave]); continue
        ruta = os.path.join(d, f'decorado{i}.png')
        generar(f'{desc}.{ESTILO_DECORADO}{ESTILO}', ruta, _semilla(desc + genero))
        if tiene_texto(ruta):                                 # control de calidad: nada de letras raras
            print(f'  decorado {i}: tiene texto, lo repinto', flush=True)
            os.remove(ruta)
            generar(f'{desc}. Absolutely no text, no numbers, no signs, no digits.{ESTILO_DECORADO}{ESTILO}', ruta, 1)
        hechos[clave] = ruta
        decorados.append(ruta)
    personajes = {}
    for p in g['personajes']:
        desc = (p.get('aspecto') or '').strip() or f"a {p.get('cuerpo', 'creature')} character called {p['nombre']}"
        bruto = os.path.join(d, f"pj_{p['id']}.png")
        error = None
        for intento in range(3):                              # si el recorte sale mal, se repinta con otra semilla
            try:
                generar(f'{desc}.{ESTILO_PERSONAJE}{ESTILO}', bruto, _semilla(desc) + intento * 104729)
                personajes[p['id']] = recortar(bruto, os.path.join(d, f"pj_{p['id']}_recorte.png"))
                break
            except SinImagenes as ex:
                error = ex
                for f in (bruto, os.path.join(d, f"pj_{p['id']}_recorte.png")):
                    if os.path.exists(f):
                        os.remove(f)
        else:
            raise SinImagenes(f"Personaje {p['nombre']}: {error}")
    # gestos del mismo personaje (si alguno falla, se usa la imagen normal)
    gestos = {}
    for p in g['personajes']:
        gestos[p['id']] = {}
        for nombre, cambio in GESTOS.items():
            bruto = os.path.join(d, f"pj_{p['id']}_{nombre}.png")
            try:
                gesto(os.path.join(d, f"pj_{p['id']}.png"), bruto, cambio)
                gestos[p['id']][nombre] = recortar(bruto, os.path.join(d, f"pj_{p['id']}_{nombre}_recorte.png"))
            except SinImagenes as ex:
                print(f"  gesto {nombre} de {p['nombre']}: {ex}", flush=True)
                if '429' in str(ex):
                    break
    return {'decorados': decorados, 'personajes': personajes, 'gestos': gestos}

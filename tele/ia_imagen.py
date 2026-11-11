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
            r = requests.post(url, headers=cab, json={'prompt': prompt[:2000], 'steps': 8, 'seed': (semilla + intento * 7919) % 2**31},
                              timeout=120)
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


def _semilla(texto):
    return int(hashlib.sha1(texto.encode()).hexdigest()[:8], 16)


def preparar(g, s, carpeta):
    """Genera y recorta todo lo del episodio. Devuelve {'decorados': [ruta por escena], 'personajes': {id: RGBA}}."""
    d = os.path.join(carpeta, 'ia'); os.makedirs(d, exist_ok=True)
    genero = s.get('formato', '')
    decorados, hechos = [], {}
    for i, e in enumerate(g['escenas']):
        desc = (e.get('decorado') or '').strip() or e.get('plano', '')
        clave = desc.lower()[:200]
        if clave in hechos:                                   # misma descripción → mismo decorado (raccord)
            decorados.append(hechos[clave]); continue
        ruta = os.path.join(d, f'decorado{i}.png')
        generar(f'{desc}.{ESTILO_DECORADO}{ESTILO}', ruta, _semilla(desc + genero))
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
    return {'decorados': decorados, 'personajes': personajes}

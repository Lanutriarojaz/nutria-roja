"""Piloto de microdocumentales de La Nutria Roja: guion (JSON de ChatGPT) → versión EN (Gemini) →
voces de mujer (edge-tts y Kokoro) → metraje real de Pixabay → montaje 9:16 con rótulos, subtítulos y música CC-BY.

Uso: python -m docu.piloto docu/pilotos/<tema>.json
No publica nada: deja los MP4 y un informe en salida-docu/.
"""
import asyncio
import json
import os
import re
import sys
import wave

import requests
from PIL import Image, ImageDraw, ImageFont

from nutria.calidad import revisar
from nutria.guion import llm
from nutria.video import sh

W, H, FPS, X = 1080, 1920, 30, 0.35          # X = solape del fundido entre escenas
AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = os.path.join(AQUI, '..', 'assets', 'Anton-Regular.ttf')
SALIDA = os.path.join(AQUI, '..', 'salida-docu')
CACHE = os.path.join(SALIDA, 'metraje')
ROJO, BLANCO = (255, 72, 60, 255), (255, 255, 255, 255)
ESLOGAN = {'es': 'Lo extraordinario está más cerca de lo que crees',
           'en': 'The extraordinary is closer than you think'}
MUSICA = ('Floating Cities', 'https://incompetech.com/music/royalty-free/mp3-royaltyfree/Floating%20Cities.mp3')
CREDITO = 'Music: "Floating Cities" by Kevin MacLeod (incompetech.com), licensed under CC BY 4.0'

# Voces de mujer a comparar: (motor, id, etiqueta)
VOCES = {
    'es': [('edge', 'es-ES-ElviraNeural', 'elvira'), ('edge', 'es-ES-XimenaNeural', 'ximena'),
           ('kokoro', 'ef_dora', 'dora-kokoro')],
    'en': [('edge', 'en-US-AvaNeural', 'ava'), ('edge', 'en-GB-SoniaNeural', 'sonia'),
           ('kokoro', 'af_heart', 'heart-kokoro')],
}


def _dur(ruta):
    return float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ruta]))


# ---------------- versión inglesa ----------------
def adaptar_en(g):
    pedido = {
        'escenas': [{'n': e['n'], 'locucion': e['locucion'], 'texto_pantalla': e.get('texto_pantalla', '')}
                    for e in g['escenas']],
        'titulo': g['titulo'], 'metadatos': g['metadatos'],
    }
    res = llm([
        {'role': 'system', 'content':
         'You localise Spanish science short-video scripts into natural, punchy American English for a narrator. '
         'Adapt, do not translate word by word: idioms and rhythm must sound native. Keep every fact exactly; '
         'add nothing. Keep the same scenes (same "n"), each "locucion" of similar length so timing matches. '
         'on-screen texts max 5 words. Hashtags in English. Answer ONLY with JSON.'},
        {'role': 'user', 'content':
         'Return {"titulo": "...", "escenas": [{"n": 1, "locucion": "...", "texto_pantalla": "..."}], '
         '"metadatos": {"titulo": "...", "descripcion": "...", "hashtags": ["#..."]}} for:\n'
         + json.dumps(pedido, ensure_ascii=False)},
    ], temperatura=0.4)
    por_n = {e['n']: e for e in res['escenas']}
    if set(por_n) != {e['n'] for e in g['escenas']}:
        raise RuntimeError('La versión inglesa no trae las mismas escenas')
    en = json.loads(json.dumps(g))
    for e in en['escenas']:
        e['locucion'] = por_n[e['n']]['locucion']
        e['texto_pantalla'] = por_n[e['n']].get('texto_pantalla', '')
    en['titulo'], en['metadatos'] = res['titulo'], res['metadatos']
    return en


# ---------------- voz ----------------
def _pronunciar(texto, g, idioma):
    if idioma != 'es':
        return texto
    for p in g.get('pronunciacion') or []:
        if p.get('termino') and p.get('como'):
            texto = re.sub(rf'\b{re.escape(p["termino"])}\b', p['como'], texto)
    return texto


async def _edge(texto, voz, mp3):
    import edge_tts
    c = edge_tts.Communicate(texto, voz, rate='+6%', boundary='WordBoundary')
    marcas = []
    with open(mp3, 'wb') as f:
        async for ch in c.stream():
            if ch['type'] == 'audio':
                f.write(ch['data'])
            elif ch['type'] == 'WordBoundary':
                marcas.append((ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7))
    return marcas


_KOKORO = {}


def _kokoro(texto, voz, wav):
    import numpy as np
    from kokoro import KPipeline
    lang = voz[0]
    if lang not in _KOKORO:
        _KOKORO[lang] = KPipeline(lang_code=lang)
    trozos = [r.audio.numpy() if hasattr(r.audio, 'numpy') else r.audio
              for r in _KOKORO[lang](texto, voice=voz, speed=1.05)]
    a = np.concatenate(trozos)
    pcm = (np.clip(a, -1, 1) * 32767).astype('<i2').tobytes()
    with wave.open(wav, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000); f.writeframes(pcm)


def locutar(texto, motor, voz, base):
    """Devuelve (wav 44,1 kHz estéreo, duración, tiempos de cada palabra relativos al tramo)."""
    wav = base + '.wav'
    palabras = texto.split()
    marcas = []
    if motor == 'edge':
        mp3 = base + '.mp3'
        for i in range(4):
            try:
                marcas = asyncio.run(_edge(texto, voz, mp3)); break
            except Exception:
                if i == 3: raise
        sh(f'ffmpeg -v error -i "{mp3}" -f s16le -ac 1 -ar 24000 - | '
           f'ffmpeg -v error -y -f s16le -ar 24000 -ac 1 -i - -ar 44100 -ac 2 "{wav}"')
    else:
        crudo = base + '_k.wav'
        _kokoro(texto, voz, crudo)
        sh(['ffmpeg', '-v', 'error', '-y', '-i', crudo, '-af', 'silenceremove=start_periods=1:start_threshold=-50dB',
            '-ar', '44100', '-ac', '2', wav])
    dur = _dur(wav)
    if len(marcas) != len(palabras):        # reparto proporcional a la longitud de cada palabra
        total = sum(len(p) + 2 for p in palabras)
        t, marcas = 0.05, []
        for p in palabras:
            d = (dur - 0.15) * (len(p) + 2) / total
            marcas.append((t, t + d)); t += d
    return wav, dur, [(a, b, p) for (a, b), p in zip(marcas, palabras)]


# ---------------- metraje (Pixabay) ----------------
def _buscar(q, usados):
    r = requests.get('https://pixabay.com/api/videos/', timeout=30, params={
        'key': os.environ['PIXABAY_API_KEY'], 'q': q[:100], 'per_page': 20, 'safesearch': 'true'})
    r.raise_for_status()
    for h in r.json().get('hits', []):
        if h['id'] in usados:
            continue
        v = h['videos']
        for tam in ('large', 'medium'):
            if v.get(tam, {}).get('url') and v[tam].get('height', 0) >= 1080:
                return h, v[tam]
    return None, None


def metraje(escenas):
    os.makedirs(CACHE, exist_ok=True)
    usados, manifiesto, rutas = set(), [], []
    for e in escenas:
        consultas = [e.get('busqueda_en'), e.get('alternativa_en'),
                     ' '.join((e.get('busqueda_en') or '').split()[:2])]
        h = v = None
        for q in filter(None, consultas):
            h, v = _buscar(q, usados)
            if h:
                break
        if not h:
            raise RuntimeError(f'Sin metraje para la escena {e["n"]}: {consultas}')
        usados.add(h['id'])
        ruta = os.path.join(CACHE, f'{h["id"]}.mp4')
        if not os.path.exists(ruta):
            with requests.get(v['url'], stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(ruta, 'wb') as f:
                    for b in r.iter_content(1 << 20):
                        f.write(b)
        rutas.append(ruta)
        manifiesto.append({'escena': e['n'], 'busqueda': q, 'pixabay_id': h['id'], 'pagina': h['pageURL'],
                           'autor': h.get('user'), 'resolucion': f'{v["width"]}x{v["height"]}',
                           'licencia': 'Pixabay Content License (uso comercial sin atribución)'})
        print(f'  metraje escena {e["n"]}: {q!r} → {h["pageURL"]}', flush=True)
    return rutas, manifiesto


# ---------------- grafismo ----------------
def _f(s):
    return ImageFont.truetype(FUENTE, s)


def _marca(d):
    d.rounded_rectangle([60, 110, 400, 178], radius=14, fill=ROJO)
    d.text((230, 144), 'LA NUTRIA ROJA', font=_f(40), fill=BLANCO, anchor='mm')


def _rotulo_escena(d, texto):
    if not texto:
        return
    texto = texto.upper()
    tam = 92
    while d.textlength(texto, font=_f(tam)) > W - 140 and tam > 50:
        tam -= 4
    f = _f(tam)
    ancho = d.textlength(texto, font=f)
    y = 330
    d.rectangle([(W - ancho) / 2 - 30, y - 18, (W + ancho) / 2 + 30, y + tam + 14], fill=(0, 0, 0, 150))
    d.rectangle([(W - ancho) / 2 - 30, y + tam + 14, (W + ancho) / 2 + 30, y + tam + 22], fill=ROJO)
    d.text((W / 2, y), texto, font=f, fill=BLANCO, anchor='ma')


def _subtitulo(d, grupo, activa):
    tam = 84
    while True:
        f = _f(tam)
        anchos = [d.textlength(w.upper(), font=f) for w in grupo]
        esp = d.textlength(' ', font=f)
        total = sum(anchos) + esp * (len(grupo) - 1)
        if total <= W - 120 or tam <= 48:
            break
        tam -= 4
    x, y = (W - total) / 2, 1500
    for i, w in enumerate(grupo):
        d.text((x, y), w.upper(), font=f, fill=ROJO if i == activa else BLANCO, anchor='ls',
               stroke_width=8, stroke_fill=(0, 0, 0, 255))
        x += anchos[i] + esp


def _cierre(idioma):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 170)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([W / 2 - 300, 700, W / 2 + 300, 800], radius=18, fill=ROJO)
    d.text((W / 2, 750), 'LA NUTRIA ROJA', font=_f(64), fill=BLANCO, anchor='mm')
    lineas, actual = [], ''
    for w in ESLOGAN[idioma].split():
        if len(actual + ' ' + w) > 24:
            lineas.append(actual); actual = w
        else:
            actual = (actual + ' ' + w).strip()
    lineas.append(actual)
    for i, l in enumerate(lineas):
        d.text((W / 2, 880 + i * 90), l.upper(), font=_f(70), fill=BLANCO, anchor='ma')
    return im


def grafismo(escenas, inicios, tramos, palabras, duracion, cola, idioma, carpeta):
    """Capa transparente: marca + rótulo de escena + subtítulo palabra a palabra + cierre."""
    eventos = []   # (t, png)
    k = 0

    def pinta(escena_i, grupo=None, activa=None):
        nonlocal k
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        _marca(d)
        _rotulo_escena(d, escenas[escena_i].get('texto_pantalla', ''))
        if grupo:
            _subtitulo(d, grupo, activa)
        n = os.path.join(carpeta, f'g_{k:04d}.png'); k += 1
        im.save(n)
        return n

    for i, (t0, ws) in enumerate(zip(inicios, palabras)):
        eventos.append((t0, pinta(i)))
        grupos, g = [], []
        for w in ws:
            g.append(w)
            if len(g) == 3 or w[2].endswith(('.', ',', '?', '!', ':', ';')):
                grupos.append(g); g = []
        if g:
            grupos.append(g)
        for gr in grupos:
            for j, w in enumerate(gr):
                eventos.append((t0 + w[0], pinta(i, [x[2] for x in gr], j)))
            eventos.append((t0 + gr[-1][1] + 0.05, pinta(i)))
    cierre = os.path.join(carpeta, 'g_cierre.png'); _cierre(idioma).save(cierre)
    eventos.append((duracion, cierre))
    eventos.sort(key=lambda e: e[0])
    lista = os.path.join(carpeta, 'grafismo.txt')
    with open(lista, 'w') as f:
        for j, (t, img) in enumerate(eventos):
            fin = eventos[j + 1][0] if j + 1 < len(eventos) else duracion + cola
            f.write(f"file '{img}'\nduration {max(fin - t, 0.034):.3f}\n")
        f.write(f"file '{eventos[-1][1]}'\n")
    mov = os.path.join(carpeta, 'grafismo.mov')
    sh(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-vf', f'fps={FPS},format=rgba',
        '-c:v', 'qtrle', mov])
    return mov


# ---------------- montaje ----------------
def plano(fuente, dur, i, carpeta):
    """Metraje a pantalla completa 9:16 con un barrido lento y algo de color."""
    out = os.path.join(carpeta, f'plano{i}.mp4')
    pan = '+' if i % 2 == 0 else '-'
    filtro = (f'scale=1180:2098:force_original_aspect_ratio=increase,'
              f"crop={W}:{H}:x='(iw-{W})/2{pan}(t/{dur:.2f}-0.5)*min(90\\,(iw-{W})/2)':y='(ih-{H})/2',"
              f'eq=contrast=1.06:saturation=1.12,vignette=PI/5,fps={FPS},setsar=1,format=yuv420p')
    sh(['ffmpeg', '-v', 'error', '-y', '-stream_loop', '-1', '-i', fuente, '-t', f'{dur:.3f}', '-an', '-vf', filtro,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', out])
    return out


def video_base(fuentes, tramos, carpeta):
    clips = [plano(f, d + X, i, carpeta) for i, (f, d) in enumerate(zip(fuentes, tramos))]
    entradas, cadena, ult, off = [], [], '[0:v]', 0.0
    for c in clips:
        entradas += ['-i', c]
    for i in range(1, len(clips)):
        off += tramos[i - 1]
        sal = f'[x{i}]'
        cadena.append(f'{ult}[{i}:v]xfade=transition=fade:duration={X}:offset={off:.3f}{sal}')
        ult = sal
    base = os.path.join(carpeta, 'base.mp4')
    sh(['ffmpeg', '-v', 'error', '-y', *entradas, '-filter_complex', ';'.join(cadena), '-map', ult,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', base])
    return base


def musica(carpeta):
    ruta = os.path.join(CACHE, 'musica.mp3')
    if not os.path.exists(ruta):
        r = requests.get(MUSICA[1], timeout=120); r.raise_for_status()
        open(ruta, 'wb').write(r.content)
    return ruta


def montar(g, idioma, motor, voz, etiqueta, fuentes):
    carpeta = os.path.join(SALIDA, 'tmp', f'{idioma}-{etiqueta}')
    os.makedirs(carpeta, exist_ok=True)
    tramos, wavs, palabras = [], [], []
    for e in g['escenas']:
        wav, d, ws = locutar(_pronunciar(e['locucion'], g, idioma), motor, voz,
                             os.path.join(carpeta, f'voz{e["n"]}'))
        # los subtítulos enseñan el texto original, no la grafía fonética
        orig = e['locucion'].split()
        if len(orig) == len(ws):
            ws = [(a, b, o) for (a, b, _), o in zip(ws, orig)]
        tramos.append(d + 0.18); wavs.append(wav); palabras.append(ws)
    tramos[0] += 0.0
    inicios = [sum(tramos[:i]) for i in range(len(tramos))]
    dur, cola = sum(tramos), 2.6
    tramos_v = tramos[:-1] + [tramos[-1] + cola]
    base = video_base(fuentes, tramos_v, carpeta)
    mov = grafismo(g['escenas'], inicios, tramos, palabras, dur, cola, idioma, carpeta)
    # voz: cada tramo con su silencio final, en orden
    ent, filt = [], []
    for i, (w, d) in enumerate(zip(wavs, tramos)):
        ent += ['-i', w]
        filt.append(f'[{i}:a]apad=whole_dur={d:.3f},atrim=0:{d:.3f}[a{i}]')
    voz_wav = os.path.join(carpeta, 'voz.wav')
    sh(['ffmpeg', '-v', 'error', '-y', *ent, '-filter_complex',
        ';'.join(filt) + ';' + ''.join(f'[a{i}]' for i in range(len(wavs))) + f'concat=n={len(wavs)}:v=0:a=1[v]',
        '-map', '[v]', '-ar', '44100', '-ac', '2', voz_wav])
    total = dur + cola
    mezcla = os.path.join(carpeta, 'mezcla.wav')
    sh(['ffmpeg', '-v', 'error', '-y', '-i', voz_wav, '-i', musica(carpeta), '-filter_complex',
        f'[0:a]apad=whole_dur={total:.3f},asplit[v1][v2];'
        f'[1:a]atrim=0:{total:.3f},volume=0.22,afade=t=in:d=1.2,afade=t=out:st={total - 2:.2f}:d=2[m];'
        '[m][v1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md];'
        '[v2][md]amix=inputs=2:duration=longest:normalize=0,volume=1.6,alimiter=limit=0.95[a]',
        '-map', '[a]', '-t', f'{total:.3f}', '-ar', '44100', '-ac', '2', mezcla])
    os.makedirs(SALIDA, exist_ok=True)
    salida = os.path.join(SALIDA, f'{g["topic_id"]}-{idioma}-{etiqueta}.mp4')
    sh(['ffmpeg', '-v', 'error', '-y', '-i', base, '-i', mov, '-i', mezcla, '-filter_complex',
        '[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[v]', '-map', '[v]', '-map', '2:a',
        '-c:v', 'libx264', '-crf', '20', '-preset', 'medium', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-t', f'{total:.3f}', salida])
    fallos, datos = revisar(salida)
    if not 40 <= datos['duracion'] <= 62:
        fallos.append(f'Duración fuera de 40-60 s: {datos["duracion"]} s')
    return salida, fallos, datos


def comprobar_fuentes(g):
    res = []
    for f in g.get('fuentes') or []:
        try:
            r = requests.get(f['url'], timeout=20, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
            ok = r.status_code < 400
        except requests.RequestException:
            ok = False
        res.append({**f, 'existe': ok})
        print(f'  fuente {"OK " if ok else "NO "} {f["url"]}', flush=True)
    return res


def main(ruta):
    g = json.load(open(ruta, encoding='utf-8'))
    if isinstance(g.get('videos'), list):          # por si llega con el formato del brief
        g = g['videos'][0]
    print('Tema:', g['titulo'], flush=True)
    informe = {'tema': g['topic_id'], 'fuentes': comprobar_fuentes(g), 'videos': [], 'musica': CREDITO}
    en = adaptar_en(g)
    informe['en'] = {'titulo': en['titulo'], 'metadatos': en['metadatos'],
                     'guion': ' '.join(e['locucion'] for e in en['escenas'])}
    fuentes, informe['metraje'] = metraje(g['escenas'])
    for idioma, guion in (('es', g), ('en', en)):
        for motor, voz, etiqueta in VOCES[idioma]:
            print(f'Montando {idioma} con {etiqueta}…', flush=True)
            try:
                salida, fallos, datos = montar(guion, idioma, motor, voz, etiqueta, fuentes)
                informe['videos'].append({'idioma': idioma, 'voz': etiqueta, 'archivo': os.path.basename(salida),
                                          'fallos': fallos, **datos})
                print(f'  → {os.path.basename(salida)} {datos} {fallos or "OK"}', flush=True)
            except Exception as ex:
                informe['videos'].append({'idioma': idioma, 'voz': etiqueta, 'error': repr(ex)[:500]})
                print(f'  ✗ {etiqueta}: {ex!r}'[:600], flush=True)
    json.dump(informe, open(os.path.join(SALIDA, 'informe.json'), 'w'), ensure_ascii=False, indent=1)
    if not any('archivo' in v for v in informe['videos']):
        sys.exit('No salió ningún vídeo')


if __name__ == '__main__':
    main(sys.argv[1])

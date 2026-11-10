"""Voz, rótulos y montaje del vídeo vertical 1080x1920 (todo gratis: edge-tts + Pillow + ffmpeg)."""
import asyncio
import json
import os
import subprocess

import edge_tts
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = os.path.join(AQUI, '..', 'assets', 'Anton-Regular.ttf')
VOZ = os.environ.get('NUTRIA_VOZ', 'es-ES-AlvaroNeural')
AMARILLO, BLANCO, ROJO = (255, 215, 0, 255), (255, 255, 255, 255), (230, 57, 70, 255)


def sh(cmd, **kw):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError(f'Falló: {cmd if isinstance(cmd, str) else " ".join(cmd)}\n{r.stderr[-1500:]}')
    return r.stdout


# ---------- voz ----------
async def _tts(texto, mp3):
    c = edge_tts.Communicate(texto, VOZ, rate='+8%', boundary='WordBoundary')
    palabras = []
    with open(mp3, 'wb') as f:
        async for ch in c.stream():
            if ch['type'] == 'audio':
                f.write(ch['data'])
            elif ch['type'] == 'WordBoundary':
                palabras.append([ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7, ch['text']])
    return palabras


def voz(texto, carpeta):
    mp3, wav = os.path.join(carpeta, 'voz.mp3'), os.path.join(carpeta, 'voz.wav')
    for i in range(4):
        try:
            palabras = asyncio.run(_tts(texto, mp3)); break
        except Exception:
            if i == 3: raise
    # La voz llega en trozos con marcas de tiempo que se solapan: se decodifica a PCM crudo y se rehace
    # el WAV sin marcas de tiempo. (Esto evita el fallo de «solo suenan los 2 primeros segundos».)
    sh(f'ffmpeg -v error -i "{mp3}" -f s16le -ac 1 -ar 24000 - | '
       f'ffmpeg -v error -y -f s16le -ar 24000 -ac 1 -i - -ar 44100 -ac 2 "{wav}"')
    dur = float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', wav]))
    return wav, palabras, dur


# ---------- rótulos ----------
def _f(s):
    return ImageFont.truetype(FUENTE, s)


def _cabecera(fecha_txt):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 120, W, 300], fill=(0, 0, 0, 125))
    d.text((W / 2, 132), 'UN DÍA COMO HOY', font=_f(84), fill=AMARILLO, anchor='ma')
    d.text((W / 2, 226), fecha_txt.upper(), font=_f(56), fill=BLANCO, anchor='ma')
    d.text((W / 2, H - 120), '@lanutriaroja', font=_f(40), fill=(255, 255, 255, 170), anchor='ma')
    return im


def _subtitulo(im, grupo, activa):
    d = ImageDraw.Draw(im)
    tam = 96
    while True:
        f, fa = _f(tam), _f(int(tam * 1.1))
        palabras = [w.upper() for w in grupo]
        anchos = [d.textlength(w, font=fa if i == activa else f) for i, w in enumerate(palabras)]
        esp = d.textlength(' ', font=f)
        total = sum(anchos) + esp * (len(palabras) - 1)
        if total <= W - 90 or tam <= 50:
            break
        tam -= 6
    x, y = (W - total) / 2, 1540
    for i, w in enumerate(palabras):
        d.text((x, y), w, font=fa if i == activa else f, fill=AMARILLO if i == activa else BLANCO,
               anchor='ls', stroke_width=9, stroke_fill=(0, 0, 0, 255))
        x += anchos[i] + esp
    return im


def rotulos(palabras, fecha_txt, duracion, carpeta):
    base = _cabecera(fecha_txt)
    rb = os.path.join(carpeta, 'r_base.png'); base.save(rb)
    grupos, g = [], []
    for p in palabras:
        g.append(p)
        if len(g) == 3 or p[2].endswith(('.', ',', '?', '…', ':', '!', ';')):
            grupos.append(g); g = []
    if g:
        grupos.append(g)
    cortes, k = [(0.0, rb)], 0
    for gi, g in enumerate(grupos):
        for i, p in enumerate(g):
            n = os.path.join(carpeta, f'r_{k:03d}.png'); k += 1
            _subtitulo(base.copy(), [w[2] for w in g], i).save(n)
            cortes.append((p[0], n))
        if gi + 1 == len(grupos):
            cortes.append((g[-1][1] + 0.3, rb))
    lista = os.path.join(carpeta, 'rotulos.txt')
    with open(lista, 'w') as f:
        for j, (t, img) in enumerate(cortes):
            fin = cortes[j + 1][0] if j + 1 < len(cortes) else duracion + 0.5
            f.write(f"file '{img}'\nduration {max(fin - t, 0.034):.3f}\n")
        f.write(f"file '{cortes[-1][1]}'\n")
    mov = os.path.join(carpeta, 'rotulos.mov')
    sh(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-vf', f'fps={FPS},format=rgba',
        '-c:v', 'qtrle', mov])
    return mov


# ---------- montaje ----------
def _tam(img):
    s = json.loads(sh(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                       '-of', 'json', img]))['streams'][0]
    return s['width'], s['height']


def escenas(imagenes, cortes, duracion, carpeta):
    """imagenes: rutas; cortes: inicios de cada frase. Cada frase = una foto con zoom suave."""
    tramos = []
    for i, t in enumerate(cortes):
        fin = cortes[i + 1] if i + 1 < len(cortes) else duracion + 0.4
        tramos.append((t if i else 0.0, fin))
    clips = []
    for i, (a, b) in enumerate(tramos):
        img = imagenes[i % len(imagenes)]
        d = b - a; n = max(int(round(d * FPS)), 2)
        w, h = _tam(img)
        fh = min(1080, int(1000 * h / w) // 2 * 2)
        z = f"'1+0.10*on/{n}'" if i % 2 == 0 else f"'1.10-0.10*on/{n}'"
        filtro = (f"[0]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"gblur=sigma=40,eq=brightness=-0.25[bg];"
                  f"[b]scale=2000:-2:flags=lanczos,zoompan=z={z}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1000x{fh}:fps={FPS}[fg];"
                  f"[bg][fg]overlay=(W-w)/2:{340 + (1080 - fh) // 3},format=yuv420p[v]")
        out = os.path.join(carpeta, f'clip{i}.mp4')
        sh(['ffmpeg', '-v', 'error', '-y', '-i', img, '-filter_complex', filtro, '-map', '[v]', '-r', str(FPS),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-t', f'{d:.3f}', out])
        clips.append(out)
    lista = os.path.join(carpeta, 'clips.txt')
    open(lista, 'w').writelines(f"file '{c}'\n" for c in clips)
    base = os.path.join(carpeta, 'base.mp4')
    sh(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', base])
    return base


def musica(duracion, semilla):
    acordes = [[220, 261.6, 329.6], [174.6, 220, 261.6], [196, 246.9, 293.7], [164.8, 207.7, 246.9]]
    a = acordes[semilla % 4]; b = acordes[(semilla + 1) % 4]; m = duracion / 2
    tono = lambda c: '+'.join(f'{v}*sin(2*PI*{f}*t)' for v, f in zip((1, 0.6, 0.5), c))
    return (f"aevalsrc='0.05*({tono(a)})*(0.6+0.4*sin(2*PI*0.25*t))*lt(t\\,{m:.2f})"
            f"+0.05*({tono(b)})*(0.6+0.4*sin(2*PI*0.25*t))*gte(t\\,{m:.2f})':s=44100:d={duracion + 1:.2f}")


def montar(imagenes, texto, cortes_frases, fecha_txt, carpeta, salida, semilla=0):
    wav, palabras, dur = voz(texto, carpeta)
    # inicio de cada frase según los tiempos de las palabras
    starts, k = [], 0
    for n in cortes_frases:
        starts.append(palabras[min(k, len(palabras) - 1)][0]); k += n
    mov = rotulos(palabras, fecha_txt, dur, carpeta)
    base = escenas(imagenes, starts, dur, carpeta)
    mezcla = os.path.join(carpeta, 'mezcla.wav')
    # Audio en un paso aparte: mezclarlo junto al vídeo con aresample metía silencios.
    sh(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-f', 'lavfi', '-i', musica(dur, semilla), '-filter_complex',
        f'[1:a]afade=t=in:d=1,afade=t=out:st={max(dur - 2, 0):.2f}:d=2,lowpass=f=1800[m];'
        '[0:a][m]amix=inputs=2:duration=first:normalize=0,volume=1.8,alimiter=limit=0.95[a]',
        '-map', '[a]', '-ar', '44100', '-ac', '2', mezcla])
    sh(['ffmpeg', '-v', 'error', '-y', '-i', base, '-i', mov, '-i', mezcla, '-filter_complex',
        '[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[v]', '-map', '[v]', '-map', '2:a',
        '-c:v', 'libx264', '-crf', '21', '-preset', 'medium', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', salida])
    return salida, dur

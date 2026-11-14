"""Piloto de La Nutria Roja (microdocumentales): guion JSON de ChatGPT → versión EN con Gemini →
metraje real de Pixabay → voz de mujer (varias opciones) → rótulos y subtítulos → vídeo 9:16 + control de calidad.

Uso: python -m docu.piloto docu/pilotos/<guion>.json
No publica nada: deja los MP4 y un informe en salida-docu/."""
import asyncio
import json
import os
import random
import re
import subprocess
import sys

import requests
from PIL import Image, ImageDraw, ImageFont

from nutria import calidad
from nutria.guion import llm

W, H, FPS = 1080, 1920, 30
X = 0.35                      # fundido entre escenas (s)
COLA = 2.6                    # cierre con eslogan (s)
AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = os.path.join(AQUI, '..', 'assets', 'Anton-Regular.ttf')
SALIDA = os.path.join(AQUI, '..', 'salida-docu')
CACHE = os.path.join(SALIDA, 'metraje')
ROJO, BLANCO = (232, 67, 52, 255), (255, 255, 255, 255)
ESLOGAN = {'es': 'Lo extraordinario está más cerca de lo que crees',
           'en': 'The extraordinary is closer than you think'}
VOCES = {
    'es': [('edge', 'es-ES-XimenaNeural')],
    'en': [('edge', 'en-US-AvaNeural'), ('edge', 'en-GB-SoniaNeural'), ('kokoro', 'af_heart')],
}
MUSICA = ('Floating Cities', 'https://incompetech.com/music/royalty-free/mp3-royaltyfree/Floating%20Cities.mp3')
CREDITO_MUSICA = ('Music: "Floating Cities" by Kevin MacLeod (incompetech.com), '
                  'licensed under Creative Commons: By Attribution 4.0 (creativecommons.org/licenses/by/4.0/)')


def sh(cmd):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'Falló: {cmd if isinstance(cmd, str) else " ".join(cmd)}\n{r.stderr[-1500:]}')
    return r.stdout


def duracion(f):
    return float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]))


# ---------- guion inglés ----------
def adaptar_en(g):
    pedido = {
        'titulo': g['titulo'], 'escenas': [{'n': e['n'], 'locucion': e['locucion'], 'texto_pantalla': e.get('texto_pantalla', '')}
                                           for e in g['escenas']], 'metadatos': g['metadatos']}
    msg = [{'role': 'system', 'content':
            'You localise Spanish science short-video scripts into natural, punchy American English for '
            'YouTube Shorts/TikTok/Reels. Adapt, do not translate word by word: same facts, same scene count and order, '
            'similar length per scene (spoken English ~ same duration). Keep on-screen text max 5 words. '
            'Hashtags in English. Answer ONLY JSON with the same structure: '
            '{"titulo": str, "escenas": [{"n": int, "locucion": str, "texto_pantalla": str}], '
            '"metadatos": {"titulo": str, "descripcion": str, "hashtags": [str]}}'},
           {'role': 'user', 'content': json.dumps(pedido, ensure_ascii=False)}]
    for _ in range(3):
        r = llm(msg, temperatura=0.5)
        if len(r.get('escenas', [])) == len(g['escenas']) and all(e.get('locucion') for e in r['escenas']):
            return r
    raise RuntimeError('Gemini no devolvió una versión inglesa con las mismas escenas')


# ---------- voz ----------
async def _edge(texto, voz, mp3):
    import edge_tts
    c = edge_tts.Communicate(texto, voz, rate='+6%', boundary='WordBoundary')
    pal = []
    with open(mp3, 'wb') as f:
        async for ch in c.stream():
            if ch['type'] == 'audio':
                f.write(ch['data'])
            elif ch['type'] == 'WordBoundary':
                pal.append([ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7, ch['text']])
    return pal


_KOKORO = {}


def _kokoro(texto, voz, wav):
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    lang = voz[0]
    if lang not in _KOKORO:
        _KOKORO[lang] = KPipeline(lang_code=lang)
    trozos = [a for _, _, a in _KOKORO[lang](texto, voice=voz, speed=1.05)]
    sf.write(wav, np.concatenate([t.numpy() if hasattr(t, 'numpy') else t for t in trozos]), 24000)


def _repartir(texto, dur):
    """Tiempos aproximados por palabra (proporcionales a su longitud) cuando el motor no los da."""
    ws = texto.split()
    pesos = [len(w) + 2 for w in ws]
    tot, t, out = sum(pesos), 0.08, []
    util = max(dur - 0.16, 0.5)
    for w, p in zip(ws, pesos):
        d = util * p / tot
        out.append([t, t + d, w]); t += d
    return out


def locutar(texto, motor, voz, base):
    wav = base + '.wav'
    if motor == 'edge':
        mp3 = base + '.mp3'
        for i in range(4):
            try:
                pal = asyncio.run(_edge(texto, voz, mp3)); break
            except Exception:
                if i == 3: raise
        sh(f'ffmpeg -v error -i "{mp3}" -f s16le -ac 1 -ar 24000 - | '
           f'ffmpeg -v error -y -f s16le -ar 24000 -ac 1 -i - -ar 44100 -ac 2 "{wav}"')
        d = duracion(wav)
        if len(pal) < len(texto.split()) * 0.6:
            pal = _repartir(texto, d)
    else:
        crudo = base + '_k.wav'
        _kokoro(texto, voz, crudo)
        sh(['ffmpeg', '-v', 'error', '-y', '-i', crudo, '-af', 'silenceremove=start_periods=1:start_threshold=-50dB,areverse,'
            'silenceremove=start_periods=1:start_threshold=-50dB,areverse', '-ar', '44100', '-ac', '2', wav])
        d = duracion(wav)
        pal = _repartir(texto, d)
    return wav, pal, d


# ---------- metraje ----------
import base64


def _candidatos(consultas, usados, vistos):
    clave = os.environ['PIXABAY_API_KEY']
    out = []
    for q in consultas:
        if not q:
            continue
        r = requests.get('https://pixabay.com/api/videos/', params={
            'key': clave, 'q': q[:100], 'per_page': 12, 'safesearch': 'true'}, timeout=30)
        r.raise_for_status()
        for h in r.json().get('hits', []):
            v = h['videos']
            pick = next((v[k] for k in ('large', 'medium') if v.get(k, {}).get('url') and v[k].get('height', 0) >= 1080), None)
            if pick and h['id'] not in usados and h['id'] not in vistos:
                vistos.add(h['id'])
                out.append({'h': h, 'pick': pick, 'q': q, 'mini': (v.get('small') or pick).get('thumbnail') or pick.get('thumbnail')})
    return out


def _mini_b64(url):
    try:
        return base64.b64encode(requests.get(url, timeout=30).content).decode()
    except Exception:
        return None


def _juez(escena, tema, cands):
    """Gemini mira las miniaturas y puntúa 0-10 si el clip muestra lo que dice la escena."""
    partes = [{'type': 'text', 'text':
               f'Microdocumental sobre: {tema}. Escena: «{escena["locucion"]}». Lo que debería verse: {escena["busqueda_en"]}'
               f' / {escena.get("alternativa_en", "")}. Puntúa de 0 a 10 cada miniatura según lo bien que ILUSTRA ESTA escena '
               '(10 = muestra justo eso; 5 = relacionado pero genérico; 0 = no tiene nada que ver, p. ej. un animal o paisaje '
               'cuando se habla de un vaso). Pon 0 a: fondo verde o azul de croma, pantallas, texto o logos incrustados, bebidas alcohólicas, personas mirando a cámara, render 3D o animación. Prefiere planos reales, bonitos y con movimiento natural. '
               'Responde SOLO JSON {"notas":[{"id":int,"nota":int}]}'}]
    for i, c in enumerate(cands):
        b = _mini_b64(c['mini']) if c['mini'] else None
        if not b:
            continue
        partes.append({'type': 'text', 'text': f'id={i} etiquetas: {c["h"].get("tags", "")}'})
        partes.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b}})
    try:
        r = llm([{'role': 'user', 'content': partes}], temperatura=0, rol='elegir', vision=True)
        notas = {int(x['id']): int(x['nota']) for x in r.get('notas', [])}
    except Exception as e:
        print('  juez de metraje sin respuesta:', str(e)[:120], flush=True)
        notas = {}
    for i, c in enumerate(cands):
        c['nota'] = notas.get(i, -1)
    return cands


def _bajar(c):
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, f"{c['h']['id']}.mp4")
    if not os.path.exists(ruta):
        with requests.get(c['pick']['url'], stream=True, timeout=120) as d:
            d.raise_for_status()
            with open(ruta, 'wb') as f:
                for b in d.iter_content(1 << 20):
                    f.write(b)
    return ruta


NOTA_MIN = int(os.environ.get('DOCU_NOTA_MIN', '7'))


def metraje(g, estricto=False):
    usados, clips = set(), []
    for e in g['escenas']:
        palabras = e['busqueda_en'].split()
        vistos, mejor = set(), []
        rondas = [[e['busqueda_en']], [e.get('alternativa_en')], [' '.join(palabras[:2]), ' '.join(palabras[-2:])]]
        for ronda in rondas:
            cands = _candidatos(ronda, usados, vistos)[:10]
            if cands:
                mejor += _juez(e, g['titulo'], cands)
            mejor.sort(key=lambda c: (c['nota'], c['h']['duration'] >= 6, c['h'].get('likes', 0)), reverse=True)
            if mejor and mejor[0]['nota'] >= 7:
                break
        if not mejor or (estricto and mejor[0]['nota'] < NOTA_MIN):
            print(f'  ✖ escena {e["n"]}: sin metraje que encaje (mejor nota {mejor[0]["nota"] if mejor else "—"}) → tema descartado', flush=True)
            return None
        c = mejor[0]
        usados.add(c['h']['id'])
        info = {'consulta': c['q'], 'pixabay_id': c['h']['id'], 'nota_juez': c['nota'], 'pagina': c['h']['pageURL'],
                'autor': c['h']['user'], 'licencia': 'Pixabay Content License (uso comercial, sin atribución obligatoria)'}
        print(f'  escena {e["n"]}: {c["q"]!r} → pixabay {c["h"]["id"]} (nota {c["nota"]}, {c["h"].get("tags", "")[:50]})', flush=True)
        clips.append((_bajar(c), info))
    return clips


# ---------- rótulos ----------
def _f(s):
    return ImageFont.truetype(FUENTE, s)


def _ajustar(d, texto, tam, ancho):
    while d.textlength(texto, font=_f(tam)) > ancho and tam > 40:
        tam -= 4
    return tam


def _base():
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([54, 96, 54 + 330, 96 + 64], 12, fill=ROJO)
    d.text((54 + 165, 96 + 32), 'LA NUTRIA ROJA', font=_f(40), fill=BLANCO, anchor='mm')
    return im


def _etiqueta(im, texto):
    if not texto:
        return im
    d = ImageDraw.Draw(im)
    t = texto.replace('→', '>').upper()
    tam = _ajustar(d, t, 92, W - 200)
    ancho = d.textlength(t, font=_f(tam))
    x0, y0 = (W - ancho) / 2 - 34, 330
    d.rectangle([x0, y0, x0 + ancho + 68, y0 + tam + 46], fill=(0, 0, 0, 165))
    d.rectangle([x0, y0, x0 + 12, y0 + tam + 46], fill=ROJO)
    d.text((W / 2 + 6, y0 + (tam + 46) / 2), t, font=_f(tam), fill=BLANCO, anchor='mm')
    return im


def _sub(im, grupo, activa):
    d = ImageDraw.Draw(im)
    ws = [w.upper() for w in grupo]
    tam = 88
    while True:
        f, fa = _f(tam), _f(int(tam * 1.08))
        an = [d.textlength(w, font=fa if i == activa else f) for i, w in enumerate(ws)]
        esp = d.textlength(' ', font=f)
        tot = sum(an) + esp * (len(ws) - 1)
        if tot <= W - 120 or tam <= 48:
            break
        tam -= 6
    x, y = (W - tot) / 2, 1450
    for i, w in enumerate(ws):
        d.text((x, y), w, font=fa if i == activa else f, fill=ROJO if i == activa else BLANCO, anchor='ls',
               stroke_width=8, stroke_fill=(0, 0, 0, 255))
        x += an[i] + esp
    return im


def _cierre(lang):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 175)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([W / 2 - 300, 700, W / 2 + 300, 800], 16, fill=ROJO)
    d.text((W / 2, 750), 'LA NUTRIA ROJA', font=_f(66), fill=BLANCO, anchor='mm')
    lineas, linea = [], ''
    for w in ESLOGAN[lang].split():
        if d.textlength((linea + ' ' + w).strip(), font=_f(74)) > W - 160:
            lineas.append(linea); linea = w
        else:
            linea = (linea + ' ' + w).strip()
    lineas.append(linea)
    for i, l in enumerate(lineas):
        d.text((W / 2, 900 + i * 96), l, font=_f(74), fill=BLANCO, anchor='ma')
    return im


def rotulos(escenas, inicios, palabras, total, lang, carpeta):
    """Una imagen PNG por cambio (marca + etiqueta de escena + subtítulo con palabra activa)."""
    cortes, k = [], 0

    def guarda(t, im):
        nonlocal k
        n = os.path.join(carpeta, f'r{k:04d}.png'); k += 1
        im.save(n); cortes.append((t, n))

    for i, e in enumerate(escenas):
        fondo = _etiqueta(_base(), e.get('texto_pantalla', ''))
        guarda(inicios[i], fondo)
        grupos, gr = [], []
        for p in palabras[i]:
            gr.append(p)
            if len(gr) == 3 or p[2].endswith(('.', ',', '?', '!', ':', ';', '…')):
                grupos.append(gr); gr = []
        if gr:
            grupos.append(gr)
        for grp in grupos:
            for j, p in enumerate(grp):
                guarda(inicios[i] + p[0], _sub(fondo.copy(), [w[2] for w in grp], j))
        guarda(inicios[i] + palabras[i][-1][1] + 0.15, fondo)
    guarda(total - COLA, _cierre(lang))
    lista = os.path.join(carpeta, 'rotulos.txt')
    with open(lista, 'w') as f:
        for j, (t, img) in enumerate(cortes):
            fin = cortes[j + 1][0] if j + 1 < len(cortes) else total + 0.5
            f.write(f"file '{img}'\nduration {max(fin - t, 0.034):.3f}\n")
        f.write(f"file '{cortes[-1][1]}'\n")
    mov = os.path.join(carpeta, 'rotulos.mov')
    sh(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-vf', f'fps={FPS},format=rgba',
        '-c:v', 'qtrle', mov])
    return mov


# ---------- montaje ----------
def tramo(ruta, dur, i, carpeta):
    """Metraje a pantalla completa 9:16 con paneo lento, grado de color suave y viñeta."""
    out = os.path.join(carpeta, f'tramo{i}.mp4')
    sentido = 1 if i % 2 == 0 else -1
    pan = f"(iw-ow)/2+{sentido}*min(70\\,(iw-ow)/2)*(t/{dur:.2f}-0.5)"
    vf = (f"scale=1150:2044:force_original_aspect_ratio=increase,crop={W}:{H}:x='{pan}':y='(ih-oh)/2',"
          f"eq=contrast=1.06:saturation=1.12:brightness=-0.02,vignette=PI/5,fps={FPS},format=yuv420p,setsar=1")
    sh(['ffmpeg', '-v', 'error', '-y', '-stream_loop', '-1', '-i', ruta, '-t', f'{dur:.3f}', '-an', '-vf', vf,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', out])
    return out


def montar(g, lang, motor, voz, clips, carpeta, salida):
    os.makedirs(carpeta, exist_ok=True)
    escenas = g['escenas']
    voces, palabras, durs = [], [], []
    for i, e in enumerate(escenas):
        wav, pal, d = locutar(e['locucion'], motor, voz, os.path.join(carpeta, f'voz{i}'))
        voces.append(wav); palabras.append(pal); durs.append(d + 0.22)
    inicios = [sum(durs[:i]) for i in range(len(durs))]
    habla = sum(durs)
    total = habla + COLA
    # vídeo: tramos encadenados con fundido
    tramos = []
    for i, (ruta, _) in enumerate(clips):
        largo = durs[i] + X + (COLA if i == len(clips) - 1 else 0)
        tramos.append(tramo(ruta, largo, i, carpeta))
    entradas, filtro, prev = [], [], '[0:v]'
    for t in tramos:
        entradas += ['-i', t]
    for i in range(1, len(tramos)):
        etiqueta = f'[x{i}]'
        filtro.append(f'{prev}[{i}:v]xfade=transition=fade:duration={X}:offset={inicios[i]:.3f}{etiqueta}')
        prev = etiqueta
    base = os.path.join(carpeta, 'base.mp4')
    sh(['ffmpeg', '-v', 'error', '-y', *entradas, '-filter_complex', ';'.join(filtro) or 'null', '-map', prev,
        '-t', f'{total:.3f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', base])
    # voz: cada escena rellenada hasta su duración
    partes = []
    for i, w in enumerate(voces):
        p = os.path.join(carpeta, f'vp{i}.wav')
        sh(['ffmpeg', '-v', 'error', '-y', '-i', w, '-af', f'apad=whole_dur={durs[i]:.3f}', '-t', f'{durs[i]:.3f}',
            '-ar', '44100', '-ac', '2', p])
        partes.append(p)
    lista = os.path.join(carpeta, 'voz.txt')
    open(lista, 'w').writelines(f"file '{p}'\n" for p in partes)
    vozwav = os.path.join(carpeta, 'voz.wav')
    sh(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-af', f'apad=whole_dur={total:.3f}',
        '-t', f'{total:.3f}', vozwav])
    musica = os.path.join(CACHE, 'musica.mp3')
    if not os.path.exists(musica):
        os.makedirs(CACHE, exist_ok=True)
        open(musica, 'wb').write(requests.get(MUSICA[1], timeout=120).content)
    mezcla = os.path.join(carpeta, 'mezcla.wav')
    sh(['ffmpeg', '-v', 'error', '-y', '-i', vozwav, '-ss', '8', '-i', musica, '-filter_complex',
        f'[1:a]atrim=0:{total + 0.5:.2f},volume=0.30,afade=t=in:d=1.2,afade=t=out:st={total - 1.8:.2f}:d=1.8[m];'
        '[0:a]asplit[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md];'
        '[v][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=9[a]',
        '-map', '[a]', '-ar', '44100', '-ac', '2', mezcla])
    mov = rotulos(escenas, inicios, palabras, total, lang, carpeta)
    sh(['ffmpeg', '-v', 'error', '-y', '-i', base, '-i', mov, '-i', mezcla, '-filter_complex',
        '[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[v]', '-map', '[v]', '-map', '2:a',
        '-c:v', 'libx264', '-crf', '20', '-preset', 'medium', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', salida])
    return total


def comprobar_fuentes(fuentes):
    out = []
    for f in fuentes:
        try:
            r = requests.get(f['url'], timeout=20, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
            out.append({**f, 'http': r.status_code})
        except Exception as e:
            out.append({**f, 'http': f'error {type(e).__name__}'})
    return out


def main(ruta):
    datos = json.load(open(ruta))
    temas = datos if isinstance(datos, list) else [datos]
    os.makedirs(SALIDA, exist_ok=True)
    g = clips = None
    for t in temas:
        print('▶ Probando tema:', t['titulo'], flush=True)
        clips = metraje(t, estricto=len(temas) > 1)
        if clips:
            g = t; break
    if not g:
        sys.exit('Ningún tema tiene metraje que encaje en todas sus escenas')
    print('▶ Elegido:', g['titulo'], flush=True)
    en = adaptar_en(g)
    meta_en = en['metadatos']
    meta_en['descripcion'] = re.sub(r'\s*(Science is wild!?|#.*)$', '', meta_en.get('descripcion', '')).strip() + \
        ' La Nutria Roja: ' + ESLOGAN['en'].lower().capitalize() + '.'
    g_en = {**g, 'titulo': en['titulo'], 'metadatos': meta_en,
            'escenas': [{**e, 'locucion': x['locucion'], 'texto_pantalla': x.get('texto_pantalla', '')}
                        for e, x in zip(g['escenas'], en['escenas'])]}
    informe = {'topic_id': g['topic_id'], 'temas_probados': [t['titulo'] for t in temas],
               'titulo': {'es': g['titulo'], 'en': g_en['titulo']},
               'guion_en': [e['locucion'] for e in g_en['escenas']], 'metadatos': {'es': g['metadatos'], 'en': g_en['metadatos']},
               'metraje': [c[1] for c in clips], 'musica': CREDITO_MUSICA,
               'fuentes': comprobar_fuentes(g.get('fuentes', [])), 'videos': []}
    for lang, guion in (('es', g), ('en', g_en)):
        for motor, voz in VOCES[lang]:
            nombre = f"{lang}-{voz}"
            print(f'▶ Montando {nombre}', flush=True)
            try:
                salida = os.path.join(SALIDA, f'{nombre}.mp4')
                total = montar(guion, lang, motor, voz, clips, os.path.join(SALIDA, 'tmp', nombre), salida)
                fallos, datos_qc = calidad.revisar(salida)
                if not 40 <= total <= 62:
                    fallos.append(f'Duración fuera de 40-60 s: {total:.1f}')
                informe['videos'].append({'archivo': os.path.basename(salida), 'voz': voz, 'motor': motor,
                                          'duracion': round(total, 1), 'fallos': fallos, **datos_qc})
                print(f'  {nombre}: {total:.1f} s, fallos: {fallos or "ninguno"}', flush=True)
            except Exception as e:
                informe['videos'].append({'archivo': None, 'voz': voz, 'error': str(e)[:600]})
                print(f'  {nombre}: ERROR {e}', flush=True)
    json.dump(informe, open(os.path.join(SALIDA, 'informe.json'), 'w'), ensure_ascii=False, indent=1)
    if not any(v.get('archivo') for v in informe['videos']):
        sys.exit('Ningún vídeo salió bien')


if __name__ == '__main__':
    main(sys.argv[1])

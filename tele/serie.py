"""Tele-Dimensional v2: guion de ChatGPT + clips de dibujos animados (LTX-Video, gratis en Hugging Face) + voces, cortinilla y rótulos.
Uso: python -m tele.serie montar GUION.json CARPETA_CLIPS [--salida DIR]      (monta un episodio con clips ya hechos)
     python -m tele.serie prompts GUION.json                                  (enseña lo que se le pide al animador)"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

from nutria import calidad
from . import audio, dibujo as D, episodio
from .catalogo import FORMATOS, VOCES

W, H, FPS = D.W, D.H, episodio.FPS
AQUI = os.path.dirname(os.path.abspath(__file__))

# Estilo común a todos los clips: así cada mundo es distinto pero el canal se reconoce.
ESTILO = ('2D cartoon animation, TV cartoon series style, flat bright colors, bold clean outlines, expressive faces, '
          'lively comedic character animation, vertical framing. ')
NEGATIVO = 'worst quality, inconsistent motion, blurry, jittery, distorted, photorealistic, 3d render, text, letters, watermark'

# El presentador fijo del canal: cierra todos los episodios. Sus clips se hacen una vez y se reutilizan.
PRESENTADOR = {'id': 'presentador', 'nombre': 'Tito Sintonía', 'voz': 'presentador_canal',
               'aspecto': 'a cheerful TV host with a huge orange curly quiff, black-and-white checkered jacket, black tie '
                          'and a giant silver microphone, in a colourful retro TV studio'}
CLIPS_PRESENTADOR = os.path.join(AQUI, 'presentador')

MAX_CLIP = 8.5          # lo más largo que da el animador gratis por clip


def prompt_escena(g, e):
    """Lo que se le pide al animador para una escena: estilo + lugar + quién sale y cómo es + qué pasa."""
    pers = {p['id']: p for p in g['personajes']}
    ids = [i for i in (e.get('presentes') or []) if i in pers]
    for l in e['lineas']:
        if l['quien'] in pers and l['quien'] not in ids:
            ids.append(l['quien'])
    quienes = ' '.join(f"{pers[i]['nombre']} is {pers[i]['aspecto'][:1].lower() + pers[i]['aspecto'][1:].rstrip('.')}." for i in ids)
    return f"{ESTILO}Setting: {g['lugar'].rstrip('.')}. {quienes} {e['video']}".strip()


def validar(g):
    """Comprueba que el guion v2 viene completo y lo deja listo (no lo juzga: el guion manda)."""
    g = g.get('guion', g)
    falta = [k for k in ('titulo', 'personajes', 'escenas', 'lugar') if not g.get(k)]
    if falta:
        raise ValueError(f'Al guion le falta: {", ".join(falta)}')
    if not 4 <= len(g['escenas']) <= 8:
        raise ValueError(f'El guion tiene {len(g["escenas"])} escenas (deben ser 6)')
    voces = [v for v in VOCES if v not in ('locutor', 'presentador_canal')]
    for i, p in enumerate(g['personajes']):
        p.setdefault('id', f'p{i}'); p.setdefault('nombre', p['id'].title())
        if p.get('voz') not in voces:
            p['voz'] = voces[i % len(voces)]
        if not p.get('aspecto'):
            raise ValueError(f'El personaje {p["nombre"]} no dice cómo es (aspecto)')
    ids = {p['id'] for p in g['personajes']}
    for n, e in enumerate(g['escenas'], 1):
        if not e.get('video') or not e.get('lineas'):
            raise ValueError(f'La escena {n} no trae "video" o "lineas"')
        e.setdefault('rotulo', ''); e.setdefault('musica', 'normal'); e.setdefault('prop', None)
        if e.get('sfx') not in audio.EFECTOS:
            e['sfx'] = None
        if e['musica'] not in ('normal', 'tension', 'silencio', 'triunfo'):
            e['musica'] = 'normal'
        for l in e['lineas']:
            if l.get('quien') not in ids:
                l['quien'] = 'narrador'
            l.setdefault('emocion', 'neutral'); l['texto'] = str(l.get('texto', '')).strip()
    g.setdefault('formato', 'informativo')
    if g['formato'] not in FORMATOS:
        g['formato'] = 'informativo'
    cierre = (g.get('presentador') or {}).get('cierre') or 'Esto ha sido Tele-Dimensional. El próximo universo, más raro todavía.'
    g['presentador'] = {'cierre': cierre}
    g.setdefault('titulo_corto', g['titulo']); g.setdefault('descripcion', g.get('resumen', ''))
    g.setdefault('hashtags', ['#teledimensional', '#humor', '#animacion', '#absurdo', '#dibujosanimados'])
    return g


def con_cierre(g):
    """Añade al final la escena del presentador fijo (su clip sale del banco, no se genera)."""
    g = json.loads(json.dumps(g))
    g['personajes'].append({k: PRESENTADOR[k] for k in ('id', 'nombre', 'voz', 'aspecto')})
    g['escenas'].append({'video': '', 'rotulo': 'Tele-Dimensional', 'musica': 'triunfo', 'sfx': None, 'prop': None,
                         'presentador': True, 'presentes': ['presentador'],
                         'lineas': [{'quien': 'presentador', 'texto': g['presentador']['cierre'], 'emocion': 'risa'}]})
    return g


def sorteo_falso(g):
    """El montaje viejo pide un «sorteo» (paleta, dimensión, semilla): lo sacamos del título para que sea siempre igual."""
    h = int(hashlib.sha1(g['titulo'].encode()).hexdigest(), 16)
    return {'formato': g['formato'], 'paleta': h % 8, 'semilla': h % 100000,
            'dimension': f"{'BDFGHJKLMNPQRTVXZ'[h % 17]}-{100 + h % 9900}"}


class Tramo:
    """Lee el clip de una escena ya en 1080x1920 a 30 fps y exactamente `dur` segundos, fotograma a fotograma (sin llenar el disco).
    Si el clip se queda corto, primero lo ralentiza un poco y después va y vuelve (adelante y atrás)."""

    def __init__(self, clip, dur):
        largo = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', clip],
                                     capture_output=True, text=True, check=True).stdout.strip() or 0)
        lento = min(max(dur / max(largo, 0.1), 1.0), 1.2)
        f = (f'[0:v]setpts={lento:.4f}*PTS,fps={FPS},split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,'
             f'loop=loop=-1:size=32767,trim=duration={dur:.3f},setpts=PTS-STARTPTS,'
             f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}')
        self.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', clip, '-filter_complex', f, '-an', '-pix_fmt', 'rgb24',
                                   '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
        self.n, self.ultimo = -1, np.zeros((H, W, 3), np.uint8)

    def cuadro(self, k):
        while self.n < k:
            b = self.p.stdout.read(W * H * 3)
            if len(b) < W * H * 3:
                break
            self.ultimo = np.frombuffer(b, np.uint8).reshape(H, W, 3); self.n += 1
        return self.ultimo.copy()

    def cerrar(self):
        self.p.stdout.close(); self.p.kill(); self.p.wait()


def render(g, s, lineas, inicios, cort, dur, wav, clips, salida):
    rng = np.random.default_rng(s['semilla'])
    p = D.paleta(s['paleta'])
    cab = D.cabecera(p, s['dimension'])
    carta = D.Carta(p, g['titulo'], FORMATOS[s['formato']][0].split(' ', 1)[1], s['dimension'])
    faldones = [D.faldon(e['rotulo'], p) if e['rotulo'] else None for e in g['escenas']]
    pers = {q['id']: dict(q, color=D.COLORES_VOZ[i % 5]) for i, q in enumerate(g['personajes'])}
    sellos = {i: D.sello(l['sello'], p['ac2']) for i, l in enumerate(lineas) if l['sello']}
    # cada escena ocupa desde su inicio hasta el de la siguiente (la 1.ª se corta en la cortinilla)
    fines = [cort[0]] + [inicios[i + 1] if i + 1 < len(inicios) else dur for i in range(1, len(inicios))]
    tramo, ei_ant = None, -1
    apagado = dur - 0.7
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', salida], stdin=subprocess.PIPE)
    li = 0
    for f in range(int(dur * FPS)):
        t = f / FPS
        if cort[0] <= t < cort[1]:                       # ---- cortinilla (la de siempre) ----
            tc = t - cort[0]
            im = carta.cuadro(tc, cort[2]['t_lema'], cort[2]['t_hoy'])
            gl = max(1 - tc / 0.2, 1 - (cort[1] - t) / 0.2, 0)
            ff.stdin.write(D.interferencia(np.array(im), gl, rng).tobytes())
            continue
        ei = max(i for i, x in enumerate(inicios) if x <= t)
        while li + 1 < len(lineas) and lineas[li + 1]['t0'] - 0.06 <= t:
            li += 1
        l = lineas[li]
        activa = l['t0'] - 0.06 <= t < l['t1'] + 0.12 and l['escena'] == ei
        golpe = max(0.0, 1 - (t - l['tg']) / 0.55) if l['golpe'] and t >= l['tg'] and l['escena'] == ei else 0.0
        if ei != ei_ant:
            if tramo:
                tramo.cerrar()
            tramo, ei_ant = Tramo(clips[ei], fines[ei] - inicios[ei] + 0.1), ei
        arr = tramo.cuadro(int((t - inicios[ei]) * FPS))
        if golpe:                                        # zoom de golpe
            z = 1 + 0.17 * golpe ** 2
            im = Image.fromarray(arr); cw, ch = W / z, H / z
            arr = np.array(im.resize((W, H), Image.BICUBIC, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2)))
        gl = max(0.0, 1 - t / 0.4)
        for tb in inicios[2:]:
            gl = max(gl, 1 - abs(t - tb) / 0.17)
        if t > apagado - 0.12:
            gl = max(gl, 0.5)
        arr = D.interferencia(arr, max(gl, golpe * 0.3), rng)
        if golpe > 0.85:
            arr = (arr.astype(np.uint16) + 150).clip(0, 255).astype(np.uint8)
        im = Image.fromarray(arr)
        im.paste(cab, (0, 96), cab)
        if faldones[ei]:
            entra = min((t - inicios[ei]) / 0.3, 1) if ei else min(t / 0.5, 1)
            im.paste(faldones[ei], (int(-W * (1 - entra) ** 3), 268), faldones[ei])
        if li in sellos and l['tg'] <= t < l['tg'] + 1.15 and l['escena'] == ei:
            se = sellos[li]; k = 2.3 - 1.3 * episodio._suave((t - l['tg']) / 0.13)
            if k > 1.01:
                se = se.resize((int(se.size[0] * k), int(se.size[1] * k)), Image.BILINEAR)
            im.paste(se, (W // 2 - se.size[0] // 2, 640 - se.size[1] // 2), se)
        if activa:
            for gr in l['grupos']:
                if gr[0][0] - 0.05 <= t < gr[-1][1] + 0.25:
                    act = max((i for i, w in enumerate(gr) if w[0] <= t + 0.03), default=0)
                    q = pers.get(l['quien'])
                    sub = D.subtitulo([w[2] for w in gr], act, q['nombre'] if q else '', q['color'] if q else (255, 255, 255))
                    im.paste(sub, (0, 1400), sub)
                    break
        if t >= apagado:                                 # la tele se apaga
            a = (t - apagado) / 0.4
            negro = Image.new('RGB', (W, H), (0, 0, 0))
            if a < 1:
                hh = max(int(H * (1 - a) ** 2.4), 8)
                ww = W if a < 0.65 else max(int(W * (1 - (a - 0.65) / 0.35)), 10)
                negro.paste(im.resize((ww, hh), Image.BILINEAR), ((W - ww) // 2, (H - hh) // 2))
            im = negro
        ff.stdin.write(im.tobytes())
    if tramo:
        tramo.cerrar()
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError('ffmpeg ha fallado al montar el vídeo')


def montar(guion, clips, carpeta):
    """guion: dict v2 ya validado. clips: lista de rutas, una por escena (sin la del presentador)."""
    os.makedirs(carpeta, exist_ok=True)
    g = con_cierre(guion)
    banco = sorted(os.path.join(CLIPS_PRESENTADOR, f) for f in os.listdir(CLIPS_PRESENTADOR) if f.endswith('.mp4'))
    clips = list(clips) + [banco[int(hashlib.sha1(g['titulo'].encode()).hexdigest(), 16) % len(banco)]]
    s = sorteo_falso(g)
    salida = os.path.join(carpeta, 'video.mp4')
    fallos = ['sin intentar']
    for extra in (0, 10, 22):
        lineas, inicios, cort, dur = episodio.sonido(g, s, carpeta, extra)
        if dur > 62 and extra < 22:
            print(f'  dura {dur:.0f} s: acelero las voces', flush=True); continue
        wav, _ = episodio.mezclar(g, lineas, inicios, cort, dur, np.random.default_rng(s['semilla'] + 1), carpeta)
        render(g, s, lineas, inicios, cort, dur, wav, clips, salida)
        fallos, medidas = calidad.revisar(salida)
        if not fallos:
            break
        print('  control de calidad:', fallos, flush=True)
    for fch in os.listdir(carpeta):
        if fch.startswith('voz') or fch == 'mezcla.wav':
            os.remove(os.path.join(carpeta, fch))
    if fallos:
        raise RuntimeError(f'El vídeo no pasa el control de calidad: {fallos}')
    info = {'titulo': g['titulo'], 'titulo_corto': g['titulo_corto'],
            'descripcion': g['descripcion'].strip() + '\n\n' + ' '.join(g['hashtags']) +
            '\n\nAnimación: LTX-Video (Lightricks). Guion y montaje: La Nutria Roja.',
            'guion': guion, 'calidad': medidas}
    json.dump(info, open(os.path.join(carpeta, 'info.json'), 'w'), ensure_ascii=False, indent=2)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('orden', choices=['montar', 'prompts'])
    ap.add_argument('guion')
    ap.add_argument('clips', nargs='?')
    ap.add_argument('--salida', default='salida-serie')
    a = ap.parse_args()
    g = validar(json.load(open(a.guion)))
    if a.orden == 'prompts':
        for n, e in enumerate(g['escenas'], 1):
            print(f'--- escena {n}\n{prompt_escena(g, e)}\n')
        return
    clips = [os.path.join(a.clips, f'escena{n}.mp4') for n in range(1, len(g['escenas']) + 1)]
    falta = [c for c in clips if not os.path.exists(c)]
    if falta:
        sys.exit(f'Faltan clips: {falta}')
    info = montar(g, clips, a.salida)
    print(f"✔ {info['titulo']} ({info['calidad']['duracion']} s) → {a.salida}/video.mp4")


if __name__ == '__main__':
    main()

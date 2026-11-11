"""Hace un episodio completo de Tele-Dimensional: sorteo → guion → voces → dibujos animados → vídeo → control de calidad.
Uso: python -m tele.episodio [--fecha AAAA-MM-DD] [--guion fichero.json] [--semilla N] [--registrar]"""
import argparse
import datetime as dt
import json
import math
import os
import shutil
import subprocess
import unicodedata

import numpy as np
from PIL import Image

from nutria import calidad
from . import audio, dibujo as D, ficha, guion
from .catalogo import ELEMENTOS, FORMATOS, HISTORIAL, historial, sorteo

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FPS = 30
W, H = D.W, D.H


def _grupos(texto, palabras):
    """Trozos de subtítulo de hasta 3 palabras, con el instante en que se dice cada una."""
    trozos = texto.split()
    if len(trozos) == len(palabras):
        palabras = [[p[0], p[1], w] for p, w in zip(palabras, trozos)]
    grupos, g = [], []
    for p in palabras:
        g.append(p)
        if len(g) == 3 or p[2].endswith(('.', ',', '?', '…', ':', '!', ';')):
            grupos.append(g); g = []
    if g:
        grupos.append(g)
    return grupos


CORT = 1.25          # lo que dura la cortinilla, justo después del gancho


def _norma(w):
    return ''.join(c for c in unicodedata.normalize('NFD', w.lower()) if c.isalpha())


def _momento_golpe(sello, palabras, t0):
    """El golpe cae en la palabra del sello (o la que empieza igual); si no está, al empezar la frase."""
    clave = _norma(sello.split()[0]) if sello.split() else ''
    if len(clave) >= 3:
        for w in palabras:
            n = _norma(w[2])
            if n and (n == clave or (len(n) >= 5 and n[:6] == clave[:6])):
                return w[0]
    return t0


def sonido(g, s, carpeta, extra=0):
    """Graba las voces y coloca cada línea en el tiempo, con sus pausas. Devuelve (líneas, inicios de escena, cortinilla, duración)."""
    voz_de = {p['id']: p['voz'] for p in g['personajes']}
    lineas, inicios, cort, t, k = [], [], None, 0.45, 0
    for ei, e in enumerate(g['escenas']):
        if ei == 1:
            c0 = lineas[-1]['t1'] + 0.28; cort = (c0, c0 + CORT); t = cort[1] + 0.4
        elif ei > 1:
            t = lineas[-1]['t1'] + 0.6
        inicios.append(0.0 if ei == 0 else cort[1] if ei == 1 else t - 0.28)
        for l in e['lineas']:
            t += min(max(float(l.get('pausa') or 0), 0), 1.3)
            x, palabras = audio.decir(l['texto'], voz_de.get(l['quien'], 'locutor'), carpeta, k, extra); k += 1
            grupos = [[[p[0] + t, p[1] + t, p[2]] for p in gr] for gr in _grupos(l['texto'], palabras)]
            lineas.append({'quien': l['quien'], 'emo': l['emocion'], 'escena': ei, 't0': t, 't1': t + len(x) / audio.SR, 'audio': x,
                           'golpe': bool(l.get('golpe')), 'sello': l.get('sello') or '', 'grupos': grupos,
                           'tg': _momento_golpe(l.get('sello') or '', [w for gr in grupos for w in gr], t)})
            t = lineas[-1]['t1'] + 0.2
    return lineas, inicios, cort, lineas[-1]['t1'] + 1.35


def mezclar(g, lineas, inicios, cort, dur, rng, carpeta):
    n = int(dur * audio.SR)
    voz, fx = np.zeros(n), np.zeros(n)
    apagado = dur - 0.7
    for l in lineas:
        audio.poner(voz, l['audio'], l['t0'])
    audio.poner(fx, audio.efecto('estatica', rng), 0, 0.45)
    audio.poner(fx, audio.efecto('cortinilla', rng), cort[0], 0.85)
    for ei, (e, t) in enumerate(zip(g['escenas'], inicios)):
        if ei > 1:
            audio.poner(fx, audio.efecto('estatica', rng)[:int(0.2 * audio.SR)], t - 0.1, 0.3)
        if e['sfx']:
            audio.poner(fx, audio.efecto(e['sfx'], rng), t + 0.02, 0.5)
    if len(inicios) > 3:
        audio.poner(fx, audio.efecto('subida', rng), inicios[-1] - 1.3, 0.3)       # la tensión sube antes del giro
    audio.poner(fx, audio.efecto('apagado', rng), apagado, 0.8)
    # música: cada escena tiene su momento; se calla en la cortinilla y se agacha en los golpes
    tramos = [(inicios[i], inicios[i + 1] if i + 1 < len(inicios) else dur, e.get('musica') or 'normal') for i, e in enumerate(g['escenas'])]
    tramos = [(cort[0], cort[1] + 0.1, 'mudo')] + tramos
    m = audio.musica(dur, rng, tramos)[:n] * 0.115
    tt = np.arange(n) / audio.SR
    m *= np.clip(tt / 0.6, 0, 1) * np.clip((apagado - tt) / 0.8, 0, 1)
    for l in lineas:
        if l['golpe']:
            audio.poner(fx, audio.efecto('golpe', rng), max(l['tg'] - 0.04, 0), 0.42)
            a, b = int(max(l['tg'] - 0.05, 0) * audio.SR), int((l['tg'] + 0.7) * audio.SR)
            m[a:b] *= 0.25
    wav = os.path.join(carpeta, 'mezcla.wav')
    audio.escribir_wav(voz + fx + m, wav)
    return wav, audio.envolvente(voz, FPS, int(dur * FPS) + 2)


def _posiciones(n):
    return {1: ([540], 470), 2: ([300, 780], 430), 3: ([205, 540, 875], 350), 4: ([150, 410, 670, 930], 270)}[n]


def _suave(a):
    a = min(max(a, 0), 1); return 1 - (1 - a) ** 3


def render(g, s, lineas, inicios, cort, dur, env, wav, salida):
    rng = np.random.default_rng(s['semilla'])
    p = D.paleta(s['paleta'])
    lejos, medio = D.decorado(s['formato'], p, rng)
    cab = D.cabecera(p, s['dimension'])
    carta = D.carta(p, g['titulo'], FORMATOS[s['formato']][0].split(' ', 1)[1])
    faldones = [D.faldon(e['rotulo'], p) for e in g['escenas']]
    pers = {q['id']: dict(q, color=D.COLORES_VOZ[i % 5], fase=i * 1.9, cara=bool(ELEMENTOS[q['cuerpo']][2]), orden=i)
            for i, q in enumerate(g['personajes'])}
    sellos = {i: D.sello(l['sello'], p['ac2']) for i, l in enumerate(lineas) if l['sello']}
    # quién está en el plató en cada escena, y en cuál entra por primera vez
    presentes, debut = [], {}
    for ei, e in enumerate(g['escenas']):
        ids = sorted({l['quien'] for l in e['lineas'] if l['quien'] in pers} | {i for i in e.get('presentes') or [] if i in pers},
                     key=lambda i: pers[i]['orden'])
        presentes.append(ids or (presentes[-1] if presentes else list(pers)))
        for i in presentes[-1]:
            debut.setdefault(i, ei)
    animo = [{} for _ in g['escenas']]          # cómo está cada uno mientras escucha
    for ei, e in enumerate(g['escenas']):
        for l in e['lineas']:
            if l['emocion'] in ('miedo', 'triste', 'enfado'):
                animo[ei].setdefault(l['quien'], l['emocion'])
    primeras = {min(i for i, l in enumerate(lineas) if l['escena'] == ei) for ei in range(len(inicios))}
    micro = set()
    t = 4.0
    while t < dur - 2:
        micro.update({int(t * FPS), int(t * FPS) + 1}); t += rng.uniform(4, 9)
    apagado = dur - 0.7
    nf = int(dur * FPS)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '24', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', salida], stdin=subprocess.PIPE)
    li, cam, ei_ant = 0, None, -1
    for f in range(nf):
        t = f / FPS
        # ---- cortinilla ----
        if cort[0] <= t < cort[1]:
            a = (t - cort[0]) / CORT
            z = 1.22 - 0.22 * _suave(a / 0.22) + 0.03 * a
            cw, ch = W / z, H / z
            im = carta.resize((W, H), Image.BICUBIC, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
            gl = max(1 - a / 0.13, (a - 0.87) / 0.13, 0)
            ff.stdin.write(D.interferencia(np.array(im), gl, rng).tobytes())
            cam = None
            continue
        ei = max(i for i, x in enumerate(inicios) if x <= t)
        while li + 1 < len(lineas) and lineas[li + 1]['t0'] - 0.06 <= t:
            li += 1
        l = lineas[li]
        activa = l['t0'] - 0.06 <= t < l['t1'] + 0.12 and l['escena'] == ei
        quien = l['quien'] if activa else None
        ultima = li == len(lineas) - 1 and activa
        golpe = max(0.0, 1 - (t - l['tg']) / 0.55) if l['golpe'] and t >= l['tg'] and l['escena'] == ei else 0.0
        e = g['escenas'][ei]
        modo = e.get('musica') or 'normal'
        av = (t - inicios[ei]) / max((inicios[ei + 1] if ei + 1 < len(inicios) else dur) - inicios[ei], 1)
        ids = presentes[ei]
        xs, tam = _posiciones(len(ids))
        pos = dict(zip(ids, xs))
        # ---- cámara: viaja hacia quien habla; plano general al abrir escena y con el narrador ----
        prog = min(max((t - l['t0']) / max(l['t1'] - l['t0'], 0.5), 0), 1.2)
        if quien in pos and (li not in primeras or len(e['lineas']) == 1):
            obj = [pos[quien], 1010, 1.2 + 0.05 * prog]
        else:
            obj = [540, 960, 1.0 + 0.045 * prog]
        if modo == 'tension':
            obj[2] += 0.07 * av                              # en tensión el plano se va cerrando
        elif modo == 'silencio':
            obj[2] += 0.05
        if cam is None or ei != ei_ant:
            cam = list(obj)                                  # corte seco al cambiar de escena
        else:
            cam = [c + (o - c) * 0.17 for c, o in zip(cam, obj)]
        ei_ant = ei
        z = cam[2] + 0.17 * golpe ** 2
        cx = cam[0] + 7 * math.sin(t * 0.9) + (rng.normal() * 16 * golpe if golpe else 0)
        cy = cam[1] + 5 * math.sin(t * 1.3 + 1) + (rng.normal() * 16 * golpe if golpe else 0)
        esc = D.escenario(lejos, medio, cx)
        if e['prop']:
            D.prop(esc, e['prop'], p, t, t - inicios[ei] - 0.25)
        for i in sorted(ids, key=lambda i: i == quien):          # quien habla se dibuja el último, delante
            q = pers[i]; habla = i == quien
            x = pos[i]; salto = 0
            if debut[i] == ei and ei > 0:                        # entra en el plató dando saltitos
                a = (t - inicios[ei]) / 0.55
                if a < 1:
                    x += (-1 if x < 540 else 1) * 720 * (1 - _suave(a)); salto = abs(math.sin(a * math.pi * 2.5)) * tam * 0.14
            if habla:
                emo, mira = l['emo'], (0.15 * math.sin(t * 1.7), 0.1)
                if emo in ('sorpresa', 'risa') and t >= l['t0']:
                    salto = math.sin(math.pi * min((t - l['t0']) / 0.35, 1)) * tam * 0.16
            else:
                emo = 'sorpresa' if (ultima and quien) or golpe > 0.3 else animo[ei].get(i, 'neutral')
                mira = (math.copysign(0.9, pos[quien] - pos[i]), 0.0) if quien in pos else (0, 0.2)
                if golpe:
                    salto = math.sin(math.pi * (1 - golpe)) * tam * 0.12
            D.personaje(esc, q['cuerpo'], x, tam * (1.06 if habla else 1.0), t, amp=float(env[f]) if habla else 0.0, emo=emo,
                        mira=mira, habla=habla, color=q['color'], fase=q['fase'], con_cara=q['cara'], salto=salto)
        if modo == 'tension':
            D.penumbra(esc, (110, 0, 24), 0.35 + 0.3 * av + 0.12 * math.sin(t * 7))
        elif modo == 'silencio':
            D.penumbra(esc, (0, 0, 0), 0.8)
        cw, ch = W / z, H / z
        x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), H - ch)
        esc = esc.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
        # ---- fallos de señal: al sintonizar, en cada cambio de escena y alguno suelto ----
        gl = max(0.0, 1 - t / 0.4)
        for tb in inicios[2:]:
            gl = max(gl, 1 - abs(t - tb) / 0.17)
        if f in micro:
            gl = max(gl, 0.22)
        if t > apagado - 0.12:
            gl = max(gl, 0.5)
        arr = D.interferencia(np.array(esc), max(gl, golpe * 0.3), rng)
        if golpe > 0.85:                                         # fogonazo
            arr = (arr.astype(np.uint16) + 150).clip(0, 255).astype(np.uint8)
        im = Image.fromarray(arr)
        # ---- rótulos ----
        im.paste(cab, (0, 96), cab)
        entra = min((t - inicios[ei]) / 0.3, 1) if ei else min(t / 0.5, 1)
        im.paste(faldones[ei], (int(-W * (1 - entra) ** 3), 268), faldones[ei])
        if li in sellos and l['tg'] <= t < l['tg'] + 1.15 and l['escena'] == ei:
            se = sellos[li]; k = 2.3 - 1.3 * _suave((t - l['tg']) / 0.13)
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
        # ---- la tele se apaga ----
        if t >= apagado:
            a = (t - apagado) / 0.4
            negro = Image.new('RGB', (W, H), (0, 0, 0))
            if a < 1:
                hh = max(int(H * (1 - a) ** 2.4), 8)
                ww = W if a < 0.65 else max(int(W * (1 - (a - 0.65) / 0.35)), 10)
                mini = im.resize((ww, hh), Image.BILINEAR).point(lambda v: min(255, int(v * (1 + 2.5 * a))))
                negro.paste(mini, ((W - ww) // 2, (H - hh) // 2))
            im = negro
        ff.stdin.write(im.tobytes())
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError('ffmpeg ha fallado al montar el vídeo')


def hacer(fecha, carpeta, guion_fijo=None, semilla=None):
    os.makedirs(carpeta, exist_ok=True)
    if guion_fijo:
        dato = json.load(open(guion_fijo))
        s, g = dato['sorteo'], guion.validar(dato['guion'], dato['sorteo'])
    else:
        s = sorteo(semilla)
        print(f"▶ Sorteo: {', '.join(s['elementos'])} · {s['concepto']} · {s['formato']} · {s['conflicto']}", flush=True)
        g = guion.escribir(s)
    salida = os.path.join(carpeta, 'video.mp4')
    fallos = ['sin intentar']
    for extra in (-5, 8, 22):
        lineas, inicios, cort, dur = sonido(g, s, carpeta, extra)
        if dur > 78 and extra < 22:
            print(f'  dura {dur:.0f} s: acelero las voces', flush=True); continue
        rng = np.random.default_rng(s['semilla'] + 1)
        wav, env = mezclar(g, lineas, inicios, cort, dur, rng, carpeta)
        render(g, s, lineas, inicios, cort, dur, env, wav, salida)
        fallos, medidas = calidad.revisar(salida)
        if dur < 38:
            fallos.append(f'Demasiado corto: {dur:.0f} s')
        if not fallos:
            break
        print('  control de calidad:', fallos, flush=True)
    if fallos:
        raise RuntimeError(f'El vídeo no pasa el control de calidad: {fallos}')
    info = {'fecha': fecha, 'ok': True, 'titulo': g['titulo'], 'titulo_corto': g['titulo_corto'],
            'descripcion': g['descripcion'].strip() + '\n\n' + ' '.join(g['hashtags']) +
            '\n\nDibujos: Twemoji (CC-BY 4.0), animados por La Nutria Roja.',
            'sorteo': s, 'guion': g, 'calidad': medidas}
    json.dump(info, open(os.path.join(carpeta, 'info.json'), 'w'), ensure_ascii=False, indent=2)
    open(os.path.join(carpeta, 'ficha.md'), 'w').write(ficha.escribir(info))
    for fch in os.listdir(carpeta):
        if fch.startswith('voz') or fch == 'mezcla.wav':
            os.remove(os.path.join(carpeta, fch))
    return info


def registrar(info):
    """Apunta el episodio en el historial (para no repetir) y guarda su ficha en el repositorio."""
    h = historial()
    s = info['sorteo']
    h.append({'fecha': info['fecha'], 'titulo': info['titulo'], 'elementos': s['elementos'], 'concepto': s['concepto'],
              'formato': s['formato'], 'conflicto': s['conflicto'], 'nota': info['guion'].get('nota')})
    json.dump(h, open(HISTORIAL, 'w'), ensure_ascii=False, indent=1)
    d = os.path.join(RAIZ, 'tele', 'episodios'); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"{info['fecha']}.md"), 'w').write(ficha.escribir(info))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fecha', default=dt.date.today().isoformat())
    ap.add_argument('--guion', help='JSON con {"sorteo":…, "guion":…} ya escrito (no llama a ninguna IA)')
    ap.add_argument('--semilla', type=int)
    ap.add_argument('--salida', default=os.path.join(RAIZ, 'salida-tele'))
    ap.add_argument('--registrar', action='store_true')
    a = ap.parse_args()
    carpeta = os.path.join(a.salida, a.fecha)
    shutil.rmtree(carpeta, ignore_errors=True)
    ultimo = None
    for intento in range(1 if a.guion else 2):
        try:
            info = hacer(a.fecha, carpeta, a.guion, a.semilla)
            break
        except Exception as e:
            ultimo = e; print(f'  ✖ intento {intento + 1}: {e}', flush=True)
    else:
        raise SystemExit(f'No se ha podido hacer el episodio: {ultimo}')
    json.dump([info], open(os.path.join(a.salida, 'tirada.json'), 'w'), ensure_ascii=False, indent=2)
    if a.registrar:
        registrar(info)
    print(f"✔ {info['titulo']} ({info['calidad']['duracion']} s) → {carpeta}/video.mp4")


if __name__ == '__main__':
    main()

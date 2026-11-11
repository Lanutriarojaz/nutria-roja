"""Montaje con decorados y personajes pintados por IA: cada episodio, su propio mundo.
Capas: decorado (paralaje) → personajes recortados (animados según quién habla y su emoción) → grafismo del género →
rótulos, subtítulos, sellos e interferencias. La cortinilla de Tele-Dimensional es la misma de siempre."""
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from . import dibujo as D
from .catalogo import FORMATOS

W, H, FPS = D.W, D.H, 30
PIE = 1660                                    # línea del suelo de los personajes


def _suave(a):
    a = min(max(a, 0), 1); return 1 - (1 - a) ** 3


# ---------- grafismo de cada género ----------
GRAFISMO = {   # etiqueta del faldón, color de la etiqueta, extra
    'juicio': ('EN SESIÓN', (122, 30, 40), 'mazo'), 'concurso': ('EN JUEGO', (230, 140, 0), 'reloj'),
    'informativo': ('ÚLTIMA HORA', (210, 20, 30), 'cinta'), 'documental': ('VIDA SALVAJE', (40, 120, 60), 'rec'),
    'reality': ('CONFESIONARIO', (190, 30, 140), 'dia'), 'debate': ('DEBATE', (40, 80, 200), 'votos'),
    'cocina': ('EN LA COCINA', (230, 90, 20), 'receta'), 'teletienda': ('¡LLAME YA!', (240, 200, 0), 'precio'),
    'tiempo': ('EL TIEMPO', (20, 140, 220), 'grados'), 'late': ('ESTA NOCHE', (110, 40, 200), 'rec'),
    'consultorio': ('LÍNEA ABIERTA', (140, 30, 160), 'telefono'), 'deportes': ('EN DIRECTO', (20, 150, 70), 'marcador'),
}


def faldon(texto, etiqueta, color, p):
    im = Image.new('RGBA', (W, 96), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = D.fuente(38); an = d.textlength(etiqueta, font=f) + 70
    d.polygon([(30, 8), (30 + an + 20, 8), (30 + an, 88), (30, 88)], fill=color + (255,), outline=D.TINTA + (255,), width=5)
    d.text((50, 47), etiqueta, font=f, fill=(255, 255, 255, 255), anchor='lm')
    d.polygon([(30 + an + 16, 8), (1050, 8), (1050, 88), (30 + an - 4, 88)], fill=(250, 250, 245, 255), outline=D.TINTA + (255,), width=5)
    t = 52; texto = texto.upper()
    while d.textlength(texto, font=D.fuente(t)) > 1000 - an - 40 and t > 26:
        t -= 2
    d.text(((30 + an + 1050) / 2 + 6, 47), texto, font=D.fuente(t), fill=D.TINTA + (255,), anchor='mm')
    return im


def _caja(d, x0, y0, x1, y1, fondo, borde=D.TINTA):
    d.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=fondo + (235,), outline=borde + (255,), width=5)


def extra(tipo, t, g, ei, p, color):
    """Pieza de grafismo propia del programa (marcador, cronómetro de receta, cinta de titulares…)."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f, fg = D.fuente(40), D.fuente(64)
    x0, y0 = 760, 390
    if tipo == 'reloj':                                    # cuenta atrás de concurso
        n = max(0, 30 - int(t) % 31)
        d.ellipse([880, 390, 1040, 550], fill=D.TINTA + (230,), outline=color + (255,), width=10)
        d.arc([880, 390, 1040, 550], -90, -90 + 360 * n / 30, fill=(255, 255, 255, 255), width=10)
        d.text((960, 470), str(n), font=fg, fill=(255, 255, 255, 255), anchor='mm')
    elif tipo == 'cinta':                                  # titulares que pasan
        titulares = '   ●   '.join(e['rotulo'].upper() for e in g['escenas']) + '   ●   '
        d.rectangle([0, 1838, W, 1900], fill=(15, 15, 25, 240)); d.rectangle([0, 1838, 210, 1900], fill=color + (255,))
        d.text((105, 1869), 'TITULARES', font=D.fuente(34), fill=(255, 255, 255, 255), anchor='mm')
        largo = d.textlength(titulares, font=f); x = 220 - (t * 160) % largo
        while x < W:
            d.text((x, 1869), titulares, font=f, fill=(255, 255, 255, 255), anchor='lm'); x += largo
        d.rectangle([0, 1838, 214, 1900], fill=color + (255,))
        d.text((107, 1869), 'TITULARES', font=D.fuente(34), fill=(255, 255, 255, 255), anchor='mm')
    elif tipo == 'marcador':
        _caja(d, 640, 390, 1050, 480, (15, 15, 25))
        d.text((700, 435), 'LOC', font=f, fill=(255, 255, 255, 255), anchor='mm')
        d.text((845, 435), f'{min(ei, 9)} - {min(ei // 2, 9)}', font=D.fuente(56), fill=(255, 225, 77, 255), anchor='mm')
        d.text((990, 435), 'VIS', font=f, fill=(255, 255, 255, 255), anchor='mm')
        d.text((845, 510), f"{int(t // 60) + 87}'", font=f, fill=(255, 255, 255, 255), anchor='mm', stroke_width=5, stroke_fill=(0, 0, 0, 255))
    elif tipo == 'receta':                                 # cronómetro de cocina
        _caja(d, x0, y0, 1050, y0 + 150, (255, 248, 230))
        d.text((905, y0 + 40), f'PASO {ei + 1}', font=f, fill=color + (255,), anchor='mm')
        s = int(t * 7) % 3600
        d.text((905, y0 + 100), f'{s // 60:02d}:{s % 60:02d}', font=fg, fill=D.TINTA + (255,), anchor='mm')
    elif tipo == 'precio':
        k = 1 + 0.06 * math.sin(t * 8)
        r = 120 * k; cx, cy = 935, 500
        pts = [(cx + math.cos(a / 12 * math.pi) * (r if a % 2 else r * 0.78), cy + math.sin(a / 12 * math.pi) * (r if a % 2 else r * 0.78)) for a in range(24)]
        d.polygon(pts, fill=(255, 220, 0, 255), outline=D.TINTA + (255,))
        d.text((cx, cy - 22), 'SOLO', font=D.fuente(34), fill=D.TINTA + (255,), anchor='mm')
        d.text((cx, cy + 20), '19,99', font=D.fuente(58), fill=(200, 20, 30, 255), anchor='mm')
    elif tipo == 'dia':
        _caja(d, 790, 390, 1050, 470, (20, 20, 20))
        d.ellipse([815, 415, 845, 445], fill=(230, 30, 40, 255) if int(t * 2) % 2 else (90, 20, 20, 255))
        d.text((945, 430), f'DÍA {47 + ei}', font=f, fill=(255, 255, 255, 255), anchor='mm')
    elif tipo == 'votos':
        a = 0.5 + 0.35 * math.sin(t * 0.7 + ei)
        _caja(d, 60, 1838, 1020, 1900, (15, 15, 25))
        d.rectangle([75, 1850, 75 + 930 * a, 1888], fill=(40, 120, 230, 255)); d.rectangle([75 + 930 * a, 1850, 1005, 1888], fill=(230, 60, 60, 255))
        d.text((90, 1869), f'{int(a * 100)}%', font=D.fuente(34), fill=(255, 255, 255, 255), anchor='lm')
        d.text((990, 1869), f'{100 - int(a * 100)}%', font=D.fuente(34), fill=(255, 255, 255, 255), anchor='rm')
    elif tipo == 'grados':
        _caja(d, 820, 390, 1050, 520, (230, 245, 255))
        d.text((935, 455), f'{-4 + ei * 13}°', font=D.fuente(80), fill=(20, 90, 200, 255), anchor='mm')
    elif tipo == 'telefono':
        _caja(d, 640, 390, 1050, 470, (40, 10, 50))
        d.text((845, 430), 'LLAME AL 9X9 ⋆ 000', font=f, fill=(255, 225, 77, 255), anchor='mm')
    elif tipo == 'mazo':
        _caja(d, 780, 390, 1050, 470, (60, 20, 25))
        d.text((915, 430), f'CAUSA Nº {4471 + ei}', font=D.fuente(36), fill=(255, 220, 160, 255), anchor='mm')
    elif tipo == 'rec':
        d.ellipse([930, 400, 960, 430], fill=(230, 30, 40, 255) if int(t * 1.5) % 2 else (0, 0, 0, 0))
        d.text((1045, 415), 'REC', font=f, fill=(255, 255, 255, 255), anchor='rm', stroke_width=4, stroke_fill=(0, 0, 0, 255))
    return im


# ---------- decorados y personajes ----------
def _decorado(ruta):
    """El cuadrado de FLUX ocupa la pantalla de alto a alto (con margen para el paralaje)."""
    lado = int(H * 1.1)
    return Image.open(ruta).convert('RGB').resize((lado, lado), Image.LANCZOS)


def _posiciones(n):
    return {1: ([540], 980), 2: ([290, 790], 900), 3: ([200, 540, 880], 780), 4: ([160, 410, 670, 920], 680)}[n]


def _pose(emo, habla, amp, t, fase, salto):
    """(ángulo, escala x, escala y, desplazamiento x, desplazamiento y) del personaje en este fotograma."""
    a, sx, sy, dx, dy = math.sin(t * 1.3 + fase) * 1.2, 1.0, 1.0 + 0.012 * math.sin(t * 2.3 + fase), 0.0, 0.0
    if habla:
        a += math.sin(t * 3.1 + fase) * 3.5 * (0.4 + amp)
        sy += 0.07 * amp; sx -= 0.035 * amp
        dy -= 18 * amp
    if emo == 'enfado':
        a += (6 + (3 * math.sin(t * 13) if habla else 0)); dx += math.sin(t * 55) * 5 if habla else 0
    elif emo == 'miedo':
        a -= 5; dx += math.sin(t * 47 + fase) * 6
    elif emo == 'sorpresa':
        a -= 6; sy += 0.05
    elif emo == 'risa':
        a += math.sin(t * 11 + fase) * 8; dy -= abs(math.sin(t * 11)) * 14
    elif emo == 'triste':
        a += 4; sy -= 0.04; dy += 20
    return a, sx, sy, dx, dy - salto


def render(g, s, lineas, inicios, cort, dur, env, wav, salida, imgs):
    rng = np.random.default_rng(s['semilla'])
    p = D.paleta(s['paleta'])
    etiqueta, color, tipo = GRAFISMO.get(s['formato'], ('EN DIRECTO', (225, 30, 50), 'rec'))
    cab = D.cabecera(p, s['dimension'])
    carta = D.Carta(p, g['titulo'], FORMATOS[s['formato']][0].split(' ', 1)[1], s['dimension'])
    faldones = [faldon(e['rotulo'], etiqueta, color, p) for e in g['escenas']]
    decorados = {r: _decorado(r) for r in set(imgs['decorados'])}
    pers = {q['id']: dict(q, orden=i, fase=i * 1.9, color=D.COLORES_VOZ[i % 5]) for i, q in enumerate(g['personajes'])}
    sellos = {i: D.sello(l['sello'], p['ac2']) for i, l in enumerate(lineas) if l['sello']}
    presentes, debut = [], {}
    for ei, e in enumerate(g['escenas']):
        ids = sorted({l['quien'] for l in e['lineas'] if l['quien'] in pers} | {i for i in e.get('presentes') or [] if i in pers},
                     key=lambda i: pers[i]['orden'])
        presentes.append(ids or (presentes[-1] if presentes else list(pers)))
        for i in presentes[-1]:
            debut.setdefault(i, ei)
    # cada personaje, escalado una vez para cada tamaño de plano (y su versión en sombra para cuando escucha)
    sprites = {}
    for n in range(1, 5):
        _, alto = _posiciones(n)
        for i, im in imgs['personajes'].items():
            k = alto / im.size[1]
            if im.size[0] * k > 560:
                k = 560 / im.size[0]
            base = im.resize((max(int(im.size[0] * k), 2), max(int(im.size[1] * k), 2)), Image.LANCZOS)
            oscura = ImageEnhance.Brightness(base.convert('RGB')).enhance(0.78).convert('RGBA'); oscura.putalpha(base.getchannel('A'))
            sprites[(i, n)] = (base, oscura)
    animo = [{} for _ in g['escenas']]
    for ei, e in enumerate(g['escenas']):
        for l in e['lineas']:
            if l['emocion'] in ('miedo', 'triste', 'enfado'):
                animo[ei].setdefault(l['quien'], l['emocion'])
    primeras = {min(i for i, l in enumerate(lineas) if l['escena'] == ei) for ei in range(len(inicios))}
    micro = set(); t = 4.0
    while t < dur - 2:
        micro.update({int(t * FPS), int(t * FPS) + 1}); t += rng.uniform(5, 10)
    apagado = dur - 0.7
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', salida], stdin=subprocess.PIPE)
    li, cam, ei_ant = 0, None, -1
    for f in range(int(dur * FPS)):
        t = f / FPS
        if cort[0] <= t < cort[1]:                                      # cortinilla (igual que siempre)
            tc = t - cort[0]
            im = carta.cuadro(tc, cort[2]['t_lema'], cort[2]['t_hoy'])
            gl = max(1 - tc / 0.2, 1 - (cort[1] - t) / 0.2, 0)
            ff.stdin.write(D.interferencia(np.array(im), gl, rng).tobytes()); cam = None
            continue
        ei = max(i for i, x in enumerate(inicios) if x <= t)
        while li + 1 < len(lineas) and lineas[li + 1]['t0'] - 0.06 <= t:
            li += 1
        l = lineas[li]
        activa = l['t0'] - 0.06 <= t < l['t1'] + 0.12 and l['escena'] == ei
        quien = l['quien'] if activa else None
        golpe = max(0.0, 1 - (t - l['tg']) / 0.55) if l['golpe'] and t >= l['tg'] and l['escena'] == ei else 0.0
        e = g['escenas'][ei]
        ids = presentes[ei]; xs, _ = _posiciones(len(ids)); pos = dict(zip(ids, xs))
        av = (t - inicios[ei]) / max((inicios[ei + 1] if ei + 1 < len(inicios) else dur) - inicios[ei], 1)
        # cámara
        prog = min(max((t - l['t0']) / max(l['t1'] - l['t0'], 0.5), 0), 1.2)
        if quien in pos and (li not in primeras or len(e['lineas']) == 1):
            obj = [pos[quien], 1150, 1.16 + 0.04 * prog]
        else:
            obj = [540, 960, 1.0 + 0.04 * prog]
        if (e.get('musica') or '') == 'tension':
            obj[2] += 0.06 * av
        cam = list(obj) if cam is None or ei != ei_ant else [c + (o - c) * 0.15 for c, o in zip(cam, obj)]
        ei_ant = ei
        # decorado con paralaje
        dec = decorados[imgs['decorados'][ei]]
        lado = dec.size[0]
        ox = int((lado - W) / 2 - (cam[0] - 540) * 0.18 + math.sin(t * 0.15) * 20)
        oy = int((lado - H) / 2)
        esc = dec.crop((ox, oy, ox + W, oy + H))
        dr = ImageDraw.Draw(esc, 'RGBA')
        # personajes
        for i in sorted(ids, key=lambda i: i == quien):
            habla = i == quien
            base, oscura = sprites[(i, len(ids))]
            spr = base if (habla or quien is None) else oscura
            x = pos[i]; salto = 0.0
            if debut[i] == ei and ei > 0:
                a = (t - inicios[ei]) / 0.5
                if a < 1:
                    x += (-1 if x < 540 else 1) * 700 * (1 - _suave(a)); salto = abs(math.sin(a * math.pi * 2.5)) * 40
            emo = l['emo'] if habla else ('sorpresa' if golpe > 0.3 else animo[ei].get(i, 'neutral'))
            if habla and emo in ('sorpresa', 'risa') and t >= l['t0']:
                salto += math.sin(math.pi * min((t - l['t0']) / 0.35, 1)) * 40
            ang, sx, sy, dx, dy = _pose(emo, habla, float(env[f]) if habla else 0.0, t, pers[i]['fase'], salto)
            if not habla and quien in pos:
                ang += math.copysign(3, pos[quien] - pos[i])          # se inclina hacia quien habla
            k = 1.05 if habla else 1.0
            w2, h2 = int(spr.size[0] * sx * k), int(spr.size[1] * sy * k)
            sp = spr.resize((w2, h2), Image.BILINEAR)
            if abs(ang) > 0.3:
                sp = sp.rotate(ang, resample=Image.BILINEAR, expand=True, center=(w2 / 2, h2))
            dr.ellipse([x - w2 * 0.38, PIE - 22, x + w2 * 0.38, PIE + 22], fill=(0, 0, 0, 90))
            esc.paste(sp, (int(x + dx - sp.size[0] / 2), int(PIE + dy - sp.size[1] + (sp.size[1] - h2) * 0.5)), sp)
        if (e.get('musica') or '') == 'tension':
            D.penumbra(esc, (110, 0, 24), 0.35 + 0.3 * av + 0.12 * math.sin(t * 7))
        elif (e.get('musica') or '') == 'silencio':
            D.penumbra(esc, (0, 0, 0), 0.8)
        # cámara (zoom) y sacudida de los golpes
        z = cam[2] + 0.17 * golpe ** 2
        cx = cam[0] + (rng.normal() * 16 * golpe if golpe else 0); cy = cam[1] + (rng.normal() * 16 * golpe if golpe else 0)
        cw, ch = W / z, H / z
        x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), H - ch)
        if z > 1.001:
            esc = esc.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
        gl = max(0.0, 1 - t / 0.4)
        for tb in inicios[2:]:
            gl = max(gl, 1 - abs(t - tb) / 0.17)
        if f in micro:
            gl = max(gl, 0.2)
        if t > apagado - 0.12:
            gl = max(gl, 0.5)
        arr = D.interferencia(np.array(esc), max(gl, golpe * 0.3), rng)
        if golpe > 0.85:
            arr = (arr.astype(np.uint16) + 150).clip(0, 255).astype(np.uint8)
        im = Image.fromarray(arr)
        # rótulos y grafismo del género
        im.paste(cab, (0, 96), cab)
        entra = min((t - inicios[ei]) / 0.3, 1) if ei else min(t / 0.5, 1)
        im.paste(faldones[ei], (int(-W * (1 - entra) ** 3), 268), faldones[ei])
        ex = extra(tipo, t, g, ei, p, color)
        im.paste(ex, (0, 0), ex)
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
                    im.paste(sub, (0, 1520), sub)
                    break
        if t >= apagado:
            a = (t - apagado) / 0.4
            negro = Image.new('RGB', (W, H), (0, 0, 0))
            if a < 1:
                hh = max(int(H * (1 - a) ** 2.4), 8); ww = W if a < 0.65 else max(int(W * (1 - (a - 0.65) / 0.35)), 10)
                mini = im.resize((ww, hh), Image.BILINEAR).point(lambda v: min(255, int(v * (1 + 2.5 * a))))
                negro.paste(mini, ((W - ww) // 2, (H - hh) // 2))
            im = negro
        ff.stdin.write(im.tobytes())
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError('ffmpeg ha fallado al montar el vídeo')

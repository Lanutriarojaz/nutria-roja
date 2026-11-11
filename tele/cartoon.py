"""Personajes de cartoon adulto dibujados por código (estilo propio): contorno grueso, colores planos, ojos saltones y
desiguales, ojeras, dientes torcidos, brazos de goma con manos de cuatro dedos y zapatones.

criatura(nombre, cuerpo) da la ficha del personaje, siempre la misma para el mismo nombre:
- cuerpo del catálogo (objeto): el dibujo hace de cuerpo y se le pone cara de cartoon encima.
- cuerpo del catálogo (animal): conserva su cara y gana brazos, manos y zapatos.
- cualquier otra palabra: criatura procedural (humanoide o alienígena) con cabeza, piel, ojos, pelo, antenas y ropa propios.
dibujar(dest, ficha, …) la pinta en un fotograma."""
import math
import random
import zlib

from PIL import Image, ImageDraw

from . import dibujo as D
from .catalogo import ELEMENTOS

TINTA = D.TINTA
BLANCO_OJO = (255, 252, 236)
BOCA = (74, 12, 30)
LENGUA = (240, 104, 128)
DIENTE = (255, 248, 220)
BABA = (190, 235, 255)
PIELES = [(158, 214, 92), (186, 150, 226), (112, 182, 236), (255, 207, 164), (242, 152, 172), (255, 172, 86), (168, 186, 160),
          (118, 214, 202), (232, 212, 118), (214, 170, 130), (150, 230, 160), (255, 140, 120)]
ROPAS = [(64, 92, 168), (196, 52, 64), (52, 140, 92), (232, 188, 48), (120, 70, 150), (240, 240, 230), (40, 40, 52), (230, 120, 40),
         (90, 170, 210), (170, 110, 70)]


def _osc(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _mez(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def criatura(nombre, cuerpo):
    """Ficha determinista del personaje: el mismo nombre da siempre el mismo personaje."""
    clave = f'{nombre}|{cuerpo}'.lower()
    r = random.Random(zlib.crc32(clave.encode()))
    cuerpo = (cuerpo or '').strip().lower()
    if cuerpo in ELEMENTOS:
        tipo = 'animal' if ELEMENTOS[cuerpo][2] else 'objeto'
    else:
        tipo = 'libre'
    piel = r.choice(PIELES)
    grande = r.uniform(1.0, 1.22)
    f = {
        'tipo': tipo, 'cuerpo': cuerpo, 'nombre': nombre,
        'piel': piel, 'ropa': r.choice(ROPAS), 'zapato': r.choice([(40, 40, 52), (196, 52, 64), (240, 240, 230), (120, 70, 40), (52, 92, 168)]),
        'ojos': [grande, r.uniform(0.74, 0.9)] if r.random() < 0.5 else [r.uniform(0.74, 0.9), grande],
        'bizco': r.uniform(-0.25, 0.25), 'ojeras': r.random() < 0.8, 'babas': r.random() < 0.4,
        'dientes': [r.uniform(0.7, 1.3) for _ in range(r.randint(4, 6))], 'hueco': r.randint(0, 5),
        'colmillo': r.random() < 0.35, 'ceja': r.uniform(0.8, 1.3), 'asim': r.uniform(-0.25, 0.25),
        'brazo': r.uniform(0.9, 1.15),
    }
    f.update({                                          # cuerpo humanoide para todos
        'torso': r.choice(['pera', 'saco', 'barril']), 'torso_w': r.uniform(0.42, 0.58),
        'corbata': r.random() < 0.45, 'n_ojos': 2, 'antenas': 0, 'orejas': False, 'manchas': False,
        'nariz': r.choice(['patata', 'ninguna', 'ninguna', 'bulbo']), 'pelo': 'calvo', 'pelo_c': (40, 30, 30),
        'cabeza': 'dibujo', 'cab_rx': r.uniform(0.34, 0.4), 'cab_ry': 0.37, 'piel2': _osc(piel, 0.82),
        'gesto0': r.randrange(4)})
    if tipo != 'libre':                                 # piel del color del objeto, ropa que contraste
        base = color_dibujo(cuerpo)
        f['piel'] = _mez(base, (255, 255, 255), 0.12); f['piel2'] = _osc(base, 0.8)
        f['ropa'] = max(ROPAS, key=lambda c: sum(abs(x - y) for x, y in zip(c, base)) + r.random() * 120)
    if tipo == 'libre':
        f.update({
            'cabeza': r.choice(['ovalo', 'huevo', 'pera', 'cuadrada', 'alargada', 'ancha']),
            'cab_rx': r.uniform(0.25, 0.33), 'cab_ry': r.uniform(0.24, 0.34),
            'torso': r.choice(['pera', 'saco', 'barril']), 'torso_w': r.uniform(0.42, 0.6),
            'n_ojos': r.choices([1, 2, 3], weights=[0.14, 0.72, 0.14])[0],
            'antenas': r.choices([0, 1, 2], weights=[0.55, 0.2, 0.25])[0],
            'nariz': r.choice(['patata', 'patata', 'pico', 'ninguna', 'bulbo']),
            'pelo': r.choice(['calvo', 'calvo', 'pinchos', 'mechon', 'tupe', 'pelos', 'cresta']),
            'pelo_c': r.choice([(40, 30, 30), (230, 220, 200), (210, 120, 40), (250, 200, 60), (120, 200, 255), (200, 80, 160)]),
            'orejas': r.random() < 0.45, 'corbata': r.random() < 0.45, 'manchas': r.random() < 0.3,
            'piel2': _osc(piel, 0.82),
        })
    return f


# ---------- utilidades ----------
class _Capa:
    """Lienzo al doble de tamaño con el origen en los pies del personaje."""

    def __init__(self, S):
        self.S = S; self.k = 2
        self.LW, self.LH = int(S * 2.3), int(S * 2.0)
        self.ox, self.oy = self.LW / 2, self.LH - S * 0.1
        self.im = Image.new('RGBA', (self.LW * 2, self.LH * 2), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def P(self, x, y):
        return ((self.ox + x) * 2, (self.oy + y) * 2)

    def caja(self, cx, cy, rx, ry):
        return [*self.P(cx - rx, cy - ry), *self.P(cx + rx, cy + ry)]

    def w(self, v):
        return max(int(v * 2), 2)

    def elip(self, cx, cy, rx, ry, fill, lw=None):
        self.d.ellipse(self.caja(cx, cy, rx, ry), fill=fill, outline=TINTA if lw else None, width=self.w(lw) if lw else 0)

    def poly(self, pts, fill, lw=None):
        q = [self.P(x, y) for x, y in pts]
        self.d.polygon(q, fill=fill)
        if lw:
            self.d.line(q + [q[0], q[1]], fill=TINTA, width=self.w(lw), joint='curve')

    def linea(self, pts, fill, lw):
        lim = []
        for q in pts:                              # sin puntos repetidos (PIL dibuja barras raras con ellos)
            if not lim or math.hypot(q[0] - lim[-1][0], q[1] - lim[-1][1]) > 0.5:
                lim.append(q)
        if len(lim) > 1:
            self.d.line([self.P(x, y) for x, y in lim], fill=fill, width=self.w(lw))
        r = lw / 2                                 # juntas y puntas redondas
        for x, y in lim:
            self.d.ellipse(self.caja(x, y, r * 0.98, r * 0.98), fill=fill)

    def tubo(self, pts, color, lw):
        """Trazo de color con contorno de tinta (brazos, piernas, antenas)."""
        self.linea(pts, TINTA, lw)
        self.linea(pts, color, lw * 0.55)


def _bezier(a, c, b, n=10):
    return [((1 - u) ** 2 * a[0] + 2 * (1 - u) * u * c[0] + u * u * b[0], (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * c[1] + u * u * b[1])
            for u in (i / (n - 1) for i in range(n))]


def _forma(cx, cy, rx, ry, tipo, n=40):
    pts = []
    for i in range(n):
        a = i / n * 2 * math.pi
        c, s = math.cos(a), math.sin(a)
        x, y = rx * c, ry * s
        if tipo == 'huevo':
            x *= 1 + 0.16 * s
        elif tipo == 'pera':
            x *= 1 + 0.26 * s
            y *= 1.05
        elif tipo == 'cuadrada':
            e = 0.45
            x = rx * math.copysign(abs(c) ** e, c); y = ry * math.copysign(abs(s) ** e, s)
        elif tipo == 'alargada':
            x *= 0.82; y *= 1.18
        elif tipo == 'ancha':
            x *= 1.2; y *= 0.88
        elif tipo == 'barril':
            x = rx * math.copysign(abs(c) ** 0.6, c)
        elif tipo == 'saco':
            x *= 1 + 0.12 * s
        pts.append((cx + x, cy + y))
    return pts


# ---------- partes ----------
def _mano(L, x, y, ang, color, S, puño=False):
    r = S * 0.058
    if not puño:
        for k, da in enumerate((-0.75, -0.25, 0.25)):   # tres dedos y el pulgar
            a = ang + da
            L.elip(x + math.cos(a) * r * 1.15, y + math.sin(a) * r * 1.15, r * 0.42, r * 0.42, color, S * 0.018)
        a = ang + 1.25
        L.elip(x + math.cos(a) * r * 0.95, y + math.sin(a) * r * 0.95, r * 0.4, r * 0.4, color, S * 0.018)
    L.elip(x, y, r, r * 0.92, color, S * 0.02)


def _brazo(L, f, hombro, s, S, t, amp, emo, habla, color, mira=0.0):
    x0, y0 = hombro
    largo = S * 0.36 * f['brazo']
    gesto = (f.get('gesto0', 0) + int(t / 1.3)) % 5 if habla else -1
    hacia = s * (mira or 1) > 0                           # este brazo es el que da al otro personaje
    if habla and emo == 'neutral' and gesto == 1:        # señala al otro; el otro brazo, en la cadera
        ang = -0.15 + 0.08 * math.sin(t * 9) if hacia else 0.7
        largo *= 1.25 if hacia else 0.8
    elif habla and emo == 'neutral' and gesto == 2:      # abre los brazos
        ang = -0.35 + 0.25 * math.sin(t * 6 + s) * (0.3 + amp)
        largo *= 1.15
    elif habla and gesto == 3:                           # mano al pecho / la otra explica
        if hacia:
            ang = -0.6 + 0.6 * math.sin(t * 8) * (0.4 + amp)
        else:
            hx, hy = x0 - s * S * 0.17, y0 + S * 0.24
            mx, my = (x0 + hx) / 2, (y0 + hy) / 2 + S * 0.08
            L.tubo(_bezier((x0, y0), (mx, my), (hx, hy)), color, S * 0.075)
            _mano(L, hx, hy, math.pi / 2 - s * 0.6, color, S)
            return
    elif habla:
        ang = -0.5 + 0.9 * math.sin(t * 8.5 + s * 1.3) * (0.4 + amp)
    elif emo == 'sorpresa':
        ang = -1.25
    elif emo == 'miedo':
        ang = -1.6 + 0.12 * math.sin(t * 38)
    elif emo == 'enfado':
        ang = 0.55
    elif emo == 'risa':
        ang = 0.3 + 0.25 * math.sin(t * 14)
    elif emo == 'triste':
        ang = 1.35
    else:
        ang = 1.1 + 0.06 * math.sin(t * 2.1 + s)
    hx = x0 + s * math.cos(ang) * largo
    hy = y0 + math.sin(ang) * largo * 0.9
    if emo == 'miedo' and not habla:                     # manos a la cara
        hx, hy = x0 + s * S * 0.02, y0 - S * 0.28
    if emo == 'enfado' and not habla:                    # brazos en jarras
        hx, hy = x0 + s * S * 0.2, y0 + S * 0.24
    mx, my = (x0 + hx) / 2, (y0 + hy) / 2
    curva = S * 0.13 * (1 if emo != 'enfado' else 1.6)
    nx, ny = -(hy - y0), (hx - x0)
    nn = math.hypot(nx, ny) or 1
    c = (mx + nx / nn * curva * s, my + ny / nn * curva * s)
    L.tubo(_bezier((x0, y0), c, (hx, hy)), color, S * 0.075)
    _mano(L, hx, hy, math.atan2(hy - c[1], hx - c[0]), color, S, puño=(emo == 'enfado'))


def _piernas(L, f, cadera_y, ancho, S, jx, color_pierna):
    for s in (-1, 1):
        x0 = s * ancho + jx
        x1 = s * (ancho + S * 0.03) + jx
        L.tubo([(x0, cadera_y), (x1, -S * 0.04)], color_pierna, S * 0.08)
        L.elip(x1 + s * S * 0.06, -S * 0.035, S * 0.13, S * 0.06, f['zapato'], S * 0.022)
        L.elip(x1 + s * S * 0.08, -S * 0.06, S * 0.04, S * 0.017, (255, 255, 255, 150))


def _ojo(L, ex, ey, er, f, emo, mira, cierra, piel, S, lado):
    lw = S * 0.016
    if f['ojeras'] and emo != 'risa':
        L.d.arc(L.caja(ex, ey + er * 0.12, er * 1.12, er * 1.12), 30, 150, fill=_mez(_osc(piel, 0.6), (90, 40, 110), 0.4),
                width=L.w(er * 0.22))
    if emo == 'risa':
        L.d.arc(L.caja(ex, ey + er * 0.35, er * 0.95, er * 0.8), 200, 340, fill=TINTA, width=L.w(lw * 2.2))
        return
    if cierra:
        L.linea([(ex - er, ey), (ex + er, ey)], TINTA, lw * 2.2)
        return
    ry = er * (1.12 if emo in ('sorpresa', 'miedo') else 1.04)
    L.elip(ex, ey, er, ry, BLANCO_OJO, lw)
    pr = er * (0.13 if emo in ('sorpresa', 'miedo') else 0.2)
    px = ex + (mira[0] * 0.45 + f['bizco'] * lado) * er
    py = ey + mira[1] * 0.4 * er
    L.elip(px, py, pr, pr, TINTA)
    if emo == 'enfado':                                   # venitas rojas
        for a in (0.5, 2.6):
            L.linea([(ex + math.cos(a) * er * 0.82, ey + math.sin(a) * er * 0.82),
                     (ex + math.cos(a + 0.25) * er * 0.55, ey + math.sin(a + 0.25) * er * 0.55)], (220, 60, 60), lw * 0.55)
    lid = {'neutral': 0.3, 'triste': 0.42, 'enfado': 0.36}.get(emo)
    if lid:                                               # párpado caído: cara de cansancio permanente
        th = math.degrees(math.asin(1 - 2 * lid))
        arco = [(ex + er * math.cos(math.radians(a)), ey + ry * math.sin(math.radians(a)))
                for a in [180 + th + (180 - 2 * th) * i / 16 for i in range(17)]]
        L.poly(arco, piel)
        L.linea(arco, TINTA, lw)
        L.linea([arco[0], arco[-1]], TINTA, lw * 1.6)


def _ceja(L, ex, ey, er, emo, lado, f, S):
    """lado: -1 ceja izquierda, 1 derecha (dentro = hacia el centro de la cara)."""
    y = ey - er * 1.35
    dentro, fuera = 0.0, 0.0
    if emo == 'enfado':
        dentro, fuera = er * 0.55, -er * 0.25
    elif emo in ('miedo', 'triste'):
        dentro, fuera = -er * 0.45, er * 0.2
    elif emo == 'sorpresa':
        dentro = fuera = -er * 0.55
    elif emo == 'risa':
        dentro = fuera = -er * 0.3
    else:
        fuera = f['asim'] * er * lado
    xi, xo = ex - lado * er * 0.95, ex + lado * er * 1.05
    yi, yo = y + dentro, y + fuera
    if emo == 'sorpresa':
        L.linea(_bezier((xi, yi), ((xi + xo) / 2, y - er * 1.0), (xo, yo), 7), TINTA, S * 0.032 * f['ceja'])
    else:
        L.linea([(xi, yi), ((xi + xo) / 2, min(yi, yo) - er * 0.12), (xo, yo)], TINTA, S * 0.032 * f['ceja'])


def _boca(L, mx, my, fs, f, emo, amp, habla, t, S):
    lw = S * 0.017
    mw = fs * 0.42
    a = min(1.0, amp * 1.35) if habla else 0.0
    if emo == 'risa':
        a = max(a, 0.75)
    if emo == 'sorpresa' and not habla:
        L.elip(mx, my + fs * 0.03, fs * 0.07, fs * 0.09, BOCA, lw)
        return
    if a < 0.08:                                          # boca cerrada
        if emo in ('enfado', 'miedo'):                    # dientes apretados
            h = fs * 0.07
            pts = [(mx - mw * 0.42, my - h / 2), (mx + mw * 0.42, my - h / 2), (mx + mw * 0.42, my + h / 2), (mx - mw * 0.42, my + h / 2)]
            L.poly(pts, DIENTE, lw)
            L.linea([(mx - mw * 0.42, my), (mx + mw * 0.42, my)], TINTA, lw * 0.8)
            for k in range(1, 5):
                xx = mx - mw * 0.42 + k * mw * 0.84 / 5
                L.linea([(xx, my - h / 2), (xx, my + h / 2)], TINTA, lw * 0.6)
            return
        curva = {'triste': -1, 'miedo': -0.6}.get(emo, 0.55)
        x0, x1 = mx - mw * 0.4, mx + mw * 0.4
        c = (mx + f['asim'] * mw * 0.3, my + fs * 0.07 * curva)
        L.linea(_bezier((x0, my - fs * 0.02 * curva), c, (x1, my - fs * 0.035 * curva + f['asim'] * fs * 0.03), 9), TINTA, lw * 1.7)
        if f['colmillo']:
            L.poly([(mx + mw * 0.12, my + fs * 0.005), (mx + mw * 0.22, my + fs * 0.005), (mx + mw * 0.17, my + fs * 0.07)], DIENTE, lw * 0.7)
        return
    # boca abierta: se dibuja en una capa aparte y se recorta con su forma
    mh = fs * (0.06 + 0.22 * a)
    sube = fs * (0.05 if emo == 'risa' else -0.02 if emo in ('triste', 'miedo') else 0.015)
    pts = []
    for i in range(13):
        u = -1 + 2 * i / 12
        pts.append((mx + u * mw / 2, my - sube * abs(u) ** 2 - fs * 0.012 * (1 - u * u)))
    for i in range(13):
        u = 1 - 2 * i / 12
        pts.append((mx + u * mw / 2 * (0.92 - 0.1 * (emo == 'risa')), my - sube * abs(u) ** 2 + mh * (1 - u * u) ** 0.6))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs) - 4, min(ys) - 4, max(xs) + 4, max(ys) + 4
    W2, H2 = int((x1 - x0) * 2) + 2, int((y1 - y0) * 2) + 2
    capa = Image.new('RGBA', (W2, H2), BOCA + (255,)); dd = ImageDraw.Draw(capa)
    Q = lambda x, y: ((x - x0) * 2, (y - y0) * 2)
    # lengua
    dd.ellipse([*Q(mx - mw * 0.24 + mw * 0.06, my + mh * 0.5), *Q(mx + mw * 0.24 + mw * 0.06, my + mh * 1.25)], fill=LENGUA)
    # dientes de arriba, torcidos y con hueco
    n = len(f['dientes']); ancho = mw * 0.8 / n; th = min(mh * 0.42, fs * 0.075)
    for k, v in enumerate(f['dientes']):
        if k == f['hueco'] % n and n > 4:
            continue
        xa = mx - mw * 0.4 + k * ancho
        h = th * v
        incl = (v - 1) * ancho * 0.6
        dd.polygon([Q(xa + 1, my - fs * 0.04), Q(xa + ancho - 1, my - fs * 0.04), Q(xa + ancho - 1 + incl, my - fs * 0.01 + h),
                    Q(xa + 1 + incl, my - fs * 0.01 + h)], fill=DIENTE, outline=TINTA, width=max(int(lw), 1))
    if emo in ('risa', 'enfado'):                         # algún diente de abajo
        for k in (1, 3):
            xa = mx - mw * 0.3 + k * ancho
            dd.polygon([Q(xa, my + mh + 2), Q(xa + ancho * 0.9, my + mh + 2), Q(xa + ancho * 0.45, my + mh * 0.62)], fill=DIENTE,
                       outline=TINTA, width=max(int(lw), 1))
    mascara = Image.new('L', (W2, H2), 0)
    ImageDraw.Draw(mascara).polygon([Q(x, y) for x, y in pts], fill=255)
    capa.putalpha(mascara)
    L.im.alpha_composite(capa, (int(L.P(x0, y0)[0]), int(L.P(x0, y0)[1])))
    q = [L.P(x, y) for x, y in pts]
    L.d.line(q + [q[0], q[1]], fill=TINTA, width=L.w(lw * 1.4), joint='curve')
    if f['babas'] and (a > 0.45 or emo == 'risa'):        # babilla en la comisura
        bx, by = mx + mw * 0.36, my + mh * 0.25
        largo = fs * (0.12 + 0.08 * math.sin(t * 5))
        L.linea([(bx, by), (bx + fs * 0.01, by + largo)], BABA, lw * 1.4)
        L.elip(bx + fs * 0.01, by + largo, fs * 0.022, fs * 0.028, BABA)


def _cara(L, f, fx, fy, fs, emo, amp, habla, mira, t, fase, piel, S, n_ojos=2):
    er = fs * 0.15
    cierra = ((t * 0.29 + fase) % 1) < 0.035 and emo not in ('sorpresa', 'miedo')
    ey = fy - fs * 0.12
    if n_ojos == 1:
        sitios = [(fx, ey, 1.45, 1)]
    elif n_ojos == 3:
        sitios = [(fx - fs * 0.27, ey + fs * 0.02, f['ojos'][0] * 0.85, -1), (fx, ey - fs * 0.1, 1.0, 0),
                  (fx + fs * 0.27, ey + fs * 0.02, f['ojos'][1] * 0.85, 1)]
    else:
        sitios = [(fx - fs * 0.19, ey, f['ojos'][0], -1), (fx + fs * 0.19, ey, f['ojos'][1], 1)]
    for x, y, k, lado in sitios:
        _ojo(L, x, y, er * k, f, emo, mira, cierra, piel, S, lado or 1)
    for x, y, k, lado in sitios:
        if lado:
            _ceja(L, x, y, er * k, emo, lado, f, S)
        elif emo == 'enfado':
            _ceja(L, x, y, er * k, emo, 1, f, S)
    if f.get('nariz') == 'patata':
        L.elip(fx + f['asim'] * fs * 0.1, fy + fs * 0.07, fs * 0.08, fs * 0.065, _osc(piel, 0.88), S * 0.016)
    elif f.get('nariz') == 'bulbo':
        L.elip(fx, fy + fs * 0.05, fs * 0.1, fs * 0.09, _mez(piel, (220, 90, 90), 0.4), S * 0.016)
    elif f.get('nariz') == 'pico':
        L.poly([(fx - fs * 0.05, fy + fs * 0.02), (fx + fs * 0.05, fy + fs * 0.02), (fx + fs * 0.12, fy + fs * 0.11)], _osc(piel, 0.9), S * 0.014)
    _boca(L, fx, fy + fs * 0.25, fs, f, emo, amp, habla, t, S)
    if emo == 'miedo':                                    # gota de sudor
        gx, gy = fx + fs * 0.42, fy - fs * 0.25 + (t * 30 % 20)
        L.poly([(gx, gy - fs * 0.07), (gx + fs * 0.04, gy), (gx, gy + fs * 0.03), (gx - fs * 0.04, gy)], BABA, S * 0.01)
    elif emo == 'triste':                                 # lagrimón
        gx, gy = sitios[0][0] - er * 0.2, sitios[0][1] + er * 1.2 + (t * 40 % 40)
        L.elip(gx, gy, fs * 0.03, fs * 0.04, BABA, S * 0.01)
    elif emo == 'enfado':                                 # vena en la frente
        vx, vy = fx + fs * 0.3, fy - fs * 0.48
        for a in (0.4, 1.97, 3.54, 5.11):
            L.linea([(vx + math.cos(a) * fs * 0.025, vy + math.sin(a) * fs * 0.025),
                     (vx + math.cos(a) * fs * 0.075, vy + math.sin(a) * fs * 0.075)], (220, 40, 50), S * 0.016)


# ---------- cuerpos ----------
def _pelo(L, f, cx, top, rx, S):
    c = f['pelo_c']; lw = S * 0.016
    if f['pelo'] == 'pinchos':
        for k in range(6):
            x = cx - rx * 0.7 + k * rx * 0.28
            L.poly([(x - rx * 0.13, top + S * 0.04), (x + rx * 0.13, top + S * 0.04), (x + rx * 0.05 * (k - 2.5), top - S * 0.08)], c, lw)
    elif f['pelo'] == 'mechon':
        L.poly(_bezier((cx - rx * 0.3, top + S * 0.03), (cx + rx * 0.2, top - S * 0.18), (cx + rx * 0.5, top - S * 0.02), 8)
               + [(cx + rx * 0.1, top + S * 0.03)], c, lw)
    elif f['pelo'] == 'tupe':
        L.elip(cx + rx * 0.15, top + S * 0.01, rx * 0.65, S * 0.07, c, lw)
    elif f['pelo'] == 'pelos':
        for k in range(4):
            x = cx - rx * 0.3 + k * rx * 0.2
            L.linea(_bezier((x, top + S * 0.01), (x + rx * 0.2, top - S * 0.08), (x - rx * 0.1, top - S * 0.12), 6), TINTA, lw)
    elif f['pelo'] == 'cresta':
        L.poly([(cx - rx * 0.12, top + S * 0.03), (cx + rx * 0.12, top + S * 0.03), (cx + rx * 0.05, top - S * 0.16), (cx - rx * 0.2, top - S * 0.12)], c, lw)
    else:                                                 # calvo: brillo
        L.elip(cx - rx * 0.35, top + S * 0.07, rx * 0.16, S * 0.025, (255, 255, 255, 140))


def _libre(L, f, S, t, amp, emo, mira, habla, fase, jx, sx, sy, color_voz):
    piel, lw = f['piel'], S * 0.022
    cadera = -S * 0.16
    tw = S * f['torso_w'] * sx
    th = S * 0.46 * sy
    tcy = cadera - th / 2
    torso = _forma(jx, tcy, tw / 2, th / 2, f['torso'])
    _piernas(L, f, cadera - S * 0.03, tw * 0.22, S, jx, _osc(f['ropa'], 0.55))
    hombro_y = cadera - th * 0.82
    for s in (-1, 1):                                     # brazo de detrás
        pass
    L.poly(torso, f['ropa'], lw)
    # cuello de la camisa y corbata
    L.poly([(jx - tw * 0.18, cadera - th * 0.98), (jx, cadera - th * 0.8), (jx + tw * 0.18, cadera - th * 0.98)], (245, 245, 235), lw * 0.7)
    if f['corbata']:
        L.poly([(jx - tw * 0.06, cadera - th * 0.84), (jx + tw * 0.06, cadera - th * 0.84), (jx + tw * 0.09, cadera - th * 0.35),
                (jx, cadera - th * 0.25), (jx - tw * 0.09, cadera - th * 0.35)], color_voz, lw * 0.7)
    else:
        for k in range(3):
            L.elip(jx, cadera - th * (0.62 - k * 0.2), S * 0.012, S * 0.012, TINTA)
    # cabeza
    rx, ry = S * f['cab_rx'], S * f['cab_ry']
    hcy = cadera - th - ry * 0.78 + (math.sin(t * 9.5 + fase) * S * 0.018 * (0.3 + amp) if habla else 0)
    if f['cabeza'] == 'dibujo':
        spr, fcx, fcy, fesc = D.sprite(f['cuerpo'])
        tam = rx * 2.25
        cab = spr.resize((max(int(tam * 2), 2),) * 2, Image.BILINEAR)
        L.poly([(jx - tw * 0.12, cadera - th * 0.95), (jx + tw * 0.12, cadera - th * 0.95), (jx + tw * 0.1, hcy + ry * 0.4),
                (jx - tw * 0.1, hcy + ry * 0.4)], f['piel2'], lw * 0.8)          # cuello
        x, y = L.P(jx - tam / 2, hcy - tam / 2)
        L.im.alpha_composite(cab, (int(x), int(y)))
        fs = tam * max(fesc, 0.6) * 0.95
        _cara(L, f, jx + (fcx - 0.5) * tam, hcy - tam / 2 + fcy * tam, fs, emo, amp, habla, mira, t, fase, f['piel'], S, 2)
        for s_ in (-1, 1):
            _brazo(L, f, (jx + s_ * tw * 0.42, hombro_y), s_, S, t, amp, emo, habla, f['piel'], mira[0])
        return
    if f['antenas']:
        for s in ([0] if f['antenas'] == 1 else [-1, 1]):
            x0 = jx + s * rx * 0.4; y0 = hcy - ry * 0.85
            punta = (x0 + s * rx * 0.35 + math.sin(t * 3 + fase) * S * 0.02, y0 - S * 0.2)
            L.tubo(_bezier((x0, y0), (x0 + s * rx * 0.05, y0 - S * 0.12), punta, 6), piel, S * 0.035)
            L.elip(punta[0], punta[1], S * 0.035, S * 0.035, color_voz, lw * 0.7)
    if f['orejas']:
        for s in (-1, 1):
            L.elip(jx + s * rx * 0.98, hcy + ry * 0.05, rx * 0.2, ry * 0.26, f['piel2'], lw)
    L.poly(_forma(jx, hcy, rx, ry, f['cabeza']), piel, lw)
    if f['manchas']:
        for k, (dx, dy) in enumerate(((-0.45, -0.35), (0.5, -0.1), (-0.2, 0.5))):
            L.elip(jx + dx * rx, hcy + dy * ry, rx * 0.1, ry * 0.08, f['piel2'])
    _pelo(L, f, jx, hcy - ry * 0.98, rx, S)
    fs = min(rx, ry) * 2
    _cara(L, f, jx, hcy + ry * 0.05, fs, emo, amp, habla, mira, t, fase, piel, S, f['n_ojos'])
    for s in (-1, 1):
        _brazo(L, f, (jx + s * tw * 0.42, hombro_y), s, S, t, amp, emo, habla, piel, mira[0])


_COLOR = {}


def color_dibujo(nombre):
    """Color dominante del dibujo (para párpados, brazos y piernas del objeto)."""
    if nombre not in _COLOR:
        im = D.sprite(nombre)[0].resize((48, 48), Image.BILINEAR)
        px = [p[:3] for p in im.getdata() if p[3] > 200 and sum(p[:3]) > 90]
        if not px:
            _COLOR[nombre] = (200, 200, 200)
        else:
            px.sort(key=lambda c: (c[0] // 40, c[1] // 40, c[2] // 40))
            cubos = {}
            for c in px:
                cubos.setdefault((c[0] // 40, c[1] // 40, c[2] // 40), []).append(c)
            mayor = max(cubos.values(), key=len)
            _COLOR[nombre] = tuple(sum(c[i] for c in mayor) // len(mayor) for i in range(3))
    return _COLOR[nombre]


def _con_dibujo(L, f, S, t, amp, emo, mira, habla, fase, jx, sx, sy, animal):
    spr, fcx, fcy, fesc = D.sprite(f['cuerpo'])
    con_cara = False
    bw, bh = S * sx, S * sy
    by1 = -S * 0.16; by0 = by1 - bh; bcy = (by0 + by1) / 2
    base = color_dibujo(f['cuerpo'])
    piel = _mez(base, (255, 255, 255), 0.15)            # brazos y párpados del color del objeto
    extremidad = _osc(base, 0.7)
    _piernas(L, f, by1 - S * 0.12, S * 0.12, S, jx, extremidad)
    cuerpo = spr
    if con_cara and habla:
        cuerpo = spr.rotate(math.sin(t * 11) * 5 * (0.3 + amp), resample=Image.BILINEAR)
    cuerpo = cuerpo.resize((max(int(bw * 2), 2), max(int(bh * 2), 2)), Image.BILINEAR)
    L.im.alpha_composite(cuerpo, (int(L.P(jx - bw / 2, 0)[0]), int(L.P(0, by0)[1])))
    if not con_cara:
        fx, fy, fs = (fcx - 0.5) * bw + jx, by0 + fcy * bh, S * max(fesc, 0.62) * 1.05
        _cara(L, f, fx, fy, fs, emo, amp, habla, mira, t, fase, piel, S)
    for s in (-1, 1):
        _brazo(L, f, (s * bw * 0.3 + jx, bcy + S * 0.06), s, S, t, amp, emo, habla, extremidad)


def dibujar(dest, f, cx, tam, t, amp=0.0, emo='neutral', mira=(0, 0), habla=False, fase=0.0, salto=0.0, color=(255, 225, 77), suelo=None):
    S = tam * 1.08
    L = _Capa(S)
    resp = math.sin(t * 2.3 + fase)
    sy = 1 + 0.02 * resp + 0.13 * amp
    sx = 1 - 0.012 * resp - 0.06 * amp
    jx = 0.0
    if emo == 'enfado' and habla:
        jx = math.sin(t * 61) * S * 0.012
    elif emo == 'miedo':
        jx = math.sin(t * 47 + fase) * S * 0.012
    pie = D.PIE if suelo is None else suelo
    ImageDraw.Draw(dest, 'RGBA').ellipse([cx - S * 0.42, pie - S * 0.07, cx + S * 0.42, pie + S * 0.07], fill=(0, 0, 0, 95))
    if f.get('cabeza'):
        _libre(L, f, S, t, amp, emo, mira, habla, fase, jx, sx, sy, color)
    else:
        _con_dibujo(L, f, S, t, amp, emo, mira, habla, fase, jx, sx, sy, f['tipo'] == 'animal')
    # el cuerpo entero se inclina (desde los pies) según cómo está
    hacia = 1 if (mira[0] or 0) >= 0 else -1
    if emo == 'enfado':
        ang = -hacia * (7 + (3 * math.sin(t * 13) if habla else 0))
    elif emo in ('sorpresa', 'miedo'):
        ang = hacia * 6 + (math.sin(t * 40) * 1.5 if emo == 'miedo' else 0)
    elif emo == 'risa':
        ang = math.sin(t * 11 + fase) * 9
    elif emo == 'triste':
        ang = -hacia * 4 + math.sin(t * 1.5) * 1
    else:
        ang = (math.sin(t * 3.1 + fase) * 4 * (0.4 + amp) - hacia * 2) if habla else math.sin(t * 1.3 + fase) * 1.2
    im = L.im.resize((L.LW, L.LH), Image.BOX)
    if abs(ang) > 0.2:
        im = im.rotate(ang, resample=Image.BILINEAR, center=(L.ox, L.oy))
    dest.paste(im, (int(cx - L.ox), int(pie - L.oy - salto)), im)

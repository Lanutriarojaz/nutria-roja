"""Todo lo que se ve: platós imposibles, personajes (objeto + ojos, boca, brazos y patas), rótulos e interferencias."""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, HOR, PIE = 1080, 1920, 1120, 1330
AQUI = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(AQUI, '..', 'assets')
FUENTE = os.path.join(ASSETS, 'Anton-Regular.ttf')
TINTA = (20, 10, 30)
LUZ = (255, 244, 214)

PALETAS = [
    dict(a='#12063b', b='#7b1fa2', s1='#ff2e93', s2='#2a0a4a', ac='#16e0bd', ac2='#ffe14d'),
    dict(a='#03224c', b='#0fa3b1', s1='#f7a072', s2='#0b3954', ac='#ff5d73', ac2='#f9f871'),
    dict(a='#2b0504', b='#d7263d', s1='#f49d37', s2='#3f0d12', ac='#3ddc97', ac2='#f5f749'),
    dict(a='#0b132b', b='#3a506b', s1='#5bc0be', s2='#1c2541', ac='#ff9f1c', ac2='#ff4d6d'),
    dict(a='#240046', b='#ff6d00', s1='#ffd60a', s2='#3c096c', ac='#00f5d4', ac2='#f15bb5'),
    dict(a='#002b36', b='#2aa198', s1='#b5e48c', s2='#073b4c', ac='#ef476f', ac2='#ffd166'),
    dict(a='#1a1423', b='#b7094c', s1='#89b0ae', s2='#372549', ac='#f6f740', ac2='#00bbf9'),
    dict(a='#10002b', b='#3a86ff', s1='#ff006e', s2='#240046', ac='#ffbe0b', ac2='#8ac926'),
]
COLORES_VOZ = [(255, 225, 77), (22, 224, 189), (255, 107, 157), (142, 202, 230), (255, 159, 28)]


def rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mez(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def osc(c, f=0.6):
    return tuple(int(v * f) for v in c)


def paleta(i):
    return {k: rgb(v) for k, v in PALETAS[i % len(PALETAS)].items()}


def fuente(t):
    return ImageFont.truetype(FUENTE, int(t))


# ---------- dibujos del catálogo, con contorno de tinta ----------
_SPR = {}
BORDE = 14


def sprite(nombre):
    """(imagen RGBA con contorno, cx, cy, escala de cara): centro y anchura útil del dibujo para colocarle la cara."""
    if nombre not in _SPR:
        im = Image.open(os.path.join(ASSETS, 'tele', f'{nombre}.png')).convert('RGBA')
        t = im.size[0] + 2 * BORDE
        lienzo = Image.new('RGBA', (t, t), (0, 0, 0, 0)); lienzo.paste(im, (BORDE, BORDE))
        a = lienzo.getchannel('A')
        gordo = a.filter(ImageFilter.GaussianBlur(BORDE / 2.2)).point(lambda v: 255 if v > 18 else 0).filter(ImageFilter.GaussianBlur(1.2))
        con = Image.new('RGBA', (t, t), TINTA + (255,)); con.putalpha(gordo); con.alpha_composite(lienzo)
        al = np.asarray(a) > 128
        ys, xs = np.nonzero(al)
        cy = float(np.median(ys)); filas = al[int(max(cy - 50, 0)):int(cy + 50)]
        cols = np.nonzero(filas.any(axis=0))[0]
        cx = float(cols.mean()) if len(cols) else t / 2
        ancho = float(np.median(filas.sum(axis=1))) if len(filas) else t
        _SPR[nombre] = (con, cx / t, cy / t, float(np.clip(ancho / (0.62 * t), 0.5, 1.0)))
    return _SPR[nombre]


# ---------- lienzo con suavizado (se dibuja al doble y se reduce) ----------
class Lienzo:
    def __init__(self, im, k, dx=0):
        self.im, self.k, self.dx, self.d = im, k, dx, ImageDraw.Draw(im, 'RGBA')

    def _p(self, pts):
        return [((x + self.dx) * self.k, y * self.k) for x, y in pts]

    def _velo(self, fill, pinta):
        """En una capa con transparencia, lo translúcido se funde encima en vez de agujerear lo que hay debajo."""
        if self.im.mode == 'RGBA' and isinstance(fill, tuple) and len(fill) == 4 and fill[3] < 255:
            tmp = Image.new('RGBA', self.im.size, (0, 0, 0, 0)); pinta(ImageDraw.Draw(tmp))
            self.im.alpha_composite(tmp); self.d = ImageDraw.Draw(self.im, 'RGBA')
        else:
            pinta(self.d)

    def poly(self, pts, fill, borde=None, w=5):
        self._velo(fill, lambda d: d.polygon(self._p(pts), fill=fill))
        if borde:
            self.d.line(self._p(list(pts) + [pts[0], pts[1]]), fill=borde, width=int(w * self.k), joint='curve')

    def rect(self, x0, y0, x1, y1, fill=None, borde=None, w=5, r=0):
        k = self.k; x0 += self.dx; x1 += self.dx
        self.d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], radius=r * k, fill=fill, outline=borde, width=int(w * k) if borde else 0)

    def elip(self, cx, cy, rx, ry, fill=None, borde=None, w=5):
        k = self.k; cx += self.dx
        self.d.ellipse([(cx - rx) * k, (cy - ry) * k, (cx + rx) * k, (cy + ry) * k], fill=fill, outline=borde,
                       width=int(w * k) if borde else 0)

    def linea(self, pts, fill, w=5):
        self._velo(fill, lambda d: d.line(self._p(pts), fill=fill, width=int(w * self.k), joint='curve'))

    def pega(self, nombre, cx, cy, tam, ang=0):
        s = sprite(nombre)[0].resize((int(tam * self.k),) * 2, Image.LANCZOS)
        if ang:
            s = s.rotate(ang, resample=Image.BICUBIC)
        donde = (int((cx + self.dx) * self.k - s.size[0] / 2), int(cy * self.k - s.size[1] / 2))
        if self.im.mode == 'RGBA':
            self.im.alpha_composite(s, donde) if min(donde) >= 0 else self.im.paste(s, donde, s)
        else:
            self.im.paste(s, donde, s)


# ---------- platós ----------
def _cortina(L, c1, c2, y0=340):
    for i in range(18):
        L.rect(i * 60, y0, i * 60 + 61, HOR, fill=c1 if i % 2 else c2)
        L.linea([(i * 60, y0), (i * 60, HOR)], osc(c1, 0.5), 3)
    for i in range(10):
        L.elip(60 + i * 120, y0, 62, 46, fill=osc(c2, 0.8), borde=TINTA, w=4)


def _juicio(L, p, rng):
    for x in (330, 750):
        L.poly([(x - 70, 340), (x + 70, 340), (x + 70, 700), (x, 760), (x - 70, 700)], p['ac'] if x < 540 else p['ac2'], TINTA, 5)
    for x in (95, 985):
        L.rect(x - 48, 410, x + 48, HOR - 30, fill=LUZ, borde=TINTA, w=5)
        for dx in (-22, 0, 22):
            L.linea([(x + dx, 430), (x + dx, HOR - 50)], osc(LUZ, 0.75), 4)
        L.rect(x - 74, 372, x + 74, 416, fill=LUZ, borde=TINTA, w=5, r=6)
        L.rect(x - 74, HOR - 40, x + 74, HOR, fill=LUZ, borde=TINTA, w=5, r=6)
    L.poly([(190, HOR), (890, HOR), (850, 830), (230, 830)], (122, 74, 33), TINTA, 6)
    L.rect(205, 792, 875, 836, fill=(168, 105, 47), borde=TINTA, w=6, r=8)
    L.rect(360, 880, 720, 1070, fill=(92, 53, 21), borde=TINTA, w=5, r=14)
    L.pega('balanza', 540, 975, 170)


def _concurso(L, p, rng):
    cx, cy, r = 540, 690, 270
    cols = [p['ac'], p['ac2'], p['s1'], LUZ]
    for i in range(12):
        L.d.pieslice([(cx - r) * L.k, (cy - r) * L.k, (cx + r) * L.k, (cy + r) * L.k], i * 30 + 8, i * 30 + 38, fill=cols[i % 4],
                     outline=TINTA, width=4 * L.k)
    L.elip(cx, cy, r, r, borde=TINTA, w=10); L.elip(cx, cy, 44, 44, fill=TINTA); L.elip(cx, cy, 18, 18, fill=LUZ)
    L.poly([(cx - 34, cy - r - 46), (cx + 34, cy - r - 46), (cx, cy - r + 26)], p['s1'], TINTA, 5)
    for i in range(30):
        a = i / 30 * 2 * math.pi
        L.elip(cx + math.cos(a) * (r + 44), cy + math.sin(a) * (r + 44), 13, 13, fill=LUZ if i % 2 else p['ac2'], borde=TINTA, w=3)
    for x in (70, 1010):
        L.rect(x - 34, 380, x + 34, HOR, fill=osc(p['b'], 0.5), borde=TINTA, w=5)
        for y in range(420, HOR - 20, 62):
            L.elip(x, y, 17, 17, fill=p['ac2'] if (y // 62) % 2 else p['ac'], borde=TINTA, w=3)


def _informativo(L, p, rng):
    for x0, y0, x1, y1 in ((50, 440, 345, 770), (375, 400, 705, 800), (735, 440, 1030, 770)):
        L.rect(x0, y0, x1, y1, fill=osc(p['a'], 0.8), borde=p['ac'], w=8, r=22)
    L.pega('mundo', 540, 600, 260)
    for i, h in enumerate((70, 150, 110, 200, 90)):
        L.rect(90 + i * 46, 730 - h, 122 + i * 46, 730, fill=p['ac2'])
    L.linea([(770, 700), (830, 600), (880, 660), (940, 520), (1000, 560)], p['s1'], 9)
    L.poly([(40, HOR), (1040, HOR), (980, 930), (100, 930)], osc(p['ac'], 0.75), TINTA, 6)
    L.rect(84, 900, 996, 942, fill=LUZ, borde=TINTA, w=6, r=10)
    L.rect(300, 985, 780, 1012, fill=p['ac2'])


def _documental(L, p, rng):
    L.elip(220, HOR + 60, 460, 250, fill=osc(p['b'], 0.55), borde=TINTA, w=5)
    L.elip(880, HOR + 90, 520, 330, fill=osc(p['s1'], 0.6), borde=TINTA, w=5)
    L.elip(830, 470, 90, 90, fill=LUZ, borde=TINTA, w=5); L.elip(860, 450, 22, 22, fill=osc(LUZ, 0.8)); L.elip(800, 500, 14, 14, fill=osc(LUZ, 0.8))
    L.pega('cactus', 150, HOR - 120, 280); L.pega('seta', 940, HOR - 90, 210); L.pega('seta', 820, HOR - 50, 120)
    L.pega('volcan', 520, HOR - 150, 330)


def _reality(L, p, rng):
    _cortina(L, osc(p['s1'], 0.8), osc(p['s1'], 0.55))
    L.rect(230, 470, 850, 910, borde=osc(p['ac'], 0.6), w=22, r=50); L.rect(230, 470, 850, 910, borde=p['ac'], w=9, r=50)
    L.pega('sofa', 540, HOR - 130, 440)


def _debate(L, p, rng):
    L.rect(0, 340, 540, HOR, fill=osc(p['ac'], 0.7)); L.rect(540, 340, W, HOR, fill=osc(p['ac2'], 0.7))
    z = [(560, 340), (470, 600), (590, 620), (480, 900), (600, 920), (520, HOR)]
    L.poly(z + [(x + 46, y) for x, y in reversed(z)], LUZ, TINTA, 5)
    for x, c in ((250, p['ac']), (830, p['ac2'])):
        L.poly([(x - 110, HOR), (x + 110, HOR), (x + 84, 880), (x - 84, 880)], osc(c, 0.4), TINTA, 6)
        L.rect(x - 100, 850, x + 100, 890, fill=c, borde=TINTA, w=6, r=8); L.elip(x, 990, 40, 40, fill=c, borde=TINTA, w=5)


def _cocina(L, p, rng):
    base = mez(LUZ, p['b'], 0.25)
    L.rect(0, 340, W, HOR, fill=base)
    for x in range(0, W + 1, 90):
        L.linea([(x, 340), (x, HOR)], osc(base, 0.8), 3)
    for y in range(340, HOR, 90):
        L.linea([(0, y), (W, y)], osc(base, 0.8), 3)
    L.poly([(380, 340), (700, 340), (760, 470), (320, 470)], osc(p['a'], 1.4), TINTA, 6)
    L.rect(110, 690, 970, 716, fill=(168, 105, 47), borde=TINTA, w=5)
    for n, x, t in (('olla', 240, 170), ('sarten', 450, 160), ('salero', 650, 140), ('botella', 850, 170)):
        L.pega(n, x, 700 - t / 2 + 8, t)
    L.rect(0, 950, W, HOR, fill=osc(p['ac'], 0.7), borde=TINTA, w=6)
    L.rect(-10, 925, W + 10, 962, fill=LUZ, borde=TINTA, w=6)
    for x in (180, 540, 900):
        L.rect(x - 90, 990, x + 90, HOR - 30, borde=TINTA, w=5, r=10); L.elip(x, 1010, 12, 12, fill=LUZ, borde=TINTA, w=3)


def _teletienda(L, p, rng):
    cx, cy = 540, 760
    for i in range(24):
        a0, a1 = i / 24 * 2 * math.pi, (i + 1) / 24 * 2 * math.pi
        L.poly([(cx, cy), (cx + math.cos(a0) * 1300, cy + math.sin(a0) * 1300), (cx + math.cos(a1) * 1300, cy + math.sin(a1) * 1300)],
               p['ac2'] + (150,) if i % 2 else p['ac'] + (90,))
    L.rect(390, 935, 690, HOR, fill=LUZ, borde=TINTA, w=6); L.elip(540, 935, 162, 36, fill=LUZ, borde=TINTA, w=6)
    L.elip(540, HOR, 190, 30, fill=osc(LUZ, 0.8), borde=TINTA, w=6)
    L.pega('etiqueta', 170, 540, 190, 14); L.pega('etiqueta', 915, 590, 160, -18)


def _tiempo(L, p, rng):
    L.rect(70, 400, 1010, 1020, fill=osc(p['b'], 0.8), borde=LUZ, w=10, r=34)
    for _ in range(9):
        x, y = rng.uniform(190, 890), rng.uniform(500, 920)
        L.elip(x, y, rng.uniform(50, 130), rng.uniform(40, 90), fill=osc(p['ac'], 0.8))
    for n, x, y, t in (('sol', 270, 540, 170), ('nube', 720, 530, 190), ('rayo', 770, 830, 150), ('copo', 320, 850, 140)):
        L.pega(n, x, y, t)
    L.rect(500, 1020, 580, HOR, fill=osc(LUZ, 0.6), borde=TINTA, w=5)


def _late(L, p, rng):
    _cortina(L, osc(p['b'], 0.75), osc(p['b'], 0.5))
    L.rect(200, 440, 880, 900, fill=osc(p['a'], 0.7), borde=LUZ, w=10, r=16)
    L.elip(760, 530, 46, 46, fill=LUZ)
    x = 215
    while x < 850:
        an, al = rng.uniform(50, 100), rng.uniform(120, 330)
        an = min(an, 868 - x)
        L.rect(x, 892 - al, x + an, 892, fill=TINTA)
        for yy in np.arange(892 - al + 16, 880, 30):
            for xx in np.arange(x + 12, x + an - 12, 24):
                if rng.random() < 0.55:
                    L.rect(xx, yy, xx + 10, yy + 14, fill=p['ac2'])
        x += an + 4
    L.poly([(600, HOR), (1060, HOR), (1030, 960), (630, 960)], (122, 74, 33), TINTA, 6)
    L.rect(612, 930, 1048, 968, fill=(168, 105, 47), borde=TINTA, w=6, r=8)
    L.pega('microfono', 700, 880, 130, -12)


def _consultorio(L, p, rng):
    L.rect(0, 340, W, HOR, fill=osc(p['a'], 0.7))
    for _ in range(26):
        x, y, r = rng.uniform(40, 1040), rng.uniform(380, 900), rng.uniform(10, 30)
        L.poly([(x, y - r), (x + r * .28, y - r * .28), (x + r, y), (x + r * .28, y + r * .28), (x, y + r), (x - r * .28, y + r * .28),
                (x - r, y), (x - r * .28, y - r * .28)], p['ac2'])
    L.d.arc([120 * L.k, 400 * L.k, 960 * L.k, 1500 * L.k], 180, 360, fill=p['ac'], width=16 * L.k)
    L.elip(540, HOR - 20, 360, 80, fill=osc(p['b'], 0.7), borde=TINTA, w=6)
    L.pega('bola', 540, HOR - 170, 280); L.pega('vela_d', 170, HOR - 120, 190); L.pega('vela_d', 910, HOR - 120, 190)


def _deportes(L, p, rng):
    L.rect(0, 340, W, HOR, fill=osc(p['a'], 0.8))
    cols = [p['ac'], p['ac2'], p['s1'], LUZ, p['b']]
    for fila, y in enumerate(range(600, 860, 44)):
        for x in range(20 + (fila % 2) * 22, W, 44):
            L.elip(x, y + rng.uniform(-5, 5), 17, 17, fill=cols[int(rng.integers(0, 5))], borde=TINTA, w=3)
    L.rect(290, 380, 790, 560, fill=TINTA, borde=p['ac2'], w=8, r=14)
    for x in (360, 470, 610, 720):
        L.rect(x - 36, 410, x + 36, 530, fill=osc(p['s1'], 0.9), r=8)
    L.elip(540, 440, 9, 9, fill=LUZ); L.elip(540, 500, 9, 9, fill=LUZ)
    L.rect(300, 860, 780, HOR + 4, borde=LUZ, w=12)
    for x in range(340, 780, 40):
        L.linea([(x, 866), (x, HOR)], LUZ + (110,), 3)
    for y in range(900, HOR, 40):
        L.linea([(306, y), (774, y)], LUZ + (110,), 3)


PLATOS = {'juicio': _juicio, 'concurso': _concurso, 'informativo': _informativo, 'documental': _documental, 'reality': _reality,
          'debate': _debate, 'cocina': _cocina, 'teletienda': _teletienda, 'tiempo': _tiempo, 'late': _late,
          'consultorio': _consultorio, 'deportes': _deportes}


def _imposibles(L, p, rng):
    """Cosas que flotan donde no deberían: escaleras a ninguna parte, puertas, ojos, teles, cubos."""
    tipos = list(rng.permutation(['escalera', 'puerta', 'ojo', 'tele', 'cubo', 'planeta']))[:4]
    for i, tipo in enumerate(tipos):
        x = 130 + i * 270 + rng.uniform(-40, 40); y = rng.uniform(390, 560); e = rng.uniform(0.8, 1.2)
        if tipo == 'escalera':
            pts = [(x - 80 * e, y + 70 * e)]
            for j in range(6):
                px, py = pts[-1]; pts += [(px + 26 * e, py), (px + 26 * e, py - 24 * e)]
            L.linea(pts, LUZ, 7); L.linea([(a, 2 * y - b - 70 * e) for a, b in pts], p['ac'], 7)
        elif tipo == 'puerta':
            L.rect(x - 46 * e, y - 90 * e, x + 46 * e, y + 90 * e, fill=p['s1'], borde=LUZ, w=8)
            L.rect(x - 30 * e, y - 72 * e, x + 30 * e, y + 90 * e, fill=p['a']); L.elip(x + 18 * e, y + 10 * e, 7, 7, fill=p['ac2'])
        elif tipo == 'ojo':
            L.elip(x, y, 95 * e, 56 * e, fill=LUZ, borde=TINTA, w=6); L.elip(x, y, 40 * e, 40 * e, fill=p['ac'], borde=TINTA, w=5)
            L.elip(x, y, 18 * e, 18 * e, fill=TINTA); L.elip(x - 10 * e, y - 12 * e, 7 * e, 7 * e, fill=LUZ)
        elif tipo == 'tele':
            L.linea([(x - 30 * e, y - 100 * e), (x, y - 56 * e), (x + 36 * e, y - 106 * e)], LUZ, 6)
            L.rect(x - 80 * e, y - 60 * e, x + 80 * e, y + 60 * e, fill=TINTA, borde=LUZ, w=6, r=18)
            L.rect(x - 62 * e, y - 44 * e, x + 34 * e, y + 44 * e, fill=p['ac2'], r=12)
            L.elip(x + 58 * e, y - 20 * e, 9, 9, fill=p['s1']); L.elip(x + 58 * e, y + 14 * e, 9, 9, fill=p['ac'])
        elif tipo == 'cubo':
            r = 62 * e
            L.poly([(x, y - r), (x + r, y - r / 2), (x, y), (x - r, y - r / 2)], p['ac2'], TINTA, 5)
            L.poly([(x - r, y - r / 2), (x, y), (x, y + r), (x - r, y + r / 2)], p['ac'], TINTA, 5)
            L.poly([(x + r, y - r / 2), (x, y), (x, y + r), (x + r, y + r / 2)], osc(p['ac'], 0.6), TINTA, 5)
        else:
            L.pega('planeta', x, y, 190 * e, rng.uniform(-25, 25))


MARGEN = 130                      # la capa lejana es más ancha que la pantalla para poder deslizarla (paralaje)
CERRADOS = ('reality', 'debate', 'cocina', 'late', 'consultorio', 'deportes')   # platós con pared: tapan el cielo


UNIVERSOS = ('cosmos', 'planeta', 'nave', 'laboratorio', 'piso')


def _universo(L, p, rng, tipo):
    """Lo que se ve detrás del plató: cambia con cada sorteo."""
    x0, x1 = -MARGEN, W + MARGEN
    if tipo == 'planeta':
        L.elip(160, 470, 150, 150, osc(p['ac'], 0.9), TINTA, 6)
        L.elip(160, 470, 150, 150, borde=TINTA, w=6)
        L.d.arc([(160 - 260 + L.dx) * L.k, (470 - 50) * L.k, (160 + 260 + L.dx) * L.k, (470 + 50) * L.k], 160, 380, fill=p['ac2'], width=10 * L.k)
        for (x, y, r) in ((880, 420, 46), (990, 520, 22)):
            L.elip(x, y, r, r, LUZ, TINTA, 4)
        pts = [(x0, HOR)]
        x = x0
        while x < x1:
            pts.append((x, HOR - rng.uniform(140, 330))); x += rng.uniform(50, 110)
        pts += [(x1, HOR - 200), (x1, HOR)]
        L.poly(pts, osc(p['b'], 0.45))
        x = x0 + 40
        while x < x1 - 40:                                       # ciudad alienígena
            an, al = rng.uniform(40, 90), rng.uniform(150, 380)
            c = osc(p['a'], 1.6)
            L.rect(x, HOR - al, x + an, HOR, fill=c, borde=TINTA, w=3)
            if rng.random() < 0.5:
                L.elip(x + an / 2, HOR - al, an * 0.6, an * 0.45, fill=c, borde=TINTA, w=3)
            else:
                L.linea([(x + an / 2, HOR - al), (x + an / 2, HOR - al - 50)], TINTA, 4); L.elip(x + an / 2, HOR - al - 54, 8, 8, fill=p['ac2'])
            for yy in np.arange(HOR - al + 20, HOR - 20, 34):
                if rng.random() < 0.6:
                    L.elip(x + an / 2, yy, 6, 9, fill=p['ac2'])
            x += an + rng.uniform(10, 50)
    elif tipo == 'nave':
        metal = osc(p['a'], 1.8) if sum(p['a']) < 200 else osc(p['a'], 0.8)
        for (a, b, c, d) in ((x0, 340, x1, 420), (x0, 900, x1, HOR), (x0, 340, 60, HOR), (1020, 340, x1, HOR)):
            L.rect(a, b, c, d, fill=metal)
        for xx in (60, 380, 700, 1020):
            L.rect(xx - 22, 400, xx + 22, 920, fill=osc(metal, 0.8), borde=TINTA, w=4)
            for yy in range(430, 900, 60):
                L.elip(xx, yy, 6, 6, fill=osc(metal, 1.3), borde=TINTA, w=2)
        L.rect(60, 420, 1020, 900, borde=TINTA, w=8, r=30)
        for i in range(int((x1 - x0) / 60) + 2):                  # franja de peligro
            xa = x0 + i * 60
            L.poly([(xa, 930), (xa + 30, 930), (xa + 10, 975), (xa - 20, 975)], (240, 200, 40) if i % 2 else TINTA)
        for yy in (1010, 1050):
            L.linea([(x0, yy), (x1, yy + 10)], osc(metal, 0.6), 18)
    elif tipo == 'laboratorio':
        base = mez(LUZ, p['ac'], 0.25)
        L.rect(x0, 340, x1, HOR, fill=base)
        for xx in range(int(x0), int(x1), 70):
            L.linea([(xx, 340), (xx, HOR)], osc(base, 0.85), 3)
        for yy in range(340, HOR, 70):
            L.linea([(x0, yy), (x1, yy)], osc(base, 0.85), 3)
        for xx in (90, 330, 750, 990):                              # tanques con bichos
            L.rect(xx - 80, 440, xx + 80, 960, fill=mez(p['ac'], (40, 80, 40), 0.3) + (230,), borde=TINTA, w=6, r=40)
            L.elip(xx, 700 + rng.uniform(-60, 60), 48, 70, fill=osc(p['ac'], 0.45))
            L.elip(xx - 14, 680, 9, 9, fill=LUZ); L.elip(xx + 12, 672, 6, 6, fill=LUZ)
            for _ in range(5):
                L.elip(xx + rng.uniform(-50, 50), rng.uniform(470, 930), 8, 8, borde=LUZ, w=2)
            L.rect(xx - 90, 420, xx + 90, 456, fill=osc(base, 0.6), borde=TINTA, w=5, r=8)
            L.rect(xx - 90, 950, xx + 90, 990, fill=osc(base, 0.6), borde=TINTA, w=5, r=8)
        L.linea([(x0, 380), (x1, 380)], (120, 120, 130), 22); L.linea([(x0, 380), (x1, 380)], TINTA, 3)
    elif tipo == 'piso':
        papel = mez(p['b'], LUZ, 0.45)
        L.rect(x0, 340, x1, HOR, fill=papel)
        for xx in range(int(x0), int(x1), 48):
            L.rect(xx, 340, xx + 20, HOR, fill=osc(papel, 0.9))
            for yy in range(370, HOR, 64):
                L.elip(xx + 34, yy + (xx // 48 % 2) * 32, 6, 6, fill=osc(papel, 0.75))
        for _ in range(5):                                          # manchas de humedad
            L.elip(rng.uniform(x0, x1), rng.uniform(380, 700), rng.uniform(40, 110), rng.uniform(30, 80), fill=(110, 80, 40, 60))
        L.rect(620, 440, 960, 760, fill=osc(p['a'], 0.8), borde=TINTA, w=10)          # ventana a la noche
        L.elip(860, 520, 34, 34, fill=LUZ)
        L.linea([(790, 440), (790, 760)], TINTA, 8); L.linea([(620, 600), (960, 600)], TINTA, 8)
        L.poly([(150, 470), (430, 450), (440, 690), (160, 710)], (168, 105, 47), TINTA, 6)   # cuadro torcido
        L.poly([(176, 495), (412, 478), (418, 668), (184, 684)], mez(p['ac'], LUZ, 0.3))
        L.elip(300, 600, 70, 40, fill=osc(p['ac'], 0.6)); L.elip(360, 540, 24, 24, fill=p['ac2'])
        L.linea([(540, 340), (540, 420)], TINTA, 4)
        L.poly([(500, 420), (580, 420), (560, 380), (520, 380)], p['ac2'], TINTA, 4)
        L.poly([(x1 - 120, 340), (x1, 340), (x1, 420)], osc(papel, 0.7), TINTA, 3)        # papel despegado


def _mugre(L, p, rng):
    """Suciedad, cables y basurilla en el suelo del plató."""
    for _ in range(9):
        x, y = rng.uniform(0, W), rng.uniform(HOR + 40, H - 80)
        e = 0.4 + (y - HOR) / (H - HOR)
        L.elip(x, y, rng.uniform(30, 90) * e, rng.uniform(10, 26) * e, fill=(60, 40, 20, int(rng.uniform(40, 80))))
    for _ in range(2):
        y0 = rng.uniform(HOR + 120, H - 150)
        pts = [(-20, y0)]
        for k in range(1, 8):
            pts.append((k * W / 7, y0 + rng.uniform(-60, 60)))
        L.linea(pts, TINTA, 9)
    for _ in range(3):
        x, y = rng.uniform(60, W - 60), rng.uniform(HOR + 300, H - 60)
        L.poly([(x - 18, y), (x + 14, y - 12), (x + 22, y + 8), (x - 6, y + 16)], LUZ, TINTA, 3)


def decorado(formato, p, rng):
    """Devuelve (capa lejana RGB, capa del plató RGBA o None). Si el plató tiene pared, va todo en una sola capa."""
    k = 2; WL = W + 2 * MARGEN
    t = np.linspace(0, 1, HOR * k)[:, None, None]
    cielo = (np.array(p['a'])[None, None, :] * (1 - t) + np.array(p['b'])[None, None, :] * t)
    arr = np.zeros((H * k, WL * k, 3), dtype=np.uint8)
    arr[:HOR * k] = np.broadcast_to(cielo, (HOR * k, WL * k, 3)).astype(np.uint8)
    arr[HOR * k:] = np.array(p['b'], dtype=np.uint8)
    lejos = Image.fromarray(arr); L = Lienzo(lejos, k, dx=MARGEN)
    for _ in range(190):
        r = rng.uniform(1, 3.4)
        L.elip(rng.uniform(-MARGEN, W + MARGEN), rng.uniform(0, HOR - 60), r, r, fill=(255, 255, 255, int(rng.uniform(90, 255))))
    universo = UNIVERSOS[int(rng.integers(0, len(UNIVERSOS)))]
    _universo(L, p, rng, universo)
    if universo in ('cosmos', 'planeta'):
        _imposibles(L, p, rng)
    medio = Image.new('RGBA', (W * k, H * k), (0, 0, 0, 0)); L = Lienzo(medio, k)
    PLATOS.get(formato, _documental)(L, p, rng)
    n = 9                                              # suelo de damero en perspectiva
    ys = [HOR + (H - HOR) * (j / n) ** 1.7 for j in range(n + 1)]
    X = lambda j, y: W / 2 + j * 230 * (0.18 + 0.82 * (y - HOR) / (H - HOR))
    for f in range(n):
        for j in range(-15, 15):
            L.poly([(X(j, ys[f]), ys[f]), (X(j + 1, ys[f]), ys[f]), (X(j + 1, ys[f + 1]), ys[f + 1]), (X(j, ys[f + 1]), ys[f + 1])],
                   p['s1'] if (j + f) % 2 == 0 else p['s2'])
    _mugre(L, p, rng)
    L.linea([(0, HOR), (W, HOR)], TINTA, 8)
    for x0, x1 in ((120, 620), (960, 460)):            # focos
        L.poly([(x0 - 40, 0), (x0 + 40, 0), (x1 + 330, PIE + 40), (x1 - 330, PIE + 40)], (255, 255, 255, 20))
    lejos = lejos.resize((WL, H), Image.LANCZOS); medio = medio.resize((W, H), Image.LANCZOS)
    if formato in CERRADOS:
        junto = lejos.crop((MARGEN, 0, MARGEN + W, H)); junto.paste(medio, (0, 0), medio)
        return junto, None
    return lejos, medio


def escenario(lejos, medio, camx):
    """El plató visto con la cámara en camx: el cielo se mueve menos que el decorado."""
    if medio is None:
        return lejos.copy()
    ox = int(min(max(MARGEN - (camx - W / 2) * 0.32, 0), 2 * MARGEN))
    esc = lejos.crop((ox, 0, ox + W, H)); esc.paste(medio, (0, 0), medio)
    return esc


class Carta:
    """La entradilla del canal, por capas: rayos que giran, logo, lema y, al final, el programa y el título de hoy."""

    def __init__(self, p, titulo, genero, dimension):
        k = 2; R = 1150
        im = Image.new('RGBA', (2 * R * k, 2 * R * k), (0, 0, 0, 0)); L = Lienzo(im, k)
        for i in range(28):
            a0, a1 = i / 28 * 2 * math.pi, (i + 1) / 28 * 2 * math.pi
            L.poly([(R, R), (R + math.cos(a0) * 2 * R, R + math.sin(a0) * 2 * R), (R + math.cos(a1) * 2 * R, R + math.sin(a1) * 2 * R)],
                   p['b'] if i % 2 else osc(p['b'], 0.55))
        self.rayos = im.resize((2 * R, 2 * R), Image.LANCZOS).convert('RGB'); self.R = R
        # capa 1: tele y logo
        c1 = Image.new('RGBA', (W, H), (0, 0, 0, 0)); L = Lienzo(c1, 1)
        L.pega('tele', 540, 470, 400)
        d = ImageDraw.Draw(c1)
        d.polygon([(-20, 700), (W + 20, 640), (W + 20, 900), (-20, 960)], fill=TINTA + (255,))
        logo = Image.new('RGBA', (W, 260), (0, 0, 0, 0)); dl = ImageDraw.Draw(logo); f = fuente(150)
        for dx, c in ((-9, (0, 240, 255, 255)), (9, (255, 40, 160, 255))):
            dl.text((W / 2 + dx, 130), 'TELE-DIMENSIONAL', font=f, fill=c, anchor='mm')
        dl.text((W / 2, 130), 'TELE-DIMENSIONAL', font=f, fill=(255, 255, 255, 255), anchor='mm')
        logo = logo.rotate(3.2, resample=Image.BICUBIC); c1.alpha_composite(logo, (0, 670))
        self.c1 = c1
        # capa 2: el lema
        c2 = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c2)
        for i, l in enumerate(('LA TELE QUE EMITE', 'DESDE OTROS UNIVERSOS')):
            d.text((W / 2, 1010 + i * 78), l, font=fuente(66), fill=p['ac2'] + (255,), anchor='mm', stroke_width=8, stroke_fill=TINTA + (255,))
        self.c2 = c2
        # capa 3: hoy, programa y título
        c3 = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c3)
        d.rounded_rectangle([90, 1190, W - 90, 1290], radius=26, fill=p['ac'] + (255,), outline=TINTA + (255,), width=7)
        t = f'HOY · {genero}'.upper(); ft = 52
        while d.textlength(t, font=fuente(ft)) > W - 240 and ft > 30:
            ft -= 2
        d.text((W / 2, 1240), t, font=fuente(ft), fill=TINTA + (255,), anchor='mm')
        d.text((W / 2, 1335), f'DESDE LA DIMENSIÓN {dimension}', font=fuente(40), fill=LUZ + (255,), anchor='mm', stroke_width=6, stroke_fill=TINTA + (255,))
        f = fuente(104); lineas, act = [], ''
        for w in titulo.upper().split():
            if d.textlength((act + ' ' + w).strip(), font=f) > 960 and act:
                lineas.append(act); act = w
            else:
                act = (act + ' ' + w).strip()
        lineas.append(act)
        for i, l in enumerate(lineas[:3]):
            d.text((W / 2, 1460 + i * 122), l, font=f, fill=LUZ + (255,), anchor='mm', stroke_width=11, stroke_fill=TINTA + (255,))
        self.c3 = c3

    def cuadro(self, t, t_lema, t_hoy):
        """Fotograma de la entradilla a los t segundos de empezar."""
        R = self.R
        r = self.rayos.rotate(t * 22, resample=Image.BILINEAR).crop((R - W // 2, R - 800 - 160, R + W // 2, R - 800 - 160 + H))
        im = r.convert('RGBA')

        def capa(c, t0, desde_abajo=False):
            if t < t0:
                return
            a = 1 - (1 - min((t - t0) / 0.22, 1)) ** 3
            if desde_abajo:
                im.alpha_composite(c, (0, int((1 - a) * 260))) if a < 1 else im.alpha_composite(c)
            else:
                k = 1.6 - 0.6 * a
                if k > 1.001:
                    cc = c.resize((int(W * k), int(H * k)), Image.BILINEAR)
                    im.alpha_composite(cc.crop((int((cc.size[0] - W) / 2), int((cc.size[1] - H) / 2) - int(800 * (k - 1)),
                                                int((cc.size[0] + W) / 2), int((cc.size[1] + H) / 2) - int(800 * (k - 1)))))
                else:
                    im.alpha_composite(c)
        capa(self.c1, 0.0)
        capa(self.c2, t_lema, True)
        capa(self.c3, t_hoy, True)
        return im.convert('RGB')


def sello(texto, color):
    """Palabra estampada en pantalla en los momentos gordos."""
    f = fuente(190); texto = texto.upper()[:14]
    tmp = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    an = int(tmp.textlength(texto, font=f)) + 80
    esc = min(1.0, 980 / an)
    im = Image.new('RGBA', (an, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((an / 2 + 8, 158), texto, font=f, fill=TINTA + (255,), anchor='mm', stroke_width=16, stroke_fill=TINTA + (255,))
    d.text((an / 2, 150), texto, font=f, fill=color + (255,), anchor='mm', stroke_width=14, stroke_fill=TINTA + (255,))
    if esc < 1:
        im = im.resize((int(an * esc), int(300 * esc)), Image.LANCZOS)
    return im.rotate(-7, resample=Image.BICUBIC, expand=True)


_VIN = None


def penumbra(im, color, fuerza):
    """Oscurece los bordes: rojo que late en las escenas de tensión, negro en los silencios."""
    global _VIN
    if _VIN is None:
        y, x = np.mgrid[0:H:4, 0:W:4]
        r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - 900) / (H / 2)) ** 2)
        _VIN = Image.fromarray(np.clip((r - 0.45) * 330, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    im.paste(color, (0, 0), _VIN.point(lambda v: int(v * fuerza)))


# ---------- personajes ----------
def personaje(dest, nombre, cx, tam, t, amp=0.0, emo='neutral', mira=(0, 0), habla=False, color=(255, 225, 77), fase=0.0,
              con_cara=False, salto=0.0):
    spr, fcx, fcy, fesc = sprite(nombre)
    k = 2; S = tam
    LW, LH = int(S * 2.1), int(S * 1.9)
    lay = Image.new('RGBA', (LW * k, LH * k), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    ox, oy = LW / 2, LH - S * 0.1
    P = lambda x, y: ((ox + x) * k, (oy + y) * k)
    resp = math.sin(t * 2.3 + fase)
    sy = 1 + 0.015 * resp + 0.09 * amp; sx = 1 - 0.01 * resp - 0.045 * amp
    jx = 0.0
    if emo == 'enfado' and habla:
        jx = math.sin(t * 61) * S * 0.012
    elif emo == 'miedo':
        jx = math.sin(t * 47 + fase) * S * 0.01
    bw, bh = S * sx, S * sy
    by1 = -S * 0.16; by0 = by1 - bh; bcy = (by0 + by1) / 2
    g = max(int(S * 0.045 * k), 2)
    # sombra en el suelo
    ds = ImageDraw.Draw(dest, 'RGBA')
    ds.ellipse([cx - S * 0.42, PIE - S * 0.07, cx + S * 0.42, PIE + S * 0.07], fill=(0, 0, 0, 95))
    # piernas y zapatos
    for s in (-1, 1):
        x1 = s * S * 0.17 + jx
        d.line([P(s * S * 0.12 + jx, by1 - S * 0.12), P(x1, -S * 0.03)], fill=TINTA, width=g)
        d.ellipse([*P(x1 + s * S * 0.05 - S * 0.11, -S * 0.085), *P(x1 + s * S * 0.05 + S * 0.11, S * 0.02)], fill=color, outline=TINTA, width=max(g // 2, 2))
    # brazos
    for s in (-1, 1):
        ang = (-0.55 + 0.6 * math.sin(t * 9 + s * 1.3) * (0.4 + amp)) if habla else (0.95 + 0.05 * resp)
        if emo == 'sorpresa':
            ang = -1.0
        elif emo == 'miedo':
            ang = -0.3 + 0.1 * math.sin(t * 40)
        hx, hy = s * bw * 0.22 + jx, bcy + S * 0.08
        mx, my = s * (bw * 0.5 + math.cos(ang) * S * 0.2) + jx, hy + math.sin(ang) * S * 0.3
        d.line([P(hx, hy), P(mx, my)], fill=TINTA, width=g)
        r = S * 0.058
        d.ellipse([*P(mx - r, my - r), *P(mx + r, my + r)], fill=(255, 255, 255), outline=TINTA, width=max(g // 2, 2))
    # cuerpo
    cuerpo = spr
    if con_cara and habla:
        cuerpo = spr.rotate(math.sin(t * 11) * 5 * (0.3 + amp), resample=Image.BILINEAR)
    cuerpo = cuerpo.resize((max(int(bw * k), 2), max(int(bh * k), 2)), Image.BILINEAR)
    lay.alpha_composite(cuerpo, (int((ox + jx - bw / 2) * k), int((oy + by0) * k)))
    # cara
    if not con_cara:
        fx, fy, fs = (fcx - 0.5) * bw + jx, by0 + fcy * bh, S * fesc
        er = fs * 0.115 * (1.25 if emo == 'sorpresa' else 1.0); ey = fy - fs * 0.07
        lw = max(int(fs * 0.022 * k), 2)
        cierra = ((t * 0.31 + fase) % 1) < 0.04
        for s in (-1, 1):
            ex = fx + s * fs * 0.17
            if emo == 'risa':
                d.arc([*P(ex - er, ey - er * 0.6), *P(ex + er, ey + er * 1.2)], 200, 340, fill=TINTA, width=lw * 2)
            elif cierra:
                d.line([P(ex - er, ey), P(ex + er, ey)], fill=TINTA, width=lw * 2)
            else:
                d.ellipse([*P(ex - er, ey - er), *P(ex + er, ey + er)], fill=(255, 255, 255), outline=TINTA, width=lw)
                pr = er * (0.3 if emo in ('sorpresa', 'miedo') else 0.46)
                px, py = ex + mira[0] * er * 0.42, ey + mira[1] * er * 0.42
                d.ellipse([*P(px - pr, py - pr), *P(px + pr, py + pr)], fill=TINTA)
                d.ellipse([*P(px - pr * 0.55, py - pr * 0.6), *P(px - pr * 0.05, py - pr * 0.1)], fill=(255, 255, 255))
            if emo == 'enfado':
                d.line([P(ex - s * er * 1.0, ey - er * 0.75), P(ex + s * er * 1.0, ey - er * 1.6)], fill=TINTA, width=lw * 3)
            elif emo in ('miedo', 'triste'):
                d.line([P(ex - s * er * 1.0, ey - er * 1.7), P(ex + s * er * 1.0, ey - er * 1.15)], fill=TINTA, width=lw * 2)
        my = fy + fs * 0.17; a = amp if habla else 0.0
        if emo == 'sorpresa' and not habla:
            a = 0.5
        if a > 0.07:
            rx, ry = fs * 0.10 * (1 + 0.35 * a), fs * (0.025 + 0.13 * a)
            d.ellipse([*P(fx - rx, my - ry), *P(fx + rx, my + ry)], fill=(74, 13, 33), outline=TINTA, width=lw)
            if a > 0.35:
                d.ellipse([*P(fx - rx * 0.6, my + ry * 0.1), *P(fx + rx * 0.6, my + ry * 0.85)], fill=(255, 107, 129))
        else:
            w = fs * 0.11
            if emo in ('enfado', 'miedo', 'triste'):
                d.arc([*P(fx - w, my - w * 0.1), *P(fx + w, my + w * 1.1)], 205, 335, fill=TINTA, width=lw * 2)
            else:
                d.arc([*P(fx - w, my - w * 0.9), *P(fx + w, my + w * 0.4)], 25, 155, fill=TINTA, width=lw * 2)
    lay = lay.resize((LW, LH), Image.BOX)
    dest.paste(lay, (int(cx - ox), int(PIE - oy - salto)), lay)


_RAYOS = {}


def prop(dest, nombre, p, t, edad):
    """El objeto de la escena, flotando en un destello giratorio."""
    if edad < 0:
        return
    pop = min(edad / 0.25, 1); pop = 1 - (1 - pop) ** 3
    clave = p['ac2']
    if clave not in _RAYOS:
        im = Image.new('RGBA', (1040, 1040), (0, 0, 0, 0)); L = Lienzo(im, 2)
        for i in range(0, 16, 2):
            a0, a1 = i / 16 * 2 * math.pi, (i + 1) / 16 * 2 * math.pi
            L.poly([(260, 260), (260 + math.cos(a0) * 258, 260 + math.sin(a0) * 258), (260 + math.cos(a1) * 258, 260 + math.sin(a1) * 258)],
                   p['ac2'] + (190,))
        L.elip(260, 260, 150, 150, fill=LUZ + (235,), borde=TINTA, w=7)
        _RAYOS[clave] = im.resize((520, 520), Image.LANCZOS)
    cy = 620 + math.sin(t * 2) * 12
    r = _RAYOS[clave].rotate(t * 40, resample=Image.BILINEAR)
    tam = int(520 * pop)
    if tam < 8:
        return
    r = r.resize((tam, tam), Image.BILINEAR)
    dest.paste(r, (int(W / 2 - tam / 2), int(cy - tam / 2)), r)
    s = sprite(nombre)[0].resize((int(230 * pop),) * 2, Image.BILINEAR)
    dest.paste(s, (int(W / 2 - s.size[0] / 2), int(cy - s.size[1] / 2)), s)


# ---------- rótulos ----------
def cabecera(p, dimension):
    im = Image.new('RGBA', (W, 170), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = fuente(96)
    for dx, c in ((-6, (0, 240, 255, 230)), (6, (255, 40, 160, 230))):
        d.text((W / 2 + dx, 4), 'TELE-DIMENSIONAL', font=f, fill=c, anchor='ma')
    d.text((W / 2, 4), 'TELE-DIMENSIONAL', font=f, fill=(255, 255, 255, 255), anchor='ma', stroke_width=3, stroke_fill=TINTA + (255,))
    d.text((W / 2, 118), f'CANAL NUTRIA ROJA  /  DIMENSIÓN {dimension}', font=fuente(36), fill=p['ac2'] + (255,), anchor='ma',
           stroke_width=4, stroke_fill=TINTA + (255,))
    return im   # se pega en (0, 96)


def faldon(texto, p):
    im = Image.new('RGBA', (W, 96), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(30, 8), (300, 8), (280, 88), (30, 88)], fill=(225, 30, 50, 255), outline=TINTA + (255,), width=5)
    d.ellipse([52, 34, 80, 62], fill=(255, 255, 255, 255))
    d.text((96, 46), 'EN DIRECTO', font=fuente(38), fill=(255, 255, 255, 255), anchor='lm')
    d.polygon([(296, 8), (1050, 8), (1050, 88), (276, 88)], fill=p['ac'] + (255,), outline=TINTA + (255,), width=5)
    t = 54; texto = texto.upper()
    while d.textlength(texto, font=fuente(t)) > 700 and t > 26:
        t -= 2
    d.text((668, 47), texto, font=fuente(t), fill=TINTA + (255,), anchor='mm')
    return im   # se pega en (x, 268)


_SUB = {}


def subtitulo(grupo, activa, nombre, color):
    clave = (tuple(grupo), activa, nombre)
    if clave in _SUB:
        return _SUB[clave]
    if len(_SUB) > 60:
        _SUB.clear()
    im = Image.new('RGBA', (W, 250), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if nombre:
        f = fuente(42); an = d.textlength(nombre.upper(), font=f)
        d.rounded_rectangle([W / 2 - an / 2 - 26, 6, W / 2 + an / 2 + 26, 70], radius=18, fill=color + (255,), outline=TINTA + (255,), width=5)
        d.text((W / 2, 38), nombre.upper(), font=f, fill=TINTA + (255,), anchor='mm')
    palabras = [w.upper() for w in grupo]
    tam = 92
    while True:
        f, fa = fuente(tam), fuente(tam * 1.1)
        anchos = [d.textlength(w, font=fa if i == activa else f) for i, w in enumerate(palabras)]
        esp = d.textlength(' ', font=f); total = sum(anchos) + esp * (len(palabras) - 1)
        if total <= W - 90 or tam <= 48:
            break
        tam -= 6
    x = (W - total) / 2
    for i, w in enumerate(palabras):
        d.text((x, 190), w, font=fa if i == activa else f, fill=(color if i == activa else (255, 255, 255)) + (255,), anchor='ls',
               stroke_width=9, stroke_fill=(0, 0, 0, 255))
        x += anchos[i] + esp
    _SUB[clave] = im
    return im   # se pega en (0, 1400)


# ---------- interferencias ----------
_MASC = None


def _mascara():
    global _MASC
    if _MASC is None:
        lin = np.ones(H); lin[::4] = 0.84; lin[1::4] = 0.93
        y, x = np.mgrid[0:H, 0:W]
        r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2) / 1.414
        _MASC = np.clip(lin[:, None] * (1 - 0.5 * r ** 3) * 256, 0, 256).astype(np.uint16)[:, :, None]
    return _MASC


def interferencia(arr, g, rng):
    """arr: HxWx3 uint8. g = fuerza del fallo de señal (0 = solo el aspecto de tele vieja)."""
    d = 2 + int(g * 22)
    arr[:, :, 0] = np.roll(arr[:, :, 0], d, axis=1)
    arr[:, :, 2] = np.roll(arr[:, :, 2], -d, axis=1)
    if g > 0.03:
        for _ in range(int(2 + g * 12)):
            y = int(rng.integers(0, H - 20)); h = int(rng.integers(6, 30 + int(g * 180)))
            arr[y:y + h] = np.roll(arr[y:y + h], int(rng.integers(-300, 300) * g), axis=1)
        if g > 0.25:
            ruido = np.repeat(np.repeat(rng.integers(0, 255, (H // 6 + 1, W // 6 + 1), dtype=np.uint8), 6, axis=0), 6, axis=1)[:H, :W, None]
            f = int(min(g, 1) * 150)
            arr[:] = ((arr.astype(np.uint16) * (256 - f) + ruido.astype(np.uint16) * f) >> 8).astype(np.uint8)
    return ((arr.astype(np.uint16) * _mascara()) >> 8).astype(np.uint8)


# ---------- vida del plató (cada fotograma) ----------
_VIDA = {}


def _cabeza_publico(rng, color, borde):
    k = 2; w, h = int(rng.uniform(150, 220)), int(rng.uniform(170, 240))
    im = Image.new('RGBA', ((w + 60) * k, (h + 90) * k), (0, 0, 0, 0)); L = Lienzo(im, k)
    cx, cy = (w + 60) / 2, h * 0.55 + 70
    L.elip(cx, cy + h * 0.6, w * 0.75, h * 0.4, fill=color)                     # hombros
    tipo = int(rng.integers(0, 5))
    if tipo == 1:                                                               # antenas
        for s in (-1, 1):
            L.linea([(cx + s * w * 0.15, cy - h * 0.3), (cx + s * w * 0.3, cy - h * 0.62)], color, 6)
            L.elip(cx + s * w * 0.3, cy - h * 0.62, 9, 9, fill=borde)
    elif tipo == 2:                                                             # tupé
        L.elip(cx + w * 0.1, cy - h * 0.38, w * 0.35, h * 0.16, fill=color)
    elif tipo == 3:                                                             # cuernecillos
        for s in (-1, 1):
            L.poly([(cx + s * w * 0.18, cy - h * 0.3), (cx + s * w * 0.32, cy - h * 0.3), (cx + s * w * 0.32, cy - h * 0.6)], color)
    L.elip(cx, cy, w / 2, h / 2 * (1.1 if tipo == 4 else 1), fill=color)
    L.d.arc([(cx - w / 2) * k, (cy - h / 2) * k, (cx + w / 2) * k, (cy + h / 2) * k], 200, 300, fill=borde, width=4 * k)
    return im.resize((w + 60, h + 90), Image.LANCZOS)


def vida(esc, t, p, semilla, abierto):
    """Bombillas que parpadean y, si se ve el cielo, algo que cruza flotando."""
    d = ImageDraw.Draw(esc)
    for i, y in enumerate(range(420, 1100, 56)):
        for x in (16, W - 16):
            on = (int(t * 5) + i + (x > 500)) % 3 != 0
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=p['ac2'] if on else osc(p['ac2'], 0.35), outline=TINTA, width=3)
    if abierto:
        clave = ('flota', semilla % 7)
        if clave not in _VIDA:
            nombre = ['ovni', 'cohete', 'planeta', 'ballena', 'pez', 'nube', 'cometa'][semilla % 7]
            _VIDA[clave] = sprite(nombre)[0].resize((130, 130), Image.LANCZOS)
        s = _VIDA[clave]
        ciclo = 16.0
        a = (t + semilla % 9) % ciclo / ciclo
        x = int(-150 + a * (W + 300)); y = int(470 + math.sin(t * 1.3) * 40)
        esc.paste(s, (x, y), s)


def publico(im, t, p, semilla, bote=0.0):
    """Cabezas del público en primer plano, abajo, como en un plató de verdad."""
    clave = ('publico', semilla)
    if clave not in _VIDA:
        rng = np.random.default_rng(semilla)
        cols = [osc(p['a'], 0.55), osc(p['s2'], 0.7), (24, 14, 34)]
        cab = []
        x = -40
        while x < W + 40:
            c = cols[int(rng.integers(0, 3))]
            cab.append((x, rng.uniform(0, 6.28), _cabeza_publico(rng, c, p['ac'])))
            x += rng.uniform(150, 210)
        _VIDA[clave] = cab
    for x, fase, s in _VIDA[clave]:
        dy = math.sin(t * 2.2 + fase) * 4 - bote * abs(math.sin(t * 18 + fase)) * 40
        im.paste(s, (int(x - s.size[0] / 2), int(H - s.size[1] * 0.5 + dy)), s)

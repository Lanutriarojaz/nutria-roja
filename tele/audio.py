"""Voces (edge-tts, una por personaje), efectos de sonido y sintonía sintetizados con numpy, y mezcla final."""
import asyncio
import os
import subprocess
import wave

import edge_tts
import numpy as np

from .catalogo import VOCES

SR = 44100


# ---------- voces ----------
async def _tts(texto, voz, rate, pitch, mp3):
    c = edge_tts.Communicate(texto, voz, rate=rate, pitch=pitch, boundary='WordBoundary')
    palabras = []
    with open(mp3, 'wb') as f:
        async for ch in c.stream():
            if ch['type'] == 'audio':
                f.write(ch['data'])
            elif ch['type'] == 'WordBoundary':
                palabras.append([ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7, ch['text']])
    return palabras


def _mas_rapido(rate, extra):
    return f'{int(rate.rstrip("%")) + extra:+d}%'


def decir(texto, preset, carpeta, k, extra=0):
    """Devuelve (audio float32 mono, [[t0, t1, palabra], ...]) ya sin silencios al principio ni al final."""
    voz, rate, pitch, _ = VOCES.get(preset, VOCES['locutor'])
    mp3 = os.path.join(carpeta, f'voz{k:02d}.mp3')
    for i in range(5):
        try:
            palabras = asyncio.run(_tts(texto, voz, _mas_rapido(rate, extra), pitch, mp3))
            if palabras and os.path.getsize(mp3) > 1000:
                break
        except Exception:
            pass
        if i == 4:
            raise RuntimeError(f'La voz no responde para «{texto[:40]}»')
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, dtype=np.float32).copy()
    fuerte = np.flatnonzero(np.abs(x) > 0.012)
    if len(fuerte) == 0:
        raise RuntimeError('La voz ha llegado vacía')
    a, b = max(fuerte[0] - int(0.03 * SR), 0), min(fuerte[-1] + int(0.08 * SR), len(x))
    x = x[a:b]
    x *= 0.14 / (np.sqrt(np.mean(x ** 2)) + 1e-9)          # mismo volumen para todas las voces
    np.clip(x, -0.98, 0.98, out=x)
    d = a / SR
    palabras = [[max(p[0] - d, 0), min(max(p[1] - d, 0.05), len(x) / SR), p[2]] for p in palabras]
    return x, palabras


# ---------- efectos ----------
def _env(n, ataque=0.005, caida=4.0):
    t = np.arange(n) / SR
    return np.minimum(t / ataque, 1) * np.exp(-caida * t)


def _tono(f, d, forma='sin'):
    t = np.arange(int(d * SR)) / SR
    fase = 2 * np.pi * np.cumsum(np.broadcast_to(f, t.shape)) / SR
    s = np.sin(fase)
    return np.sign(s) * 0.5 if forma == 'cuad' else (2 / np.pi * np.arcsin(s) if forma == 'tri' else s)


def _suave(x, n):
    return np.convolve(x, np.ones(n) / n, mode='same')


def efecto(nombre, rng):
    r = rng.standard_normal
    if nombre == 'estatica':
        n = int(0.42 * SR); return _suave(r(n), 3) * np.linspace(1, 0, n) ** 0.6 * 0.5
    if nombre == 'ding':
        n = int(0.9 * SR); return (_tono(1318.5, 0.9) + 0.6 * _tono(1976, 0.9)) * _env(n, caida=5) * 0.5
    if nombre == 'error':
        n = int(0.55 * SR); return _tono(98, 0.55, 'cuad') * np.minimum(1, (n - np.arange(n)) / 2000) * 0.7
    if nombre == 'whoosh':
        n = int(0.6 * SR); e = np.sin(np.linspace(0, np.pi, n)) ** 2
        return (_suave(r(n), 40) * 6 + _suave(r(n), 8)) * e * 0.5
    if nombre == 'mazo':
        g = _tono(np.linspace(190, 70, int(0.16 * SR)), 0.16) * _env(int(0.16 * SR), caida=22)
        return np.concatenate([g, np.zeros(int(0.12 * SR)), g, np.zeros(int(0.1 * SR)), g * 1.2])
    if nombre == 'redoble':
        n = int(1.1 * SR); x = np.zeros(n); t = 0.0; paso = 0.07
        while t < 1.0:
            i = int(t * SR); m = min(int(0.05 * SR), n - i)
            x[i:i + m] += r(m) * _env(m, caida=60) * (0.4 + 0.6 * t)
            t += paso; paso = max(paso * 0.93, 0.022)
        return np.concatenate([x * 0.6, (_suave(r(int(0.5 * SR)), 2) * _env(int(0.5 * SR), caida=7)) * 0.7])
    if nombre == 'aplausos':
        n = int(1.4 * SR); x = np.zeros(n)
        for i in rng.integers(0, n - 900, 260):
            x[i:i + 800] += _suave(r(800), 4) * _env(800, caida=90)
        return x * np.sin(np.linspace(0, np.pi, n)) ** 0.7 * 0.45
    if nombre == 'murmullo':
        n = int(1.2 * SR); return _suave(r(n), 60) * 9 * (0.6 + 0.4 * np.sin(np.arange(n) / SR * 37)) * np.sin(np.linspace(0, np.pi, n)) * 0.6
    if nombre == 'alarma':
        return np.concatenate([_tono(f, 0.16, 'cuad') for f in (880, 660, 880, 660)]) * 0.45
    if nombre == 'laser':
        n = int(0.4 * SR); return _tono(np.linspace(1800, 200, n), 0.4, 'tri') * _env(n, caida=5) * 0.6
    if nombre == 'latido':
        g = _tono(np.linspace(90, 45, int(0.14 * SR)), 0.14) * _env(int(0.14 * SR), caida=18)
        return np.concatenate([g, np.zeros(int(0.1 * SR)), g * 0.7, np.zeros(int(0.35 * SR)), g, np.zeros(int(0.1 * SR)), g * 0.7]) * 1.3
    if nombre == 'caja':
        n = int(0.7 * SR); return np.concatenate([_tono(2093, 0.09), _tono(2637, 0.7)[:n]]) * _env(n + int(0.09 * SR), caida=6) * 0.45
    if nombre == 'golpe':        # mazazo dramático: bombo grave + acorde disonante + ruido
        n = int(0.9 * SR)
        bombo = _tono(np.linspace(110, 34, n), 0.9) * _env(n, caida=5) * 1.2
        acorde = sum(_tono(f, 0.9, 'cuad') for f in (146.8, 155.6, 220, 311.1)) * _env(n, caida=4) * 0.22
        return bombo + acorde + _suave(r(n), 3) * _env(n, caida=18) * 0.5
    if nombre == 'subida':       # tensión que sube antes del giro
        n = int(1.3 * SR); e = np.linspace(0, 1, n) ** 2
        return (_tono(np.linspace(180, 1500, n), 1.3, 'tri') * 0.35 + _suave(r(n), 6) * 0.5) * e
    if nombre == 'cortinilla':   # la sintonía del canal: siempre la misma
        notas = [0, 4, 7, 12, 16]; paso = 0.105
        x = np.zeros(int(1.25 * SR))
        for i, st in enumerate(notas):
            f = 329.63 * 2 ** (st / 12); d = 0.75 if i == 4 else 0.2; m = int(d * SR)
            poner(x, (_tono(f, d, 'cuad') * 0.5 + _tono(f / 2, d, 'tri')) * _env(m, caida=3 if i == 4 else 9), i * paso)
        final = sum(_tono(329.63 * 2 ** (st / 12), 0.7) for st in (0, 4, 7)) * _env(int(0.7 * SR), caida=3) * 0.3
        poner(x, final, 4 * paso)
        w = int(0.45 * SR); poner(x, _suave(r(w), 30) * 5 * np.sin(np.linspace(0, np.pi, w)) ** 2 * 0.35, 0)
        return x * 0.6
    if nombre == 'apagado':
        n = int(0.5 * SR); return _tono(np.linspace(9000, 60, n), 0.5) * _env(n, caida=9) * 0.35
    return np.zeros(1)


EFECTOS = ['ding', 'error', 'whoosh', 'mazo', 'redoble', 'aplausos', 'murmullo', 'alarma', 'laser', 'latido', 'caja']


# ---------- sintonía ----------
def musica(dur, rng, tramos=()):
    """Banda sonora generada. tramos = [(t0, t1, modo)], con modo:
    normal (arpegio de fondo), tension (pulso grave que aprieta), silencio (solo un zumbido), triunfo (arpegio luminoso)."""
    bpm = int(rng.integers(100, 124)); paso = 60 / bpm / 2
    raiz = 110 * 2 ** (int(rng.integers(0, 8)) / 12)
    progres = [[0, 8, 3, 10], [0, 5, 8, 7], [0, 3, 10, 5], [0, 10, 8, 7], [0, 7, 8, 5]][int(rng.integers(0, 5))]
    patron = [[0, 2, 1, 2, 3, 2, 1, 2], [0, 1, 2, 3, 2, 1, 0, 3], [0, 3, 2, 3, 1, 3, 2, 3]][int(rng.integers(0, 3))]
    n = int((dur + 2) * SR); x = np.zeros(n)

    def modo(t):
        for a, b, m in tramos:
            if a <= t < b:
                return m, (t - a) / max(b - a, 0.1)
        return 'normal', 0.0

    k = 0; t = 0.0
    while t < dur + 1:
        m, av = modo(t)
        grado = progres[(k // 8) % 4]
        i = int(t * SR)
        if m == 'mudo':
            pass
        elif m == 'silencio':
            mm = min(int(paso * SR) + 200, n - i)
            x[i:i + mm] += _tono(raiz / 2, paso + 0.01)[:mm] * 0.10
        elif m == 'tension':
            mm = min(int(paso * 0.9 * SR), n - i)                       # pulso grave en corcheas, cada vez más fuerte
            x[i:i + mm] += _tono(raiz / 2, paso * 0.9, 'tri')[:mm] * _env(mm, 0.004, 9) * (0.9 + 0.7 * av)
            if k % 2 == 0:                                              # latigazo agudo disonante que va subiendo
                f = raiz * 4 * 2 ** ((1 + int(av * 5)) / 12); m2 = min(int(paso * 1.8 * SR), n - i)
                x[i:i + m2] += _tono(f, paso * 1.8, 'cuad')[:m2] * _env(m2, 0.02, 5) * (0.07 + 0.12 * av)
            m3 = min(1500, n - i); x[i:i + m3] += rng.standard_normal(m3) * _env(m3, caida=160) * (0.08 + 0.1 * av)
        else:
            mayor = m == 'triunfo'
            menor = (grado in (0, 5, 7)) and not mayor
            acorde = [0, 3 if menor else 4, 7, 12]
            f = raiz * 2 ** ((grado + acorde[patron[k % 8]]) / 12) * (2 if mayor else 1)
            mm = min(int(paso * 1.6 * SR), n - i)
            x[i:i + mm] += _tono(f * 2, paso * 1.6, 'cuad')[:mm] * _env(mm, caida=7) * 0.28
            if k % 4 == 0:
                m2 = min(int(paso * 3.6 * SR), n - i)
                x[i:i + m2] += _tono(raiz / 2 * 2 ** (grado / 12), paso * 3.6, 'tri')[:m2] * _env(m2, 0.01, 2.2) * 0.8
            if k % 2 == 1:
                m3 = min(1800, n - i); x[i:i + m3] += rng.standard_normal(m3) * _env(m3, caida=140) * 0.10
        k += 1; t += paso
    return _suave(x, 5)


# ---------- mezcla ----------
def escribir_wav(x, ruta):
    x = np.tanh(x * 1.5) / np.tanh(1.5)
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.95
    pcm = (np.repeat(x[:, None], 2, axis=1) * 32767).astype('<i2')
    with wave.open(ruta, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def poner(pista, x, t, g=1.0):
    i = int(t * SR)
    if i >= len(pista):
        return
    m = min(len(x), len(pista) - i)
    pista[i:i + m] += x[:m] * g


def envolvente(voz, fps, nframes):
    """Volumen de la voz por fotograma (0..1), para mover las bocas."""
    paso = SR // fps
    e = np.zeros(nframes)
    for f in range(nframes):
        seg = voz[f * paso:(f + 1) * paso]
        if len(seg):
            e[f] = np.sqrt(np.mean(seg ** 2))
    e = np.clip(e / 0.16, 0, 1) ** 0.7
    return np.maximum(e, np.concatenate([[0], e[:-1]]) * 0.55)   # la boca cierra con un poco de retardo

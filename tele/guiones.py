"""Guiones completos escritos por ChatGPT (atajo del iPhone, uno por idea). El motor los usa antes que las ideas sueltas.
Uso: python -m tele.guiones guardar < respuesta      |      python -m tele.guiones pendientes"""
import datetime as dt
import glob
import json
import os
import sys

from .ideas import _json

AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(AQUI, 'guiones')
USADOS = os.path.join(CARPETA, 'usados.json')


def guardar(texto, fuente='chatgpt'):
    g = _json(texto)
    g = g.get('guion', g) if isinstance(g, dict) else g
    if not isinstance(g, dict) or not g.get('escenas') or not g.get('personajes'):
        raise ValueError('La respuesta no es un guion (faltan escenas o personajes)')
    lineas = sum(len(e.get('lineas') or []) for e in g['escenas'])
    if lineas < 8:
        raise ValueError(f'Guion demasiado corto: {lineas} líneas')
    os.makedirs(CARPETA, exist_ok=True)
    hoy = dt.date.today().isoformat(); n = 1
    while os.path.exists(os.path.join(CARPETA, f'{hoy}-{fuente}-{n}.json')):
        n += 1
    ruta = os.path.join(CARPETA, f'{hoy}-{fuente}-{n}.json')
    json.dump({'fuente': fuente, 'fecha': hoy, 'guion': g}, open(ruta, 'w'), ensure_ascii=False, indent=1)
    return ruta, g.get('titulo', '')


def _usados():
    try:
        return set(json.load(open(USADOS)))
    except (OSError, ValueError):
        return set()


def pendientes():
    u = _usados()
    return [dict(json.load(open(r)), clave=os.path.basename(r)) for r in sorted(glob.glob(os.path.join(CARPETA, '20*.json')))
            if os.path.basename(r) not in u]


def gastar(clave):
    u = _usados(); u.add(clave); os.makedirs(CARPETA, exist_ok=True)
    json.dump(sorted(u), open(USADOS, 'w'), ensure_ascii=False, indent=0)


if __name__ == '__main__':
    if sys.argv[1:2] == ['guardar']:
        ruta, titulo = guardar(sys.stdin.read(), (sys.argv[2:3] or ['chatgpt'])[0])
        print(f'✔ Guion «{titulo}» guardado en {os.path.relpath(ruta)}')
    else:
        p = pendientes(); print(len(p)); [print(' -', x['guion'].get('titulo')) for x in p]

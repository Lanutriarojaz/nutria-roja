"""Descarga los dibujos (Twemoji, CC-BY 4.0) y los guarda como PNG en assets/tele/. Solo hace falta al ampliar el catálogo.
Uso: pip install resvg_py && python -m tele.preparar"""
import os
import requests
import resvg_py

from .catalogo import ELEMENTOS, ATREZO

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'tele')
BASE = 'https://cdn.jsdelivr.net/gh/jdecked/twemoji@16.0.1/assets/svg/{}.svg'


def main():
    os.makedirs(DEST, exist_ok=True)
    todo = {k: v[1] for k, v in ELEMENTOS.items()} | ATREZO
    faltan = []
    for k, cod in todo.items():
        ruta = os.path.join(DEST, f'{k}.png')
        if os.path.exists(ruta):
            continue
        r = requests.get(BASE.format(cod), timeout=30)
        if r.status_code != 200:
            faltan.append(f'{k} ({cod}): {r.status_code}'); continue
        open(ruta, 'wb').write(bytes(resvg_py.svg_to_bytes(svg_string=r.text, width=512, height=512)))
    print(f'{len(todo) - len(faltan)}/{len(todo)} dibujos listos')
    if faltan:
        print('FALTAN:', ', '.join(faltan)); raise SystemExit(1)


if __name__ == '__main__':
    main()

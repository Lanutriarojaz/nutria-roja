"""Espera a que GitHub Pages sirva TODOS los vídeos de la tirada antes de dárselos a Buffer.
(Antes solo se esperaba al primero y Buffer rechazaba el resto con «Video could not be read from its URL».)
Uso: python -m nutria.esperar salida/tirada.json https://usuario.github.io/repo [minutos]"""
import json
import sys
import time

import requests


def listo(url):
    try:
        r = requests.head(url, timeout=20, allow_redirects=True)
        return r.status_code == 200 and int(r.headers.get('content-length', 0)) > 100000
    except (requests.RequestException, ValueError):
        return False


def main():
    tirada, base = sys.argv[1], sys.argv[2].rstrip('/')
    limite = float(sys.argv[3]) if len(sys.argv) > 3 else 15
    todos = [f"{base}/{v.get('archivo') or v['fecha']}.mp4" for v in json.load(open(tirada)) if v.get('ok')]
    pendientes, t0 = list(todos), time.time()
    while pendientes and time.time() - t0 < limite * 60:
        pendientes = [u for u in pendientes if not listo(u)]
        if pendientes:
            print(f'  faltan por servirse {len(pendientes)} vídeos…', flush=True); time.sleep(15)
    if pendientes:
        print('::error::GitHub Pages no sirve: ' + ', '.join(u.rsplit('/', 1)[-1] for u in pendientes)); sys.exit(1)
    time.sleep(20)                                  # margen para que la caché llegue a todos los servidores
    print(f'Pages sirve los {len(todos)} vídeos')


if __name__ == '__main__':
    main()

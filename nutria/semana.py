"""Genera la tirada de vídeos: python -m nutria.semana --desde 2026-11-11 --dias 6"""
import argparse
import datetime as dt
import json
import os
import random
import shutil
import traceback

from . import calidad, fuentes, guion, video

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def elegir_imagenes(hecho, g, carpeta, n=5):
    vistas, cands = set(), []
    for art in hecho['articulos']:
        for im in fuentes.imagenes_articulo(art):
            if im['titulo'] not in vistas:
                vistas.add(im['titulo']); cands.append((0, im))
    for i, q in enumerate(g.get('busquedas', [])[:3]):
        for im in fuentes.buscar_commons(q, 4):
            if im['titulo'] not in vistas:
                vistas.add(im['titulo']); cands.append((1 + i, im))
    # fotos grandes y apaisadas o cuadradas primero; las del artículo, antes que las de la búsqueda
    cands = [(p, im) for p, im in cands if im['ancho'] >= 500 and im['alto'] >= 350]
    cands.sort(key=lambda x: (x[0], -min(x[1]['ancho'], 1600) * min(x[1]['alto'], 1600)))
    elegidas, rutas = [], []
    for _, im in cands:
        if len(rutas) >= n:
            break
        ext = '.png' if im['url'].lower().split('?')[0].endswith('.png') else '.jpg'
        ruta = os.path.join(carpeta, f'img{len(rutas)}{ext}')
        try:
            fuentes.descargar(im['url'], ruta)
            video._tam(ruta)  # comprueba que ffmpeg la lee
            rutas.append(ruta); elegidas.append(im)
        except Exception:
            continue
    return rutas, elegidas


def un_dia(fecha, carpeta, usados):
    d, m = fecha.day, fecha.month
    candidatos = fuentes.efemerides(m, d)
    if not candidatos:
        raise RuntimeError('Wikipedia no tiene efemérides para ese día')
    errores = []
    for hecho in guion.elegir(candidatos, d, m, usados) + candidatos[:5]:
        if hecho['articulos'][0] in usados:
            continue
        try:
            fuente = (hecho.get('resumen') or '') + '\n\n' + fuentes.articulo(hecho['articulos'][0])
            g = None
            for intento in range(3):
                try:
                    g = guion.escribir(hecho, fuente, d, m)
                except ValueError as e:
                    errores.append(f"guion: {e}"); continue
                ok, malos = guion.verificar(g, fuente, hecho)
                if ok:
                    break
                errores.append(f"datos no respaldados: {malos[:2]}"); g = None
            if not g:
                continue
            os.makedirs(carpeta, exist_ok=True)
            rutas, imgs = elegir_imagenes(hecho, g, carpeta)
            if len(rutas) < 2:
                errores.append(f"pocas fotos para «{hecho['articulos'][0]}»"); continue
            frases = [g['gancho'], *g['frases'], g['pregunta']]
            texto = ' '.join(frases)
            salida = os.path.join(carpeta, 'video.mp4')
            fecha_txt = f"{d} de {guion.MESES[m - 1]} de {hecho['año']}"
            for intento in range(2):
                video.montar(rutas, texto, [len(f.split()) for f in frases], fecha_txt, carpeta, salida,
                             semilla=fecha.toordinal())
                fallos, medidas = calidad.revisar(salida)
                if not fallos:
                    break
                errores.append(f"calidad: {fallos}")
            if fallos:
                continue
            creditos = '; '.join(f"{i['autor']} ({i['licencia']})" for i in imgs)
            info = {'fecha': fecha.isoformat(), 'año': hecho['año'], 'hecho': hecho['texto'],
                    'articulo': hecho['articulos'][0], 'titulo': g['titulo'],
                    'descripcion': g['descripcion'] + f"\n\nFotos: Wikimedia Commons — {creditos}",
                    'guion': frases, 'imagenes': [i['titulo'] for i in imgs], 'calidad': medidas}
            json.dump(info, open(os.path.join(carpeta, 'info.json'), 'w'), ensure_ascii=False, indent=2)
            return info
        except Exception as e:
            errores.append(f"{hecho['articulos'][0]}: {e!r}")
    raise RuntimeError('Ningún hecho salió bien: ' + ' | '.join(errores[-6:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--desde', help='primer día (AAAA-MM-DD); por omisión, hoy')
    ap.add_argument('--dias', type=int, default=7)
    ap.add_argument('--salida', default=os.path.join(RAIZ, 'salida'))
    a = ap.parse_args()
    inicio = dt.date.fromisoformat(a.desde) if a.desde else dt.date.today()
    shutil.rmtree(a.salida, ignore_errors=True); os.makedirs(a.salida)
    tirada, usados = [], []
    for k in range(a.dias):
        f = inicio + dt.timedelta(days=k)
        print(f'▶ {f}', flush=True)
        try:
            info = un_dia(f, os.path.join(a.salida, f.isoformat()), usados)
            usados.append(info['articulo'])
            tirada.append({**info, 'ok': True})
            print(f"  ✔ {info['titulo']}  ({info['calidad']['duracion']} s)", flush=True)
        except Exception as e:
            traceback.print_exc()
            tirada.append({'fecha': f.isoformat(), 'ok': False, 'error': str(e)[:500]})
            print(f'  ✖ {e}', flush=True)
    json.dump(tirada, open(os.path.join(a.salida, 'tirada.json'), 'w'), ensure_ascii=False, indent=2)
    bien = sum(t['ok'] for t in tirada)
    print(f'Hechos {bien}/{len(tirada)}')
    if bien == 0:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

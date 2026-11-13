"""Genera la tirada de vídeos: python -m nutria.semana --desde 2026-11-11 --dias 6"""
import argparse
import datetime as dt
import json
import os
import random
import shutil
import traceback

from . import calidad, encargos, fuentes, guion, video

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _candidatas(hecho, g):
    """Fotos candidatas: las del artículo, las de las búsquedas de ChatGPT y las que propone Gemini."""
    vistas, cands = set(), []

    def add(im, prio):
        if im['titulo'] not in vistas and im['ancho'] >= 500 and im['alto'] >= 350:
            vistas.add(im['titulo']); cands.append((prio, im))

    for art in hecho.get('articulos') or []:
        try:
            for im in fuentes.imagenes_articulo(art):
                add(im, 0)
        except Exception as e:
            print(f'  (sin fotos del artículo «{art}»: {str(e)[:80]})', flush=True)
    consultas = list(g.get('busquedas', []))[:3]
    try:   # Gemini: búsquedas propias, más variadas y concretas que las del guion
        r = guion.llm([
            {'role': 'system', 'content': 'Eres documentalista gráfico de un canal de historia en vídeos cortos. Responde solo JSON.'},
            {'role': 'user', 'content': f"Tema: {g.get('titulo')}\nHecho ({hecho.get('año')}): {hecho.get('texto')}\nGuion: {' '.join(g.get('frases', []))}\n\n"
                                       'Propón 5 búsquedas EN INGLÉS para Wikimedia Commons que den fotos reales, nítidas y variadas '
                                       '(personas, lugares, objetos, época; no mapas ni logos). Responde {"busquedas":["..."]}.'}],
            temperatura=0.4, rol='elegir')
        consultas += [q for q in r.get('busquedas', []) if isinstance(q, str)][:5]
    except Exception as e:
        print(f'  Gemini no propone búsquedas: {str(e)[:100]}', flush=True)
    for i, q in enumerate(dict.fromkeys(consultas)):
        try:
            for im in fuentes.buscar_commons(q, 4):
                add(im, 1 + i)
        except Exception as e:
            print(f'  (búsqueda «{q}» falla: {str(e)[:60]})', flush=True)
    cands.sort(key=lambda x: (x[0], -min(x[1]['ancho'], 1600) * min(x[1]['alto'], 1600)))
    return [im for _, im in cands]


def _ordenar_con_gemini(cands, hecho, g, n):
    """Gemini mira los títulos de archivo y elige las n fotos que mejor cuentan el hecho. Si falla, orden por defecto."""
    if len(cands) <= n:
        return cands
    lista = '\n'.join(f"{i}: {im['titulo']}" for i, im in enumerate(cands[:40]))
    try:
        r = guion.llm([
            {'role': 'system', 'content': 'Eres editor gráfico de un canal de historia en vídeos cortos. Responde solo JSON.'},
            {'role': 'user', 'content': f"Hecho ({hecho.get('año')}): {hecho.get('texto')}\nGuion: {' '.join(g.get('frases', []))}\n\nArchivos disponibles:\n{lista}\n\n"
                                       f'Elige las {n} que mejor ilustran el relato, en el orden en que deben salir y sin repetir plano. '
                                       'Descarta lo que no pinte nada (escudos, mapas, fotos de otra cosa). Responde {"ids":[...]}.'}],
            temperatura=0.2, rol='elegir')
        ids = [int(i) for i in r.get('ids', []) if str(i).isdigit() and int(i) < len(cands[:40])]
        ids = list(dict.fromkeys(ids))
        elegidas = [cands[i] for i in ids]
        resto = [im for im in cands if im not in elegidas]
        return elegidas + resto
    except Exception as e:
        print(f'  Gemini no elige fotos: {str(e)[:100]}', flush=True)
        return cands


def elegir_imagenes(hecho, g, carpeta, n=5):
    cands = _ordenar_con_gemini(_candidatas(hecho, g), hecho, g, n)
    elegidas, rutas = [], []
    for im in cands:
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


def _art(hecho):
    return (hecho.get('articulos') or [hecho.get('texto', '')[:60]])[0]


def un_dia(fecha, carpeta, usados):
    d, m = fecha.day, fecha.month
    candidatos = fuentes.efemerides(m, d)
    if not candidatos:
        raise RuntimeError('Wikipedia no tiene efemérides para ese día')
    errores = []
    chatgpt = None                                   # guion de ChatGPT (atajo del domingo): él elige el hecho y manda; solo se mira el formato
    try:
        prev = encargos.de_chatgpt(fecha.isoformat())
        if prev and _art(prev[0]) not in usados:
            guion.validar(prev[2], prev[0], d, guion.MESES[m - 1])
            chatgpt = prev; print(f"  guion de ChatGPT: «{prev[2].get('titulo')}»", flush=True)
    except Exception as e:
        errores.append(f'ChatGPT no válido: {e}'); print('  guion de ChatGPT no válido:', str(e)[:120], flush=True)
    orden = ([chatgpt[0]] if chatgpt else []) + guion.elegir(candidatos, d, m, usados) + candidatos[:5]
    for hecho in orden:
        if _art(hecho) in usados or (chatgpt and hecho is not chatgpt[0] and _art(hecho) == _art(chatgpt[0])):
            continue
        try:
            if chatgpt and hecho is chatgpt[0]:
                fuente, g = chatgpt[1], chatgpt[2]
            else:
                fuente = (hecho.get('resumen') or '') + '\n\n' + fuentes.articulo(hecho['articulos'][0])
                g = None
            for intento in range(0 if g else 3):
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
                errores.append(f"pocas fotos para «{_art(hecho)}»"); continue
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
                    'articulo': _art(hecho), 'titulo': g['titulo'],
                    'descripcion': g['descripcion'] + f"\n\nFotos: Wikimedia Commons — {creditos}",
                    'guion': frases, 'imagenes': [i['titulo'] for i in imgs], 'calidad': medidas}
            json.dump(info, open(os.path.join(carpeta, 'info.json'), 'w'), ensure_ascii=False, indent=2)
            return info
        except Exception as e:
            errores.append(f"{_art(hecho)}: {e!r}")
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

"""Genera la tirada de vídeos: python -m nutria.semana --desde 2026-11-11 --dias 6"""
import argparse
import base64
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


def _miniatura_b64(ruta):
    out = ruta + '.v.jpg'
    video.sh(['ffmpeg', '-v', 'error', '-y', '-i', ruta, '-vf', 'scale=640:640:force_original_aspect_ratio=decrease',
              '-frames:v', '1', out])
    return base64.b64encode(open(out, 'rb').read()).decode()


REVISION = """Eres el documentalista gráfico de un canal de historia que presume de rigor: una foto equivocada nos hace perder la credibilidad.
Decide qué fotos pueden ilustrar este vídeo SIN ERRAR en nada.
HECHO ({año}): {hecho}
SUJETO (lo que debe verse): {sujeto}
DETALLES QUE NO PUEDEN FALLAR (país, bando, época, modelo, lugar, persona): {detalles}
GUION: {guion}

De cada imagen te doy el nombre de archivo y la descripción de Wikimedia. Responde por cada una:
- "si": muestra el sujeto MISMO, o su lugar, su objeto o a sus protagonistas, y NADA contradice los detalles.
  El contexto cultural o de época NO basta (un grabado antiguo "del mismo estilo", un edificio del mismo país, ropa o merchandising con un logo): eso es "no".
  Si el sujeto es una persona, vale cualquier foto SUYA identificada por el pie de foto, de cualquier época, mientras el pie no
  la ligue a un hecho que contradiga el relato (no valen su casa, un museo, ni otra persona aunque sea del mismo oficio).
- "no" TAMBIÉN para cualquier imagen gráficamente violenta o perturbadora (cadáveres, fosas comunes, heridas, desnudos):
  las redes la penalizan y no es el tono del canal. Una foto de época que muestre un lugar o a personas sin escenas crudas sí vale.
- "no": muestra otra cosa; o lo mismo pero de otro país, bando, época, modelo o persona (p. ej. una nave soviética cuando el hecho es de una nave de EE. UU.);
  o algo genérico que podría ser de cualquier sitio (un ring de boxeo cualquiera, un cohete cualquiera); o un mapa, logo o texto.
- "dudoso": no puedes asegurarlo.
Reglas: no identifiques a nadie por la cara; para personas fíate del pie de foto y de que la imagen sea coherente con él.
Si la descripción dice una cosa y la imagen otra, es "no". Ante la duda, "dudoso".
Responde {{"fotos":[{{"id":N,"veredicto":"si|no|dudoso","muestra":"lo que se ve, en 8-15 palabras, en español","motivo":"breve"}}]}}"""

ASIGNACION = """Para cada frase de este vídeo elige UNA de las fotos aprobadas (por su id). Puedes repetir fotos.
Reglas:
- La foto debe ilustrar el SIGNIFICADO de la frase, nunca una palabra suelta. Si habla de crisis o de hambre, no pongas a alguien comiendo; si dice «cohete», no pongas un cohete cualquiera.
- Si ninguna foto encaja con lo que dice la frase, usa la más neutra del sujeto principal. Jamás una que muestre algo distinto o contradictorio.
- No repitas la misma foto más de 2 frases seguidas.
SUJETO: {sujeto}
FOTOS APROBADAS:
{fotos}
FRASES:
{frases}
Responde {{"asignacion":[id, id, ...]}} con exactamente {n} ids, uno por frase y en orden."""


def _revisar_fotos(cands, hecho, g, sujeto, detalles):
    """cands: [{'im':..., 'ruta':...}]. Gemini MIRA cada foto (con su pie de Commons) y aprueba solo las que encajan."""
    aprobadas = []
    guion_txt = ' '.join([g.get('gancho', ''), *g.get('frases', [])])
    cab = REVISION.format(año=hecho.get('año'), hecho=hecho.get('texto'), sujeto=sujeto, detalles=detalles or 'los que se deduzcan del hecho', guion=guion_txt)
    for i in range(0, len(cands), 6):
        lote = cands[i:i + 6]
        partes = [{'type': 'text', 'text': cab}]
        for k, c in enumerate(lote):
            im = c['im']
            partes.append({'type': 'text', 'text': f"Imagen id={i + k}. Archivo: {im['titulo']}. Descripción: {im.get('desc') or '—'}. Categorías: {im.get('cats') or '—'}."})
            partes.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + _miniatura_b64(c['ruta'])}})
        r = guion.llm([{'role': 'user', 'content': partes}], temperatura=0, rol='elegir', vision=True)
        for f in r.get('fotos', []):
            try:
                idx = int(f['id'])
            except (KeyError, ValueError, TypeError):
                continue
            if i <= idx < i + len(lote):
                c = cands[idx]; c['veredicto'] = f.get('veredicto'); c['muestra'] = f.get('muestra', ''); c['motivo'] = f.get('motivo', '')
                print(f"    {'✔' if f.get('veredicto') == 'si' else '✖'} {c['im']['titulo'][:55]} → {f.get('veredicto')}: {f.get('muestra', '')[:60]} ({f.get('motivo', '')[:50]})", flush=True)
                if f.get('veredicto') == 'si':
                    aprobadas.append(c)
    return aprobadas


def _asignar(aprobadas, frases, sujeto):
    """Una foto por frase, según lo que dice cada frase. Si Gemini falla, reparto por orden entre las aprobadas."""
    n = len(frases)
    try:
        r = guion.llm([{'role': 'user', 'content': ASIGNACION.format(
            sujeto=sujeto, n=n, fotos='\n'.join(f"{i}: {c['muestra']}" for i, c in enumerate(aprobadas)),
            frases='\n'.join(f'{i + 1}. {f}' for i, f in enumerate(frases)))}], temperatura=0, rol='elegir')
        ids = [int(x) for x in r.get('asignacion', [])]
        if len(ids) == n and all(0 <= x < len(aprobadas) for x in ids):
            return ids
        print(f'  asignación rara ({len(ids)} ids para {n} frases): reparto por orden', flush=True)
    except Exception as e:
        print(f'  Gemini no asigna fotos a las frases: {str(e)[:100]}', flush=True)
    return [i % len(aprobadas) for i in range(n)]


def elegir_imagenes(hecho, g, carpeta, frases, minimo=3):
    """Devuelve (una ruta por frase, fotos distintas usadas). Solo entran fotos que Gemini ha mirado y aprobado.
    Si no hay al menos `minimo` aprobadas, falla: mejor ningún vídeo que una foto que no es."""
    sujeto = g.get('sujeto') or hecho.get('texto') or g.get('titulo')
    detalles = g.get('detalles_clave') or ''
    cands, n = [], 0
    for im in _candidatas(hecho, g)[:16]:
        ext = '.png' if im['url'].lower().split('?')[0].endswith('.png') else '.jpg'
        ruta = os.path.join(carpeta, f'cand{n}{ext}')
        try:
            fuentes.descargar(im['url'], ruta); video._tam(ruta)
            cands.append({'im': im, 'ruta': ruta}); n += 1
        except Exception:
            continue
    if not cands:
        raise ValueError('ninguna foto candidata se pudo bajar')
    aprobadas = _revisar_fotos(cands, hecho, g, sujeto, detalles)
    if len(aprobadas) < minimo:
        raise ValueError(f'solo {len(aprobadas)} fotos aprobadas de {len(cands)} (mínimo {minimo}): no se publica con fotos dudosas')
    ids = _asignar(aprobadas, frases, sujeto)
    usadas = list(dict.fromkeys(ids))
    # renombrar a imgN para que el montaje y los créditos las usen en orden
    rutas = {}
    for k, i in enumerate(usadas):
        c = aprobadas[i]; nueva = os.path.join(carpeta, f'img{k}' + os.path.splitext(c['ruta'])[1])
        os.replace(c['ruta'], nueva); rutas[i] = nueva
    return [rutas[i] for i in ids], [aprobadas[i]['im'] | {'muestra': aprobadas[i]['muestra']} for i in usadas]


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
            frases = [g['gancho'], *g['frases'], g['pregunta']]
            try:
                rutas, imgs = elegir_imagenes(hecho, g, carpeta, frases)
            except ValueError as e:
                errores.append(f"fotos de «{_art(hecho)}»: {e}"); print(f'  ✖ {e}', flush=True); continue
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
                    'guion': frases, 'imagenes': [i['titulo'] for i in imgs], 'fotos': [{'archivo': i['titulo'], 'muestra': i.get('muestra', '')} for i in imgs], 'calidad': medidas}
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

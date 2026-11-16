"""Microdocumental del día (lunes, miércoles y viernes): guion de ChatGPT (o reserva de Gemini) → metraje que encaje →
voz de Ximena → control de calidad. Deja salida-docu/diario/docu-FECHA.mp4 y diario.json para publicar.
Uso: python -m docu.diario [--fecha AAAA-MM-DD]"""
import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

from nutria import calidad
from . import encargos, piloto

SALIDA = os.path.join(piloto.SALIDA, 'diario')
VOZ = ('edge', 'es-ES-XimenaNeural')
VOZ_EN = ('edge', 'en-GB-SoniaNeural')        # The Red Otter


def guion_del_dia(fecha):
    f = os.path.join(encargos.GUIONES, f'{fecha}.json')
    if os.path.exists(f):
        g = json.load(open(f))
        if not encargos.validar(g):
            print('▶ Guion de ChatGPT:', g['titulo'], flush=True)
            return g
        print('⚠️ El guion de ChatGPT no es válido:', encargos.validar(g), flush=True)
    print('▶ Sin guion de ChatGPT para hoy: escribe Gemini (reserva)', flush=True)
    return encargos.escribir(fecha)


def descripcion(g, ia):
    m = g['metadatos']
    tags = ' '.join(dict.fromkeys(['#LaNutriaRoja', *m.get('hashtags', [])]))
    extra = '\n\nAlgunas escenas son recreaciones generadas con IA.' if ia else ''
    return f"{m['descripcion']}\n\nLa Nutria Roja: lo extraordinario está más cerca de lo que crees.{extra}\n\n{piloto.CREDITO_MUSICA}\n\n{tags}"


def descripcion_en(m, ia):
    tags = ' '.join(dict.fromkeys(['#TheRedOtter', *m.get('hashtags', [])]))
    extra = '\n\nSome scenes are AI-generated recreations.' if ia else ''
    return f"{m['descripcion']}\n\nThe Red Otter: the extraordinary is closer than you think.{extra}\n\n{piloto.CREDITO_MUSICA}\n\n{tags}"


MAX_S, MIN_S, OBJETIVO_S = 70, 30, 66


def acelerar(salida, total):
    """AUTOCORRECCIÓN: si el vídeo se pasa de 70 s pero por poco (hasta ~1,28×), se acelera el propio vídeo y su audio lo justo para
    dejarlo en ~66 s, en vez de anularlo. Es lo que se hacía a mano. Devuelve la nueva duración o None si no se puede."""
    factor = total / OBJETIVO_S
    if not 1.0 < factor <= 1.28:
        return None
    tmp = salida + '.rapido.mp4'
    piloto.sh(['ffmpeg', '-v', 'error', '-y', '-i', salida, '-filter_complex',
               f'[0:v]setpts=PTS/{factor:.4f}[v];[0:a]atempo={factor:.4f}[a]', '-map', '[v]', '-map', '[a]',
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
               '-movflags', '+faststart', tmp])
    os.replace(tmp, salida)
    return piloto.duracion(salida)


def montar_y_revisar(g, lang, voz, clips, carpeta, salida):
    fallos, total = ['sin montar'], 0
    ritmo_original = piloto.RITMO_EN
    try:
        for intento in range(3):
            total = piloto.montar(g, lang, *voz, clips, carpeta, salida)
            fallos, datos = calidad.revisar(salida)
            if total > MAX_S and not fallos:                 # solo falla la duración: se arregla sin rehacer nada
                nuevo = acelerar(salida, total)
                if nuevo:
                    print(f'  ⏩ {lang}: dura {total:.1f} s, se acelera a {nuevo:.1f} s en vez de anularlo', flush=True)
                    total = nuevo
                    fallos, datos = calidad.revisar(salida)
            if not MIN_S <= total <= MAX_S:                  # Álvaro: mejor algo corto o largo que sin vídeo
                fallos.append(f'Duración {total:.1f} s fuera de {MIN_S}-{MAX_S}')
            print(f'  control de calidad ({lang}): {fallos or "OK"} {datos}', flush=True)
            if not fallos:
                break
            if total > MAX_S and lang == 'en':                # demasiado largo para acelerar el vídeo: reintentar con la voz más rápida
                pct = min(int((total / OBJETIVO_S - 1) * 100) + 2, 30)
                piloto.RITMO_EN = f'+{pct}%'
                print(f'  el inglés dura {total:.1f} s: reintento con la voz {piloto.RITMO_EN} más rápida', flush=True)
    finally:
        piloto.RITMO_EN = ritmo_original
    return fallos, total


def ingles(g, clips, fecha):
    """Versión de The Red Otter: mismo tema y planos, guion adaptado al inglés y voz de Sonia."""
    r = {'ok': False, 'fecha': fecha.isoformat(), 'idioma': 'en', 'archivo': f'docu-en-{fecha}.mp4'}
    try:
        en = piloto.adaptar_en(g)
        g_en = {**g, 'titulo': en['titulo'], 'pregunta': en.get('pregunta') or g.get('pregunta', ''), 'metadatos': en['metadatos'],
                'escenas': [{**e, 'locucion': x['locucion'], 'texto_pantalla': x.get('texto_pantalla', '')}
                            for e, x in zip(g['escenas'], en['escenas'])]}
        print('▶ Versión inglesa:', g_en['titulo'], flush=True)
        fallos, total = montar_y_revisar(g_en, 'en', VOZ_EN, clips, os.path.join(SALIDA, 'tmp-en'), os.path.join(SALIDA, r['archivo']))
        ia = any(c[1].get('ia') for c in clips)
        r.update({'ok': not fallos, 'motivo': '; '.join(fallos), 'titulo': en['metadatos'].get('titulo') or en['titulo'],
                  'descripcion': descripcion_en(en['metadatos'], ia), 'ia': ia, 'topic_id': g['topic_id'], 'tema': en['titulo'],
                  'duracion': round(total, 1)})
    except Exception as e:
        r['motivo'] = f'Versión inglesa: {e}'[:400]
        print('⚠️', r['motivo'], flush=True)
    json.dump(r, open(os.path.join(SALIDA, 'diario-en.json'), 'w'), ensure_ascii=False, indent=1)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fecha', default=dt.datetime.now(ZoneInfo('Europe/Madrid')).date().isoformat())
    a = ap.parse_args()
    fecha = dt.date.fromisoformat(a.fecha)
    os.makedirs(SALIDA, exist_ok=True)
    resultado = {'ok': False, 'fecha': fecha.isoformat()}
    g, descartados = guion_del_dia(fecha), []
    clips = None
    for intento in range(3):
        print('▶ Buscando metraje:', g['titulo'], flush=True)
        clips = piloto.metraje(g, estricto=True)
        if clips:
            break
        descartados.append(g['titulo'])
        print('▶ Tema sin metraje bueno; Gemini escribe otro', flush=True)
        g = encargos.escribir(fecha, evitar=descartados)
    if not clips:
        resultado['motivo'] = 'Ningún tema con metraje que encaje: ' + '; '.join(descartados)
    else:
        salida = os.path.join(SALIDA, f'docu-{fecha}.mp4')
        fallos, total = montar_y_revisar(g, 'es', VOZ, clips, os.path.join(SALIDA, 'tmp'), salida)
        ia = any(c[1].get('ia') for c in clips)
        resultado.update({'ok': not fallos, 'idioma': 'es', 'archivo': f'docu-{fecha}.mp4', 'motivo': '; '.join(fallos), 'titulo': g['metadatos'].get('titulo') or g['titulo'],
                          'descripcion': descripcion(g, ia), 'ia': ia, 'autor': g.get('autor', 'chatgpt'),
                          'topic_id': g['topic_id'], 'tema': g['titulo'], 'duracion': round(total, 1),
                          'metraje': [c[1] for c in clips], 'fuentes': g.get('fuentes', [])})
    json.dump(resultado, open(os.path.join(SALIDA, 'diario.json'), 'w'), ensure_ascii=False, indent=1)
    en = ingles(g, clips, fecha) if clips and os.environ.get('DOCU_INGLES', '1') == '1' else {'ok': False}
    print(json.dumps({k: resultado.get(k) for k in ('ok', 'fecha', 'titulo', 'autor', 'motivo')}, ensure_ascii=False))
    if not resultado['ok'] and not en.get('ok'):
        sys.exit(1)


if __name__ == '__main__':
    main()

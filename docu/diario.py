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


def montar_y_revisar(g, lang, voz, clips, carpeta, salida):
    fallos, total = ['sin montar'], 0
    for intento in range(2):
        total = piloto.montar(g, lang, *voz, clips, carpeta, salida)
        fallos, datos = calidad.revisar(salida)
        if not 38 <= total <= 65:
            fallos.append(f'Duración {total:.1f} s fuera de 40-60')
        print(f'  control de calidad ({lang}): {fallos or "OK"} {datos}', flush=True)
        if not fallos:
            break
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

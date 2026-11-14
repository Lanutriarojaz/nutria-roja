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
        motivos = []
        for intento in range(2):
            total = piloto.montar(g, 'es', *VOZ, clips, os.path.join(SALIDA, 'tmp'), salida)
            fallos, datos = calidad.revisar(salida)
            if not 38 <= total <= 65:
                fallos.append(f'Duración {total:.1f} s fuera de 40-60')
            print(f'  control de calidad: {fallos or "OK"} {datos}', flush=True)
            if not fallos:
                break
            motivos = fallos
        ia = any(c[1].get('ia') for c in clips)
        resultado.update({'ok': not fallos, 'motivo': '; '.join(fallos), 'titulo': g['metadatos'].get('titulo') or g['titulo'],
                          'descripcion': descripcion(g, ia), 'ia': ia, 'autor': g.get('autor', 'chatgpt'),
                          'topic_id': g['topic_id'], 'tema': g['titulo'], 'duracion': round(total, 1),
                          'metraje': [c[1] for c in clips], 'fuentes': g.get('fuentes', [])})
    json.dump(resultado, open(os.path.join(SALIDA, 'diario.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: resultado.get(k) for k in ('ok', 'fecha', 'titulo', 'autor', 'motivo')}, ensure_ascii=False))
    if not resultado['ok']:
        sys.exit(1)


if __name__ == '__main__':
    main()

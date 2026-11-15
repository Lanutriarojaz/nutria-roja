"""Programa el microdocumental del día en Buffer (TikTok, YouTube, Instagram) a las 19:00 de Madrid y lo apunta en el historial.
No repite si ya hay un vídeo en cola en ese canal, día y hora (se puede relanzar sin duplicar).
Uso: BUFFER_API_KEY=... MEDIA_BASE=https://<usuario>.github.io/<repo> python -m docu.publicar salida-docu/diario/diario.json [--prueba]"""
import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

from nutria.publicar import CREAR, canales, gql, metadatos, ya_programados
from . import encargos

HORA = os.environ.get('DOCU_HORA', '19:00')


def apuntar(v):
    h = encargos.historial()
    if not any(x['fecha'] == v['fecha'] for x in h):
        h.append({'fecha': v['fecha'], 'topic_id': v['topic_id'], 'titulo': v['tema'], 'autor': v.get('autor')})
        json.dump(h, open(encargos.HISTORIAL, 'w'), ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('diario')
    ap.add_argument('--prueba', action='store_true')
    a = ap.parse_args()
    v = json.load(open(a.diario))
    if not v.get('ok'):
        sys.exit('El vídeo no pasó los controles: no se programa')
    hh, mm = map(int, HORA.split(':'))
    dia = dt.date.fromisoformat(v['fecha'])
    cuando = dt.datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=ZoneInfo('Europe/Madrid'))
    url = f"{os.environ['MEDIA_BASE'].rstrip('/')}/{v.get('archivo') or 'docu-' + v['fecha'] + '.mp4'}"
    print(f"{v['fecha']} {HORA} → {url}\n  {v['titulo']}\n---\n{v['descripcion']}\n---")
    if a.prueba:
        print('(prueba: no se programa nada)'); return
    if cuando < dt.datetime.now(ZoneInfo('Europe/Madrid')) + dt.timedelta(minutes=10):
        sys.exit('La hora de publicación ya ha pasado')
    chs = canales()
    en_cola = ya_programados(chs)
    malos = []
    for servicio, c in chs.items():
        if (c['id'], v['fecha'], f'{hh:02d}:{mm:02d}') in en_cola:
            print(f'⏭ {servicio}: ya estaba en cola'); continue
        entrada = {'channelId': c['id'], 'text': v['descripcion'], 'schedulingType': 'automatic', 'mode': 'customScheduled',
                   'dueAt': cuando.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                   'assets': [{'video': {'url': url, 'metadata': {'thumbnailOffset': 2500}}}],
                   'metadata': metadatos(servicio, v)}
        r = gql(CREAR, {'input': entrada})['createPost']
        ok = 'post' in r
        print(f"{'✔' if ok else '✖'} {servicio}: {r.get('post', {}).get('id') or r.get('message')}")
        if not ok:
            malos.append(servicio)
    if v.get('idioma', 'es') == 'es':
        apuntar(v)
    if malos:
        sys.exit('Buffer rechazó: ' + ', '.join(malos))


if __name__ == '__main__':
    main()

"""Programa el episodio del día en Buffer (TikTok, YouTube Shorts, Instagram Reels).
Uso: BUFFER_API_KEY=... MEDIA_BASE=https://<usuario>.github.io/<repo> python -m tele.publicar salida-tele/tirada.json [--hora 13:00] [--prueba]"""
import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

from nutria.publicar import CREAR, canales, gql

MADRID = ZoneInfo('Europe/Madrid')


def en_cola(chs, cuando):
    """Canales que ya tienen algo programado a esa misma hora (para no duplicar si se relanza)."""
    ya = set()
    try:
        for o in gql('query { account { organizations { id } } }')['account']['organizations']:
            d = gql('query($o: OrganizationId!) { posts(input: {organizationId: $o, filter: {status: [scheduled]}}, first: 100) '
                    '{ edges { node { dueAt channelId } } } }', {'o': o['id']})
            for e in d['posts']['edges']:
                n = e['node']
                if n.get('dueAt') and abs((dt.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')) - cuando).total_seconds()) < 600:
                    ya.add(n['channelId'])
    except Exception as e:
        print(f'⚠️ No pude leer la cola de Buffer ({str(e)[:120]})')
    return ya


def metadatos(servicio, v):
    if servicio == 'youtube':
        return {'youtube': {'title': v['titulo_corto'][:100], 'categoryId': '23', 'privacy': 'public', 'madeForKids': False,
                            'notifySubscribers': True}}
    if servicio == 'instagram':
        return {'instagram': {'type': 'reel', 'shouldShareToFeed': True}}
    return {servicio: {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tirada')
    ap.add_argument('--hora', default=os.environ.get('TELE_HORA', '13:00'))
    ap.add_argument('--prueba', action='store_true')
    a = ap.parse_args()
    v = json.load(open(a.tirada))[0]
    hh, mm = map(int, a.hora.split(':'))
    dia = dt.date.fromisoformat(v['fecha'])
    cuando = dt.datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=MADRID)
    ahora = dt.datetime.now(MADRID)
    if cuando < ahora + dt.timedelta(minutes=10):          # si se lanza tarde, sale dentro de un cuarto de hora
        cuando = (ahora + dt.timedelta(minutes=15)).replace(second=0, microsecond=0)
    url = f"{os.environ['MEDIA_BASE'].rstrip('/')}/td-{v['fecha']}.mp4"
    if a.prueba:
        print(f"(prueba) {cuando:%d/%m %H:%M} → {url}\n{v['titulo_corto']}\n{v['descripcion']}"); return
    chs = canales()
    ya = en_cola(chs, cuando)
    fallos = 0
    for servicio, c in chs.items():
        if c['id'] in ya:
            print(f'⏭ {servicio}: ya había un vídeo a esa hora'); continue
        r = gql(CREAR, {'input': {
            'channelId': c['id'], 'text': v['descripcion'], 'schedulingType': 'automatic', 'mode': 'customScheduled',
            'dueAt': cuando.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'assets': [{'video': {'url': url, 'metadata': {'thumbnailOffset': 2500}}}], 'metadata': metadatos(servicio, v)}})['createPost']
        ok = 'post' in r
        fallos += not ok
        print(f"{'✔' if ok else '✖'} {servicio}: {r.get('post', {}).get('id') or r.get('message')}")
    if fallos or not chs:
        sys.exit(1)


if __name__ == '__main__':
    main()

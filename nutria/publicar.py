"""Programa la tirada en Buffer (TikTok, YouTube Shorts, Instagram Reels), un vídeo por día a la hora fijada.
Uso: BUFFER_API_KEY=... MEDIA_BASE=https://raw.githubusercontent.com/<usuario>/<repo>/media \
     python -m nutria.publicar salida/tirada.json [--hora 19:00] [--prueba]"""
import argparse
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import requests

API = 'https://api.buffer.com'
REDES = ('tiktok', 'youtube', 'instagram')


def gql(query, variables=None):
    for i in range(4):
        r = requests.post(API, json={'query': query, 'variables': variables or {}},
                          headers={'Authorization': f"Bearer {os.environ['BUFFER_API_KEY']}"}, timeout=60)
        if r.status_code == 429:
            time.sleep(30 * (i + 1)); continue
        j = r.json()
        if j.get('errors'):
            raise RuntimeError(f"Buffer: {j['errors'][0].get('message')}")
        return j['data']
    raise RuntimeError('Buffer: demasiadas peticiones')


def canales():
    orgs = gql('query { account { organizations { id name } } }')['account']['organizations']
    out = {}
    for o in orgs:
        for c in gql('query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id name service isQueuePaused } }',
                     {'o': o['id']})['channels']:
            if c['service'] in REDES and not c['isQueuePaused']:
                out.setdefault(c['service'], c)
    return out


def ya_programados(chs):
    """(canal, día, hora) que ya tienen un vídeo en cola, para no duplicar si se relanza la tirada.
    La hora distingue estos vídeos de los de Tele-Dimensional, que salen el mismo día a otra hora."""
    hechos = set()
    try:
        orgs = gql('query { account { organizations { id } } }')['account']['organizations']
        ids = {c['id'] for c in chs.values()}
        for o in orgs:
            d = gql('query($o: OrganizationId!) { posts(input: {organizationId: $o, filter: {status: [scheduled]}}) '
                    '{ edges { node { id dueAt channelId } } } }', {'o': o['id']})
            for e in d['posts']['edges']:
                n = e['node']
                if n.get('dueAt') and n.get('channelId') in ids:
                    dia = dt.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Madrid')).date()
                    local = dt.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Madrid'))
                    hechos.add((n['channelId'], dia.isoformat(), f'{local:%H:%M}'))
    except Exception as e:
        print(f'⚠️ No pude leer la cola de Buffer ({str(e)[:120]}); sigo sin comprobar duplicados')
    return hechos


CREAR = '''mutation($input: CreatePostInput!) { createPost(input: $input) {
  ... on PostActionSuccess { post { id dueAt } }
  ... on MutationError { message } } }'''


def metadatos(servicio, v):
    if servicio == 'youtube':
        return {'youtube': {'title': v['titulo'][:100], 'categoryId': '27', 'privacy': 'public',
                            'madeForKids': False, 'notifySubscribers': True}}
    if servicio == 'instagram':
        return {'instagram': {'type': 'reel', 'shouldShareToFeed': True}}
    if servicio == 'tiktok':
        return {'tiktok': {}}
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tirada')
    ap.add_argument('--hora', default=os.environ.get('NUTRIA_HORA', '19:00'))
    ap.add_argument('--prueba', action='store_true', help='no programa nada, solo enseña')
    a = ap.parse_args()
    tirada = json.load(open(a.tirada))
    base = os.environ['MEDIA_BASE'].rstrip('/')
    chs = {} if a.prueba else canales()
    faltan = [r for r in REDES if r not in chs]
    if faltan and not a.prueba:
        print(f'⚠️ Canales sin conectar en Buffer: {", ".join(faltan)}')
    hh, mm = map(int, a.hora.split(':'))
    en_cola = ya_programados(chs) if chs else set()
    resultado = []
    for v in tirada:
        if not v.get('ok'):
            continue
        dia = dt.date.fromisoformat(v['fecha'])
        cuando = dt.datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=ZoneInfo('Europe/Madrid'))
        if cuando < dt.datetime.now(ZoneInfo('Europe/Madrid')) + dt.timedelta(minutes=3):
            print(f"⏭ {v['fecha']}: la hora ya ha pasado, no se programa"); continue
        url = f"{base}/{v['fecha']}.mp4"
        texto = v['descripcion']
        for servicio, c in chs.items():
            if (c['id'], v['fecha'], f'{hh:02d}:{mm:02d}') in en_cola:
                print(f"⏭ {v['fecha']} {servicio}: ya había un vídeo en cola ese día"); continue
            entrada = {'channelId': c['id'], 'text': texto, 'schedulingType': 'automatic', 'mode': 'customScheduled',
                       'dueAt': cuando.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                       'assets': [{'video': {'url': url, 'metadata': {'thumbnailOffset': 1500}}}],
                       'metadata': metadatos(servicio, v)}
            r = gql(CREAR, {'input': entrada})['createPost']
            ok = 'post' in r
            resultado.append({'fecha': v['fecha'], 'red': servicio, 'ok': ok, 'detalle': r.get('post', {}).get('id') or r.get('message')})
            print(f"{'✔' if ok else '✖'} {v['fecha']} {servicio}: {resultado[-1]['detalle']}")
        if a.prueba:
            print(f"(prueba) {v['fecha']} {cuando:%H:%M} → {url}\n  {v['titulo']}")
    json.dump(resultado, open(os.path.join(os.path.dirname(a.tirada), 'programados.json'), 'w'), ensure_ascii=False, indent=2)
    if any(not r['ok'] for r in resultado):
        sys.exit(1)


if __name__ == '__main__':
    main()

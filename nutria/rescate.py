"""Sustituye en Buffer los posts YA programados de unos días por otra versión del vídeo (sin rehacer nada).
  python -m nutria.rescate ver        salida/rescate.json   → enseña qué hay en la cola para esos días y qué comando de borrado ofrece Buffer (no toca nada)
  python -m nutria.rescate sustituir  salida/rescate.json   → borra de la cola los posts de esos días (13:30) y programa los nuevos
Solo afecta a posts que siguen EN COLA (los ya publicados no se tocan)."""
import datetime as dt
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

from nutria.publicar import canales, gql

MADRID = ZoneInfo('Europe/Madrid')


def en_cola(chs, fechas):
    """[(id, canal, servicio, dia, hora, texto)] de los posts programados en esos días."""
    ids = {c['id']: s for s, c in chs.items()}
    out = []
    for o in gql('query { account { organizations { id } } }')['account']['organizations']:
        d = gql('query($o: OrganizationId!) { posts(input: {organizationId: $o, filter: {status: [scheduled]}}, first: 100) '
                '{ edges { node { id dueAt channelId text } } } }', {'o': o['id']})
        for e in d['posts']['edges']:
            n = e['node']
            if n.get('channelId') not in ids or not n.get('dueAt'):
                continue
            local = dt.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')).astimezone(MADRID)
            if local.date().isoformat() in fechas:
                out.append((n['id'], n['channelId'], ids[n['channelId']], local.date().isoformat(), f'{local:%H:%M}', (n.get('text') or '')[:70]))
    return sorted(out, key=lambda x: (x[3], x[2]))


def comandos_de_borrado():
    d = gql('query { __type(name: "Mutation") { fields { name args { name type { name kind ofType { name kind } } } } } }')
    return [f for f in d['__type']['fields'] if 'delete' in f['name'].lower() or 'remove' in f['name'].lower()]


def main():
    accion, ruta = sys.argv[1], sys.argv[2]
    nuevos = [v for v in json.load(open(ruta)) if v.get('ok')]
    fechas = {v['fecha'] for v in nuevos}
    chs = canales()
    cola = en_cola(chs, fechas)
    print(f'En la cola de Buffer para {sorted(fechas)}: {len(cola)} posts')
    for c in cola:
        print(f'  {c[3]} {c[4]} {c[2]:9} {c[0]}  {c[5]}')
    borrado = comandos_de_borrado()
    print('Comandos de borrado que ofrece Buffer:', json.dumps(borrado, ensure_ascii=False)[:600])
    if accion == 'ver':
        return
    nombre = next((f['name'] for f in borrado if f['name'].lower() in ('deletepost', 'removepost')), None)
    if not nombre:
        sys.exit('Buffer no ofrece un comando de borrado conocido: no sustituyo nada')
    for pid, _, red, dia, hora, _ in cola:
        r = gql('mutation($id: PostId!) { %s(input: {id: $id}) { __typename } }' % nombre, {'id': pid})
        print(f'  🗑 borrado {dia} {red}: {json.dumps(r)[:120]}')
    print('Programando las versiones nuevas…')
    sys.exit(subprocess.call([sys.executable, '-m', 'nutria.publicar', ruta]))


if __name__ == '__main__':
    main()

"""Chequeo de salud: cola de Buffer por red (límite del plan gratis: 10 publicaciones programadas por canal)
y espacio de los vídeos en GitHub Pages (límite 1 GB). Uso: BUFFER_API_KEY=... python -m nutria.estado"""
import datetime as dt
import os
import subprocess
from zoneinfo import ZoneInfo

from .publicar import canales, gql

LIMITE_COLA = 10


def main():
    chs = canales()
    ids = {c['id']: s for s, c in chs.items()}
    cola = {s: [] for s in chs}
    for o in gql('query { account { organizations { id } } }')['account']['organizations']:
        d = gql('query($o: OrganizationId!) { posts(input: {organizationId: $o, filter: {status: [scheduled]}}, first: 100) '
                '{ edges { node { dueAt channelId } } } }', {'o': o['id']})
        for e in d['posts']['edges']:
            n = e['node']
            if n.get('channelId') in ids and n.get('dueAt'):
                cola[ids[n['channelId']]].append(dt.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Madrid')))
    print('## Buffer: publicaciones programadas por red (máximo gratis: 10)')
    peor = 0
    for s, fechas in cola.items():
        fechas.sort(); peor = max(peor, len(fechas))
        print(f"- {s}: {len(fechas)}/{LIMITE_COLA}  " + ', '.join(f'{f:%d/%m %H:%M}' for f in fechas))
    print('\n## Buffer: últimas publicaciones con error o ya enviadas')
    for estado in ('error', 'sent'):
        try:
            for o in gql('query { account { organizations { id } } }')['account']['organizations']:
                d = gql('query($o: OrganizationId!, $s: [PostStatus!]) { posts(input: {organizationId: $o, filter: {status: $s}}, first: 12) '
                        '{ edges { node { dueAt channelId error { message } } } } }', {'o': o['id'], 's': [estado]})
                for e in d['posts']['edges'][:12]:
                    n = e['node']
                    if n.get('channelId') in ids:
                        f = dt.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Madrid')) if n.get('dueAt') else None
                        msg = ((n.get('error') or {}).get('message') or '')[:140]
                        print(f"- {'❌' if estado == 'error' else '✅'} {ids[n['channelId']]} {f:%d/%m %H:%M}  {msg}" if f else f"- {estado} {ids[n['channelId']]}")
        except Exception as ex:
            print(f'- (no pude leer «{estado}»: {str(ex)[:150]})')
    faltan = [r for r in ('tiktok', 'youtube', 'instagram') if r not in chs]
    if faltan:
        print(f"- ⚠️ Canales desconectados o en pausa: {', '.join(faltan)}")
    print(f"\nMargen: {LIMITE_COLA - peor} huecos libres en la red más llena "
          f"(el lunes, con 7 efemérides + 1 Tele-Dimensional, la cola llega a 8).")
    try:
        subprocess.run(['git', 'fetch', '-q', '--depth', '1', 'origin', 'media'], check=True)
        out = subprocess.run(['git', 'ls-tree', '-r', '-l', 'origin/media'], capture_output=True, text=True, check=True).stdout
        total = sum(int(l.split()[3]) for l in out.splitlines() if l.split()[3].isdigit())
        print(f"\n## GitHub Pages: {total / 1e6:.0f} MB de vídeos publicados (límite 1000 MB)")
    except Exception as e:
        print('No pude medir la rama media:', str(e)[:120])


if __name__ == '__main__':
    main()

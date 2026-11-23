"""Vigilante DESPUÉS de publicar: busca en Buffer los posts que fallaron al enviarse en las últimas 30 h (las dos cuentas),
los reintenta una vez y, si alguno sigue fallando, deja informe-envios.md y ok=no en $GITHUB_OUTPUT para mandar UN correo.
Si todo salió bien, silencio. Uso: python -m nutria.envios"""
import datetime as dt
import os
import time

import requests

API = 'https://api.buffer.com'
CUENTAS = [('La Nutria Roja', 'BUFFER_API_KEY'), ('The Red Otter', 'BUFFER_API_KEY_EN')]


def gql(clave, q, v=None):
    for i in range(4):
        r = requests.post(API, json={'query': q, 'variables': v or {}}, headers={'Authorization': f'Bearer {clave}'}, timeout=60)
        if r.status_code == 429:
            time.sleep(30 * (i + 1)); continue
        j = r.json()
        if j.get('errors'):
            raise RuntimeError(j['errors'][0].get('message'))
        return j['data']
    raise RuntimeError('Buffer no responde (429)')


def fallidos(clave, desde):
    out = []
    for o in gql(clave, 'query { account { organizations { id } } }')['account']['organizations']:
        d = gql(clave, 'query($o: OrganizationId!) { posts(input: {organizationId: $o, filter: {status: [error]}}, first: 50) '
                       '{ edges { node { id dueAt channelService text error { message rawError } } } } }', {'o': o['id']})
        for e in d['posts']['edges']:
            n = e['node']
            if n.get('dueAt') and dt.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')) >= desde:
                out.append(n)
    return out


def main():
    desde = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=30)
    informe, quedan = [], 0
    for cuenta, var in CUENTAS:
        clave = os.environ.get(var)
        if not clave:
            continue
        try:
            malos = fallidos(clave, desde)
        except Exception as e:
            informe.append(f'- {cuenta}: no pude leer Buffer ({str(e)[:120]})'); continue
        for n in malos:
            motivo = (n.get('error') or {}).get('message') or '?'
            print(f"✖ {cuenta} {n['dueAt'][:16]} {n['channelService']}: {motivo}")
            try:
                r = gql(clave, 'mutation($i: PublishPostNowInput!) { publishPostNow(input: $i) { __typename ... on MutationError { message } } }', {'i': {'id': n['id']}})
                print('  reintento:', r)
            except Exception as e:
                print('  reintento falló:', str(e)[:120])
        if malos:
            time.sleep(120)                                 # dar tiempo a Buffer a enviar
            siguen = {x['id']: x for x in fallidos(clave, desde)}
            for n in malos:
                if n['id'] in siguen:
                    quedan += 1
                    motivo = (siguen[n['id']].get('error') or {}).get('message') or '?'
                    informe.append(f"- {cuenta} · {n['channelService']} · {n['dueAt'][:16]} UTC · «{(n.get('text') or '')[:60]}»: **{motivo}**")
                else:
                    print(f"  ✔ recuperado: {cuenta} {n['channelService']}")
    titulo = f'📺 {quedan} vídeo(s) no se han podido publicar' if quedan else 'Todo publicado'
    texto = '\n'.join([f'# {titulo}', '', *informe, '',
                       'Se reintentó una vez automáticamente. Para verlos: Buffer → Sent/Error, o dímelo y lo miro.']) + '\n'
    open('informe-envios.md', 'w').write(texto)
    print(texto)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"titulo={titulo}\nok={'no' if quedan else 'si'}\n")


if __name__ == '__main__':
    main()

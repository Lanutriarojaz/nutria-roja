"""Sondeo (solo lectura): ¿qué estadísticas de los posts publicados da la API de Buffer? Enseña los campos y un ejemplo."""
import json

from nutria.publicar import gql


def campos(tipo):
    d = gql('query($n: String!) { __type(name: $n) { name kind fields { name type { name kind ofType { name kind ofType { name } } } } } }', {'n': tipo})
    return d['__type']


def main():
    post = campos('Post')
    print('Campos de Post:', [f['name'] for f in post['fields']])
    for f in post['fields']:
        if any(k in f['name'].lower() for k in ('metric', 'stat', 'insight', 'analytic', 'engag')):
            t = f['type'].get('name') or (f['type'].get('ofType') or {}).get('name') or ((f['type'].get('ofType') or {}).get('ofType') or {}).get('name')
            print(f'\n== {f["name"]} → {t}')
            if t:
                try:
                    sub = campos(t)
                    print('   ', json.dumps([x['name'] for x in (sub.get('fields') or [])], ensure_ascii=False))
                except Exception as e:
                    print('   (no se pudo abrir)', e)
    orgs = gql('query { account { organizations { id } } }')['account']['organizations']
    d = gql('query($o: OrganizationId!) { posts(input: {organizationId: $o, filter: {status: [sent]}}, first: 3) { edges { node { id dueAt channelId text } } } }', {'o': orgs[0]['id']})
    print('\nEjemplo de enviados:', json.dumps(d, ensure_ascii=False)[:600])


if __name__ == '__main__':
    main()

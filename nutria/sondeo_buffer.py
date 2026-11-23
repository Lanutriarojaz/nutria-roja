"""Sondeo (solo lectura) de la API de Buffer: campos de Post y de sus assets, y un post fallido de ejemplo."""
import json

from nutria.publicar import gql


def campos(tipo):
    return gql('query($n: String!) { __type(name: $n) { name kind possibleTypes { name } fields { name type { name kind ofType { name kind ofType { name } } } } } }', {'n': tipo})['__type']


def main():
    post = campos('Post')
    print('Post:', [(f['name'], f['type'].get('name') or (f['type'].get('ofType') or {}).get('name') or ((f['type'].get('ofType') or {}).get('ofType') or {}).get('name')) for f in post['fields']])
    for t in ('Asset', 'VideoAsset', 'PostError', 'Error', 'PostAsset', 'Mutation'):
        try:
            c = campos(t)
            if c:
                print(t, c.get('kind'), [p['name'] for p in (c.get('possibleTypes') or [])],
                      [f['name'] for f in (c.get('fields') or []) if t != 'Mutation' or 'post' in f['name'].lower()])
        except Exception as e:
            print(t, 'no:', str(e)[:80])


if __name__ == '__main__':
    main()

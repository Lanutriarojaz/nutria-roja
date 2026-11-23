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


def extra():
    print('PostPublishingError', [f['name'] for f in campos('PostPublishingError')['fields']])
    m = gql('query { __type(name: "Mutation") { fields { name args { name type { name kind ofType { name } } } type { name kind possibleTypes { name } } } } }')
    for f in m['__type']['fields']:
        if f['name'] in ('publishPostNow', 'editPost'):
            print(f['name'], [(a['name'], a['type'].get('name') or a['type']['ofType']['name']) for a in f['args']], f['type'])
    for n in ('PublishPostNowInput', 'EditPostInput', 'DailyPostingLimitsInput'):
        try:
            c = gql('query($n: String!) { __type(name: $n) { inputFields { name type { name kind ofType { name } } } } }', {'n': n})['__type']
            if c: print(n, [(x['name'], x['type'].get('name') or x['type']['ofType']['name']) for x in c['inputFields']])
        except Exception as e:
            print(n, 'no', str(e)[:60])
    orgs = gql('query { account { organizations { id } } }')['account']['organizations']
    for o in orgs:
        d = gql('query($o: OrganizationId!) { posts(input: {organizationId: $o, filter: {status: [error]}}, first: 20) '
                '{ edges { node { id dueAt channelService status error { ' + ' '.join(f['name'] for f in campos('PostPublishingError')['fields']) + ' } } } } }', {'o': o['id']})
        print(json.dumps(d, ensure_ascii=False)[:1500])


if __name__ == '__main__':
    extra()
    main()

"""Cambia la hora de los posts ya programados en Buffer (sin borrar ni volver a subir nada).
Uso: python -m nutria.mover HH:MM HH:MM AAAA-MM-DD [AAAA-MM-DD ...]   (de esa hora a la otra, esos días)"""
import datetime as dt
import sys
from zoneinfo import ZoneInfo

from nutria.publicar import canales, gql
from nutria.rescate import en_cola

EDITAR = 'mutation($i: EditPostInput!) { editPost(input: $i) { __typename ... on PostActionSuccess { post { id dueAt } } ... on MutationError { message } } }'


def main():
    desde, hasta, fechas = sys.argv[1], sys.argv[2], set(sys.argv[3:])
    hh, mm = map(int, hasta.split(':'))
    mal = 0
    for pid, _, red, dia, hora, texto in en_cola(canales(), fechas):
        if hora != desde:
            continue
        d = dt.date.fromisoformat(dia)
        nuevo = dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=ZoneInfo('Europe/Madrid')).astimezone(ZoneInfo('UTC'))
        r = gql(EDITAR, {'i': {'id': pid, 'dueAt': nuevo.strftime('%Y-%m-%dT%H:%M:%S.000Z'), 'mode': 'customScheduled', 'schedulingType': 'automatic'}})['editPost']
        ok = 'post' in r
        mal += not ok
        print(f"{'✔' if ok else '✖'} {dia} {red}: {desde} → {hasta}  {r.get('post') or r.get('message')}")
    if mal:
        sys.exit(1)


if __name__ == '__main__':
    main()

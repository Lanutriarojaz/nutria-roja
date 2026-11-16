"""Enseña qué hay programado en Buffer (solo lectura): día, hora, red y texto. Sirve para comprobar sin abrir Buffer.
Uso: BUFFER_API_KEY=... python -m nutria.cola [AAAA-MM-DD ...]   (sin fechas: hoy y los 6 días siguientes)"""
import datetime as dt
import sys

from nutria.publicar import canales
from nutria.rescate import en_cola


def main():
    hoy = dt.date.today()
    fechas = set(sys.argv[1:]) or {(hoy + dt.timedelta(days=n)).isoformat() for n in range(7)}
    chs = canales()
    print('Redes que ve esta clave:', ', '.join(f"{k}={c['name']}" for k, c in chs.items()) or 'NINGUNA')
    cola = en_cola(chs, fechas)
    print(f'{len(cola)} posts programados entre {min(fechas)} y {max(fechas)}')
    for pid, _, red, dia, hora, texto in cola:
        print(f'  {dia} {hora} {red:9} {texto}')


if __name__ == '__main__':
    main()

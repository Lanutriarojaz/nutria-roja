"""Efemérides con guion de ChatGPT (atajo del iPhone, domingo por la noche).
1) preparar: el domingo GitHub elige con Wikipedia el hecho de cada día de la semana siguiente y deja un encargo por día
   (nutria/encargos/1.txt … 7.txt) con el texto de la fuente; los datos del hecho quedan en nutria/encargos/meta-FECHA.json.
2) guardar: el atajo devuelve cada guion (con su "fecha") y se guarda en nutria/guiones/FECHA.json.
3) La tirada del lunes lo usa SOLO si el verificador confirma que todo está en la fuente; si no, escribe como siempre.
Uso: python -m nutria.encargos preparar [--desde AAAA-MM-DD]   |   python -m nutria.encargos guardar < respuesta"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

from . import fuentes, guion

AQUI = os.path.dirname(os.path.abspath(__file__))
ENCARGOS = os.path.join(AQUI, 'encargos')
GUIONES = os.path.join(AQUI, 'guiones')

EXTRA = """
IMPORTANTE para este encargo:
- Escribe SOLO con datos que estén en el TEXTO FUENTE. Un verificador comprobará cada dato; si inventas, el guion se tira.
- Añade al JSON el campo "fecha": "{fecha}" exactamente así.
- Responde SOLO con el JSON, sin explicaciones ni ```.
"""


def preparar(desde, dias=7):
    os.makedirs(ENCARGOS, exist_ok=True)
    for f in glob.glob(os.path.join(ENCARGOS, '*')):
        os.remove(f)
    usados = []
    for n in range(dias):
        fecha = desde + dt.timedelta(days=n)
        d, m = fecha.day, fecha.month
        candidatos = fuentes.efemerides(m, d)
        if not candidatos:
            print(f'⚠️ {fecha}: Wikipedia no tiene efemérides'); continue
        hecho = next((h for h in guion.elegir(candidatos, d, m, usados) if h['articulos'][0] not in usados), candidatos[0])
        usados.append(hecho['articulos'][0])
        fuente = (hecho.get('resumen') or '') + '\n\n' + fuentes.articulo(hecho['articulos'][0])
        mes = guion.MESES[m - 1]
        texto = (guion.SISTEMA.format(dia=d, mes=mes) + f"\n\nHECHO ({hecho['año']}): {hecho['texto']}\n\nTEXTO FUENTE (Wikipedia):\n{fuente}\n\n"
                 + guion.FORMATO.format(dia=d, mes=mes) + EXTRA.format(fecha=fecha.isoformat()))
        open(os.path.join(ENCARGOS, f'{n + 1}.txt'), 'w').write(texto)
        json.dump({'fecha': fecha.isoformat(), 'hecho': hecho, 'fuente': fuente},
                  open(os.path.join(ENCARGOS, f'meta-{fecha.isoformat()}.json'), 'w'), ensure_ascii=False, indent=1)
        print(f"✔ {fecha}: {hecho['año']} · {hecho['texto'][:80]}")


def _json(texto):
    t = re.sub(r'^```(?:json)?|```$', '', texto.strip(), flags=re.M).strip()
    a, b = t.find('{'), t.rfind('}')
    if a < 0 or b < a:
        raise ValueError('La respuesta no trae JSON')
    return json.loads(t[a:b + 1])


def guardar(texto):
    g = _json(texto)
    fecha = str(g.get('fecha', ''))[:10]
    dt.date.fromisoformat(fecha)                      # tiene que traer una fecha válida
    if not os.path.exists(os.path.join(ENCARGOS, f'meta-{fecha}.json')):
        raise ValueError(f'No hay encargo para el {fecha}')
    os.makedirs(GUIONES, exist_ok=True)
    json.dump(g, open(os.path.join(GUIONES, f'{fecha}.json'), 'w'), ensure_ascii=False, indent=1)
    return fecha, g.get('titulo', '')


def de_chatgpt(fecha):
    """(hecho, fuente, guion) escritos por ChatGPT para ese día, o None."""
    r, meta = os.path.join(GUIONES, f'{fecha}.json'), os.path.join(ENCARGOS, f'meta-{fecha}.json')
    if not (os.path.exists(r) and os.path.exists(meta)):
        return None
    m = json.load(open(meta))
    return m['hecho'], m['fuente'], json.load(open(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('accion', choices=['preparar', 'guardar'])
    ap.add_argument('--desde')
    a = ap.parse_args()
    if a.accion == 'guardar':
        fecha, titulo = guardar(sys.stdin.read())
        print(f'✔ Guion de efeméride del {fecha}: «{titulo}»')
    else:
        hoy = dt.date.today()
        desde = dt.date.fromisoformat(a.desde) if a.desde else hoy + dt.timedelta(days=(7 - hoy.weekday()) % 7 or 7)
        preparar(desde)


if __name__ == '__main__':
    main()

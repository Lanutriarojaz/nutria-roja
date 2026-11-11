"""Banco de ideas de Tele-Dimensional.
- ChatGPT (atajo del iPhone, cada domingo) es la fuente principal; Claude (tarea programada) es la reserva.
- Cada tanda se guarda en tele/ideas/AAAA-MM-DD.json; el episodio diario gasta una idea pendiente.
Uso:
  python -m tele.ideas guardar --fuente chatgpt < texto      (acepta JSON tal cual o con texto alrededor)
  python -m tele.ideas pendientes                            (cuántas quedan)
  python -m tele.ideas prompt                                (el encargo que se le hace a la IA)"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

from .catalogo import FORMATOS

AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(AQUI, 'ideas')
USADAS = os.path.join(CARPETA, 'usadas.json')
CAMPOS = ('elementos', 'concepto', 'formato', 'premisa', 'chiste', 'giro')

PROMPT = """Eres el jefe de ideas de TELE-DIMENSIONAL, una serie de vídeos de un minuto (TikTok, Reels, Shorts) en español de España:
un canal de televisión ficticio que emite desde universos alternativos. Humor absurdo y seco para adultos, ciencia ficción,
sátira de la tele y de la vida cotidiana, dilemas filosóficos tratados como un trámite. Todo original: nada de personajes,
frases o mundos de series o películas que existan, ni personas reales, ni política actual, ni religiones concretas.

Inventa 7 ideas de episodio MUY DISTINTAS entre sí. Cada una:
- 3 elementos cotidianos (objetos, comida, animales o cosas del día a día) que sean IMPRESCINDIBLES para la historia.
- Un concepto filosófico, paradoja o mito (cada idea uno distinto, no siempre los típicos).
- Un formato de tele, uno de estos: {formatos}.
- La premisa en una frase: «X quiere Y, pero Z». Tiene que entenderse a la primera.
- El chiste central: la situación absurda que da risa, contada en una frase.
- El giro final: lo que lo cambia todo en la última frase y que ES el concepto filosófico. Mejor si cierra el círculo.
- Un gancho: la primera frase del vídeo (máximo 12 palabras), una afirmación imposible dicha como rutina.

Responde SOLO con este JSON, sin nada más:
{{"ideas": [{{"titulo": "...", "elementos": ["...", "...", "..."], "concepto": "...", "formato": "...", "conflicto": "...",
"premisa": "...", "chiste": "...", "giro": "...", "gancho": "..."}}]}}"""


def prompt():
    return PROMPT.format(formatos=', '.join(FORMATOS))


def _json(texto):
    """Saca el JSON de la respuesta aunque venga con explicaciones o ```json alrededor."""
    t = texto.strip()
    t = re.sub(r'^```(?:json)?|```$', '', t, flags=re.M).strip()
    try:
        return json.loads(t)
    except ValueError:
        pass
    a, b = t.find('{'), t.rfind('}')
    if a < 0 or b < a:
        raise ValueError('La respuesta no trae JSON')
    return json.loads(t[a:b + 1])


def limpiar(dato):
    ideas = dato.get('ideas', dato) if isinstance(dato, dict) else dato
    if not isinstance(ideas, list):
        raise ValueError('No hay una lista de ideas')
    buenas = []
    for i in ideas:
        if not isinstance(i, dict) or any(not i.get(k) for k in CAMPOS):
            continue
        el = [str(e).strip().lower() for e in i['elementos'] if str(e).strip()][:3]
        if len(el) < 3:
            continue
        f = str(i['formato']).strip().lower()
        if f not in FORMATOS:      # admite el nombre largo («un juicio televisado») o parecido
            f = next((k for k, v in FORMATOS.items() if k in f or f in v[0]), None)
        if not f:
            continue
        buenas.append({'titulo': str(i.get('titulo', ''))[:80], 'elementos': el, 'concepto': str(i['concepto'])[:120],
                       'formato': f, 'conflicto': str(i.get('conflicto', ''))[:200], 'premisa': str(i['premisa'])[:300],
                       'chiste': str(i['chiste'])[:300], 'giro': str(i['giro'])[:300], 'gancho': str(i.get('gancho', ''))[:120]})
    if len(buenas) < 3:
        raise ValueError(f'Solo {len(buenas)} ideas válidas')
    return buenas


def guardar(texto, fuente, fecha=None):
    ideas = limpiar(_json(texto))
    os.makedirs(CARPETA, exist_ok=True)
    fecha = fecha or dt.date.today().isoformat()
    ruta = os.path.join(CARPETA, f'{fecha}-{fuente}.json')
    json.dump({'fuente': fuente, 'fecha': fecha, 'ideas': ideas}, open(ruta, 'w'), ensure_ascii=False, indent=1)
    return ruta, len(ideas)


def _usadas():
    try:
        return set(json.load(open(USADAS)))
    except (OSError, ValueError):
        return set()


def pendientes():
    """Ideas sin usar, de la tanda más antigua a la más nueva; ChatGPT antes que la reserva."""
    usadas, out = _usadas(), []
    tandas = sorted(glob.glob(os.path.join(CARPETA, '20*.json')), key=lambda r: (os.path.basename(r)[:10], 'chatgpt' not in r))
    for ruta in tandas:
        d = json.load(open(ruta))
        for n, i in enumerate(d['ideas']):
            clave = f"{os.path.basename(ruta)}#{n}"
            if clave not in usadas:
                out.append(dict(i, clave=clave, fuente=d['fuente']))
    return out


def gastar(clave):
    u = _usadas(); u.add(clave)
    os.makedirs(CARPETA, exist_ok=True)
    json.dump(sorted(u), open(USADAS, 'w'), ensure_ascii=False, indent=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('accion', choices=['guardar', 'pendientes', 'prompt'])
    ap.add_argument('--fuente', default='chatgpt')
    a = ap.parse_args()
    if a.accion == 'prompt':
        print(prompt())
    elif a.accion == 'pendientes':
        p = pendientes(); print(len(p)); [print(' -', i['fuente'], '·', i['titulo'] or i['premisa'][:60]) for i in p]
    else:
        ruta, n = guardar(sys.stdin.read(), a.fuente)
        print(f'✔ {n} ideas guardadas en {os.path.relpath(ruta)}')


if __name__ == '__main__':
    main()

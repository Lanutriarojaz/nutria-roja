"""Chequeo del domingo por la noche: ¿han llegado los guiones de ChatGPT para la semana que empieza el lunes?
Sin IA ni cuotas: solo cuenta ficheros. Escribe el informe en el fichero que se le diga y deja en $GITHUB_OUTPUT titulo=… y ok=si|no.
Uso: python -m nutria.chequeo [--lunes AAAA-MM-DD] [--informe informe.md]"""
import argparse
import datetime as dt
import json
import os

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def _leer(ruta):
    try:
        return json.load(open(ruta))
    except (OSError, ValueError):
        return None


def _bien_efemeride(g):
    return isinstance(g, dict) and g.get('titulo') and len(g.get('frases') or []) >= 3


def _bien_docu(g):
    return isinstance(g, dict) and bool(g)


def revisar(lunes):
    """Devuelve (efemérides, documentales): listas de (fecha, estado) con estado 'ok' | 'falta' | 'roto' | 'viejo'."""
    efe, doc = [], []
    for n in range(7):
        f = lunes + dt.timedelta(days=n)
        ruta = os.path.join(RAIZ, 'nutria', 'guiones', f'{f.isoformat()}.json')
        if not os.path.exists(ruta):
            efe.append((f, 'falta')); continue
        g = _leer(ruta)
        if not _bien_efemeride(g):
            efe.append((f, 'roto'))
        elif not g.get('sujeto'):
            efe.append((f, 'viejo'))          # llegó, pero con el encargo antiguo (sin «sujeto» para revisar las fotos)
        else:
            efe.append((f, 'ok'))
    for n in (0, 2, 4):                        # documentales: lunes, miércoles y viernes
        f = lunes + dt.timedelta(days=n)
        ruta = os.path.join(RAIZ, 'docu', 'guiones', f'{f.isoformat()}.json')
        if not os.path.exists(ruta):
            doc.append((f, 'falta'))
        else:
            doc.append((f, 'ok' if _bien_docu(_leer(ruta)) else 'roto'))
    return efe, doc


def _fmt(f):
    return f'{DIAS[f.weekday()]} {f.day}/{f.month}'


def informe(lunes):
    efe, doc = revisar(lunes)
    ok_e = sum(e == 'ok' for _, e in efe) + sum(e == 'viejo' for _, e in efe)
    ok_d = sum(e == 'ok' for _, e in doc)
    todo = ok_e == len(efe) and ok_d == len(doc) and all(e != 'viejo' for _, e in efe)
    marca = {'ok': '✅', 'falta': '❌ no ha llegado', 'roto': '❌ llegó roto', 'viejo': '⚠️ llegó con el encargo antiguo'}
    L = [f'# Guiones para la semana del {_fmt(lunes)}', '',
         f'**Efemérides: {ok_e}/{len(efe)}** · **Documentales: {ok_d}/{len(doc)}**', '', '## Efemérides']
    L += [f'- {_fmt(f)}: {marca[e]}' for f, e in efe]
    L += ['', '## Documentales']
    L += [f'- {_fmt(f)}: {marca[e]}' for f, e in doc]
    if todo:
        L += ['', 'Todo ha llegado. No tienes que hacer nada.']
    else:
        L += ['', '**Qué pasa con los que faltan:** ese día lo escribe Gemini de reserva (Efemérides y Documentales) y sale igualmente; '
                  'solo se pierde que lo escriba ChatGPT.',
              'Si quieres recuperarlos, abre en el iPhone el atajo «Efemérides guiones» o «Documentales guiones» y pulsa ▶ antes del lunes a las 6:00.']
    titulo = (f"{'✅' if todo else '⚠️'} Guiones de la semana del {lunes.day}/{lunes.month}: "
              f"Efemérides {ok_e}/{len(efe)} · Documentales {ok_d}/{len(doc)}")
    return titulo, '\n'.join(L) + '\n', todo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lunes', help='lunes de la semana a revisar (AAAA-MM-DD); por omisión, el próximo lunes')
    ap.add_argument('--informe', default='informe-chequeo.md')
    a = ap.parse_args()
    hoy = dt.date.today()
    lunes = dt.date.fromisoformat(a.lunes) if a.lunes else hoy + dt.timedelta(days=(7 - hoy.weekday()) % 7 or 7)
    titulo, texto, todo = informe(lunes)
    open(a.informe, 'w').write(texto)
    print(titulo); print(texto)
    salida = os.environ.get('GITHUB_OUTPUT')
    if salida:
        with open(salida, 'a') as f:
            f.write(f'titulo={titulo}\nok={"si" if todo else "no"}\n')


if __name__ == '__main__':
    main()

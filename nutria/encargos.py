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

LIBRE = """Eres el guionista de «La Nutria Roja», un canal de vídeos cortos (TikTok, Reels, Shorts) en español de España sobre lo que pasó un día como hoy en la historia.

TU DÍA: {dia} de {mes}. ELIGE TÚ el hecho: lo más interesante, sorprendente o curioso que pasó un {dia} de {mes} de cualquier año
(un invento, un récord, un estreno, un descubrimiento, un personaje, algo insólito...). Que enganche a gente joven de España.
Evita tragedias con muchas víctimas y la política actual que divide. Usa solo datos de los que estés seguro: fecha, año y cifras exactos.
IMPORTANTE, LAS FOTOS: el vídeo se ilustra solo con fotos libres de derechos de Wikimedia Commons (dominio público o licencias abiertas), y cada una
se revisa mirándola. Elige un hecho que TENGA fotos libres claras: ciencia, exploración, inventos, edificios y lugares, naturaleza, historia y personajes
históricos, deporte hasta los años 90, misiones espaciales (NASA), obras de arte antiguas. EVITA lo que casi nunca tiene fotos libres: manga, anime, cine,
series, música y videojuegos modernos, marcas y productos actuales, famosos recientes. Si dudas entre dos hechos, elige el que se pueda ver mejor.

Estilo: cercano, con ritmo, frases cortas, curiosidad. Que suene a persona contándoselo a un amigo, no a IA ni a enciclopedia.
PROHIBIDO: "¡Increíble!", "¿Sabías que...?" como muletilla, "sumérgete", "fascinante", "en un mundo donde", "no te lo vas a creer",
"épico", "un hito sin precedentes", rayas largas (—). Como mucho 1 emoji en el título y 1 en la descripción.
La primera frase de "frases" empieza EXACTAMENTE por "Un día como hoy, {dia} de {mes} de <AÑO>," con el año del hecho.

Devuelve SOLO este JSON (sin explicaciones ni ```):
{{
 "fecha": "{fecha}",
 "año": 0000,
 "hecho": "el hecho en una frase",
 "articulo": "título EXACTO del artículo de Wikipedia en español sobre el tema (para buscar las fotos)",
 "sujeto": "quién o qué debe VERSE en las fotos, con su nombre exacto (p. ej. «Mike Tyson», «módulo lunar Intrepid del Apolo 12»)",
 "detalles_clave": "lo que NO puede fallar al elegir fotos: país o bando, época, modelo, lugar, persona (p. ej. «EE. UU., NASA, 1969; no es soviético»)",
 "gancho": "frase de 6 a 12 palabras que haga parar el dedo, intrigante, sin revelar todo (no empieces por 'Un día como hoy')",
 "frases": ["Un día como hoy, {dia} de {mes} de AAAA, ...", "...", "..."],
 "pregunta": "pregunta final corta que apetezca contestar (opinión o experiencia)",
 "titulo": "título para YouTube Shorts, máximo 70 caracteres, con el tema y el año, como mucho 1 emoji",
 "descripcion": "primera línea con la palabra clave y gancho, segunda con un dato extra breve, y al final 4 o 5 hashtags: #historia #undiacomohoy #curiosidades + 1 o 2 del tema",
 "busquedas": ["3 búsquedas EN INGLÉS para encontrar fotos reales del tema en Wikimedia Commons, concretas (personas, lugares, objetos, año)"]
}}
LAS FOTOS: otra IA buscará fotos reales en Wikimedia Commons y las revisará mirándolas. "sujeto" y "detalles_clave" son la guía de esa revisión: sé concreto y exacto.
"frases": de 4 a 6, en total 60 a 90 palabras, con 1 o 2 curiosidades sorprendentes y el dato más bestia guardado para el final.
"""


def preparar(desde, dias=7):
    """Un encargo por día con libertad total: ChatGPT elige el hecho y escribe el guion (sin veto de Gemini)."""
    os.makedirs(ENCARGOS, exist_ok=True)
    for f in glob.glob(os.path.join(ENCARGOS, '*')):
        os.remove(f)
    for n in range(dias):
        fecha = desde + dt.timedelta(days=n)
        mes = guion.MESES[fecha.month - 1]
        open(os.path.join(ENCARGOS, f'{n + 1}.txt'), 'w').write(LIBRE.format(dia=fecha.day, mes=mes, fecha=fecha.isoformat()))
        json.dump({'fecha': fecha.isoformat(), 'libre': True}, open(os.path.join(ENCARGOS, f'meta-{fecha.isoformat()}.json'), 'w'),
                  ensure_ascii=False, indent=1)
        print(f"✔ {fecha}: encargo libre")


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
    if not g.get('frases') or not g.get('titulo'):
        raise ValueError('Al guion le faltan frases o título')
    os.makedirs(GUIONES, exist_ok=True)
    json.dump(g, open(os.path.join(GUIONES, f'{fecha}.json'), 'w'), ensure_ascii=False, indent=1)
    return fecha, g.get('titulo', '')


def de_chatgpt(fecha):
    """(hecho, fuente, guion) de ChatGPT para ese día, o None. Con el encargo libre, el hecho sale del propio guion."""
    r, meta = os.path.join(GUIONES, f'{fecha}.json'), os.path.join(ENCARGOS, f'meta-{fecha}.json')
    if not os.path.exists(r):
        return None
    g = json.load(open(r))
    m = json.load(open(meta)) if os.path.exists(meta) else {}
    if m.get('hecho'):                                # encargo antiguo: el hecho lo había elegido Gemini
        return m['hecho'], m.get('fuente', ''), g
    año = int(str(g.get('año') or re.search(r'de (\d{3,4}),', (g.get('frases') or [''])[0]).group(1)))
    hecho = {'año': año, 'texto': g.get('hecho') or g.get('titulo', ''), 'articulos': [a for a in [g.get('articulo')] if a],
             'resumen': ''}
    return hecho, '', g


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

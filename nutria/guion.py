"""Elige el hecho del día y escribe el guion con una IA gratuita; una segunda pasada comprueba los datos."""
import json
import os
import re
import time
import requests

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre']


def llm(mensajes, temperatura=0.7):
    """Gemini (plan gratuito, clave GEMINI_API_KEY); si no, Groq; si no, Pollinations (gratis sin clave)."""
    if os.environ.get('GEMINI_API_KEY'):
        url, cab = ('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
                    {'Authorization': f"Bearer {os.environ['GEMINI_API_KEY']}"})
        cuerpo = {'model': os.environ.get('NUTRIA_MODELO', 'gemini-2.5-flash'), 'messages': mensajes,
                  'temperature': temperatura, 'response_format': {'type': 'json_object'}}
    elif os.environ.get('GROQ_API_KEY'):
        url, cab = 'https://api.groq.com/openai/v1/chat/completions', {'Authorization': f"Bearer {os.environ['GROQ_API_KEY']}"}
        cuerpo = {'model': 'llama-3.3-70b-versatile', 'messages': mensajes, 'temperature': temperatura,
                  'response_format': {'type': 'json_object'}}
    else:
        url, cab = 'https://text.pollinations.ai/openai', {}
        cuerpo = {'model': 'openai', 'messages': mensajes, 'response_format': {'type': 'json_object'}}
    ultimo = None
    for i in range(6):
        try:
            r = requests.post(url, json=cuerpo, headers=cab, timeout=120)
            if r.status_code == 200:
                try:
                    t = r.json()['choices'][0]['message']['content']
                    return json.loads(t[t.index('{'):t.rindex('}') + 1])
                except (ValueError, KeyError, IndexError, TypeError):
                    ultimo = f'200 con respuesta rara: {r.text[:300]!r}'
                    print('  IA:', ultimo, flush=True)
            else:
                ultimo = f'{r.status_code} {r.text[:300]}'
                print('  IA:', ultimo, flush=True)
        except (requests.RequestException, ValueError, KeyError) as e:
            ultimo = repr(e)
        time.sleep(min(60, 15 * (i + 1)))
    raise RuntimeError(f'La IA no responde: {ultimo}')


SISTEMA = """Eres el guionista de «La Nutria Roja», un canal de vídeos cortos (TikTok, Reels, Shorts) en español de España sobre lo que pasó un día como hoy en la historia.
Estilo: cercano, con ritmo, frases cortas, curiosidad. Nada de sensacionalismo ni de opiniones políticas.
REGLAS DE ORO:
1. Solo puedes usar datos que aparezcan en el TEXTO FUENTE. Si un dato no está, no lo pongas. Nada de cifras, citas ni detalles inventados.
2. La primera frase de "frases" empieza EXACTAMENTE por "Un día como hoy, {dia} de {mes} de <AÑO>," con el año del hecho.
3. Nunca numeres días ("día 1", "día 2"...).
4. Escribe los números grandes como se dicen si es natural; los años, en cifras.
Responde SOLO con JSON."""

FORMATO = """Devuelve este JSON:
{{
 "gancho": "frase de 6 a 12 palabras que haga parar el dedo, intrigante, sin revelar todo (no empieces por 'Un día como hoy')",
 "frases": ["Un día como hoy, {dia} de {mes} de AAAA, ...", "...", "..."],   // 4 a 6 frases, en total 60 a 90 palabras, incluye 1 o 2 curiosidades sorprendentes del texto fuente
 "pregunta": "pregunta final corta para que comenten",
 "titulo": "título para YouTube Shorts, máximo 70 caracteres, con gancho y 1 emoji",
 "descripcion": "texto para la publicación: 1-2 frases con gancho + 4 o 5 hashtags en español (#historia #undiacomohoy #curiosidades + 1-2 del tema)",
 "busquedas": ["3 búsquedas EN INGLÉS para encontrar fotos reales del tema en Wikimedia Commons, concretas (personas, lugares, objetos, año)"]
}}"""


def elegir(candidatos, dia, mes, evitar_temas):
    lista = '\n'.join(f"#{c['id']} ({c['año']}){' [destacado]' if c['destacado'] else ''}: {c['texto']}"
                      for c in candidatos[:30])
    r = llm([
        {'role': 'system', 'content': 'Eres editor de un canal de historia en vídeos cortos para público español joven. Responde solo JSON.'},
        {'role': 'user', 'content': f"Hechos del {dia} de {MESES[mes - 1]}:\n{lista}\n\nElige los 3 con más potencial viral y visual "
                                   f"(sorprendentes, conocidos o curiosos; evita tragedias con muchas víctimas, política actual divisiva y temas ya usados esta semana: {', '.join(evitar_temas) or 'ninguno'}). "
                                   'Responde {"ids":[id1,id2,id3]} en orden de preferencia.'},
    ], temperatura=0.4)
    ids = [int(i) for i in r.get('ids', []) if str(i).isdigit() or isinstance(i, int)]
    return [c for i in ids for c in candidatos if c['id'] == i] or candidatos[:3]


def escribir(hecho, fuente, dia, mes):
    m = MESES[mes - 1]
    sistema = SISTEMA.format(dia=dia, mes=m)
    usuario = (f"HECHO ({hecho['año']}): {hecho['texto']}\n\nTEXTO FUENTE (Wikipedia):\n{fuente}\n\n"
               + FORMATO.format(dia=dia, mes=m))
    g = llm([{'role': 'system', 'content': sistema}, {'role': 'user', 'content': usuario}])
    validar(g, hecho, dia, m)
    return g


def validar(g, hecho, dia, m):
    for k in ('gancho', 'frases', 'pregunta', 'titulo', 'descripcion', 'busquedas'):
        if not g.get(k):
            raise ValueError(f'Falta «{k}» en el guion')
    cab = f"Un día como hoy, {dia} de {m} de {hecho['año']},"
    if not g['frases'][0].startswith(cab):
        raise ValueError(f'La primera frase no empieza por «{cab}»: {g["frases"][0][:80]}')
    todo = ' '.join([g['gancho'], *g['frases'], g['pregunta']])
    if re.search(r'\bd[ií]a\s+\d\b', todo.replace(cab, '')):
        raise ValueError('Numera los días')
    n = len(todo.split())
    if not 55 <= n <= 125:
        raise ValueError(f'Longitud rara: {n} palabras')
    if len(g['titulo']) > 95:
        g['titulo'] = g['titulo'][:92].rstrip() + '…'


def verificar(g, fuente, hecho):
    """Segunda IA: ¿todo lo que dice el guion está en la fuente?"""
    texto = '\n'.join([g['gancho'], *g['frases'], g['pregunta'], g['titulo'], g['descripcion']])
    r = llm([
        {'role': 'system', 'content': 'Eres un verificador de datos estricto. Responde solo JSON.'},
        {'role': 'user', 'content': f"FUENTE:\nHecho ({hecho['año']}): {hecho['texto']}\n{fuente}\n\nGUION:\n{texto}\n\n"
                                   'Lista cada afirmación factual del guion (fechas, cifras, nombres, causas, superlativos) que NO esté respaldada por la fuente. '
                                   'Las frases de estilo, preguntas y ganchos sin datos no cuentan. '
                                   'Responde {"inventado": ["..."], "ok": true|false} (ok=true solo si la lista está vacía).'},
    ], temperatura=0)
    malos = [x for x in r.get('inventado', []) if x]
    return (bool(r.get('ok')) and not malos), malos

"""Elige el hecho del día y escribe el guion con una IA gratuita; una segunda pasada comprueba los datos."""
import json
import os
import re
import time
import requests

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre']


_MODELOS_GEMINI = {}


def _claves_gemini(rol='escribir'):
    """Reparto de trabajo entre cuentas de Google (cada una con su cupo):
    - escribir el guion: clave 2 (cuenta personal) → clave 3 → Nutria
    - elegir / revisar:  clave 3 → clave 2 → Nutria
    La de la Nutria (GEMINI_API_KEY) solo entra si las otras fallan."""
    e = os.environ.get
    orden = [e('GEMINI_API_KEY_2'), e('GEMINI_API_KEY_3')] if rol == 'escribir' else [e('GEMINI_API_KEY_3'), e('GEMINI_API_KEY_2')]
    return list(dict.fromkeys(k for k in orden + [e('GEMINI_API_KEY')] if k))


def _modelos_gemini(clave):
    """Modelos «flash» que la clave puede usar ahora mismo, del preferido al de reserva (cada uno tiene su propio cupo gratis)."""
    if clave in _MODELOS_GEMINI:
        return _MODELOS_GEMINI[clave]
    pref = [m for m in [os.environ.get('NUTRIA_MODELO'), 'gemini-3.8-flash', 'gemini-flash-latest',
                        'gemini-flash-lite-latest'] if m]
    hay = []
    try:
        r = requests.get('https://generativelanguage.googleapis.com/v1beta/models',
                         params={'key': clave, 'pageSize': 200}, timeout=30)
        for m in r.json().get('models', []):
            n = m['name'].split('/')[-1]
            if 'generateContent' in m.get('supportedGenerationMethods', []) and ('flash' in n or n.startswith('gemma')) \
                    and not re.search(r'(image|tts|audio|live|exp|preview|thinking|embed|-e\d|-1b|-4b)', n):
                hay.append(n)
    except Exception as e:
        print('  IA: no pude listar los modelos de Gemini:', repr(e)[:120], flush=True)
    flash = sorted([n for n in hay if 'flash' in n], key=lambda n: [int(x) for x in re.findall(r'\d+', n)], reverse=True)
    gemma = sorted([n for n in hay if n.startswith('gemma')], key=lambda n: [int(x) for x in re.findall(r'\d+', n)], reverse=True)
    _MODELOS_GEMINI[clave] = list(dict.fromkeys(pref + flash))[:7] + gemma[:2]
    print('  IA: modelos Gemini en rotación:', ', '.join(_MODELOS_GEMINI[clave]), flush=True)
    return _MODELOS_GEMINI[clave]


def _proveedores(mensajes, temperatura, rol='escribir'):
    rf = {'type': 'json_object'}
    for clave in _claves_gemini(rol):
        n = {os.environ.get('GEMINI_API_KEY_2'): 'personal', os.environ.get('GEMINI_API_KEY_3'): 'clave3'}.get(clave, 'nutria')
        modelos = _modelos_gemini(clave)
        if rol != 'escribir':   # cadena: el que escribe usa los modelos grandes; el que revisa/elige, los «lite» primero
            modelos = sorted(modelos, key=lambda x: 'lite' not in x)
        for m in modelos:
            cuerpo = {'model': m, 'messages': mensajes, 'temperature': temperatura}
            if not m.startswith('gemma'):
                cuerpo['response_format'] = rf
            yield (f'{n}:{m}', 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
                   {'Authorization': f"Bearer {clave}"}, cuerpo)
    if os.environ.get('GROQ_API_KEY'):
        yield ('groq', 'https://api.groq.com/openai/v1/chat/completions', {'Authorization': f"Bearer {os.environ['GROQ_API_KEY']}"},
               {'model': 'llama-3.3-70b-versatile', 'messages': mensajes, 'temperature': temperatura, 'response_format': rf})
    yield ('pollinations', 'https://text.pollinations.ai/openai', {},
           {'model': 'openai', 'messages': mensajes, 'response_format': rf, 'max_tokens': 8000})


_AGOTADOS = set()   # modelos que ya han dicho «sin cupo» en esta ejecución


def llm(mensajes, temperatura=0.7, rol='escribir', espera=120, vision=False):
    """Prueba los modelos gratuitos por turnos: si uno está saturado (503), sin cupo (429) o retirado (404),
    pasa al siguiente al momento. Hasta 3 vueltas completas con pausas crecientes."""
    ultimo = None
    for vuelta in range(5):
        for nombre, url, cab, cuerpo in _proveedores(mensajes, temperatura, rol):
            if nombre in _AGOTADOS or (vision and (nombre in ('groq', 'pollinations') or 'gemma' in nombre)):
                continue
            try:
                r = requests.post(url, json=cuerpo, headers=cab, timeout=espera)
                if r.status_code == 200:
                    try:
                        t = r.json()['choices'][0]['message']['content']
                        return json.loads(t[t.index('{'):t.rindex('}') + 1])
                    except (ValueError, KeyError, IndexError, TypeError):
                        ultimo = f'{nombre}: respuesta rara {r.text[:150]!r}'
                else:
                    ultimo = f'{nombre}: {r.status_code} {r.text[:160]}'
                    if r.status_code in (404, 400) or (r.status_code == 429 and 'quota' in r.text.lower()):
                        _AGOTADOS.add(nombre)
            except requests.RequestException as e:
                ultimo = f'{nombre}: {e!r}'[:200]
            print('  IA:', ultimo.replace('\n', ' '), flush=True)
            time.sleep(3)
        time.sleep(30 * (vuelta + 1))
    raise RuntimeError(f'Ninguna IA responde: {ultimo}')


SISTEMA = """Eres el guionista de «La Nutria Roja», un canal de vídeos cortos (TikTok, Reels, Shorts) en español de España sobre lo que pasó un día como hoy en la historia.
Estilo: cercano, con ritmo, frases cortas, curiosidad. Nada de sensacionalismo ni de opiniones políticas.
QUE SUENE A PERSONA, NO A IA (muy importante):
- Escribe como alguien que se lo cuenta a un amigo en un bar: natural, directo, con algún giro coloquial de España ("ojo", "lo mejor viene ahora", "y aquí viene lo curioso") pero sin pasarte.
- PROHIBIDO: "¡Increíble!", "¿Sabías que...?" como muletilla, "sumérgete", "fascinante", "en un mundo donde", "no te lo vas a creer", "épico", "un hito sin precedentes", enumeraciones de tres adjetivos, frases que empiezan por "En resumen".
- Varía la forma de empezar el gancho cada vez (una pregunta, una imagen, un dato, una contradicción). Nada de fórmulas repetidas.
- Nada de rayas largas (—) ni de exclamaciones seguidas. Como mucho 1 emoji en el título y 1 en la descripción.
- La pregunta final tiene que ser una pregunta de verdad que apetezca contestar (opinión o experiencia), no "¿qué opinas?" a secas.
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
 "titulo": "título para YouTube Shorts, máximo 70 caracteres, que alguien buscaría o en el que haría clic (incluye el tema y el año), como mucho 1 emoji",
 "descripcion": "texto para la publicación: primera línea con la palabra clave del tema y gancho, segunda línea con un dato extra breve, y al final 4 o 5 hashtags en español: #historia #undiacomohoy #curiosidades + 1 o 2 concretos del tema (persona, lugar o acontecimiento)",
 "busquedas": ["3 búsquedas EN INGLÉS para encontrar fotos reales del tema en Wikimedia Commons, concretas (personas, lugares, objetos, año)"]
}}"""


def elegir(candidatos, dia, mes, evitar_temas):
    try:
        return _elegir(candidatos, dia, mes, evitar_temas)
    except Exception as e:
        print('  elegir sin IA:', str(e)[:120], flush=True)
        return [c for c in candidatos if c['destacado']][:3] or candidatos[:3]


def _elegir(candidatos, dia, mes, evitar_temas):
    lista = '\n'.join(f"#{c['id']} ({c['año']}){' [destacado]' if c['destacado'] else ''}: {c['texto']}"
                      for c in candidatos[:30])
    r = llm([
        {'role': 'system', 'content': 'Eres editor de un canal de historia en vídeos cortos para público español joven. Responde solo JSON.'},
        {'role': 'user', 'content': f"Hechos del {dia} de {MESES[mes - 1]}:\n{lista}\n\nElige los 3 con más potencial viral y visual "
                                   f"(sorprendentes, conocidos o curiosos; evita tragedias con muchas víctimas, política actual divisiva y temas ya usados esta semana: {', '.join(evitar_temas) or 'ninguno'}). "
                                   'Responde {"ids":[id1,id2,id3]} en orden de preferencia.'},
    ], temperatura=0.4, rol='elegir')
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
    ], temperatura=0, rol='verificar')
    malos = [x for x in r.get('inventado', []) if x]
    return (bool(r.get('ok')) and not malos), malos

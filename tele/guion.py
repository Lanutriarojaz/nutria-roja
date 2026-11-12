"""El guionista de Tele-Dimensional: una IA gratuita escribe el episodio a partir del sorteo, otra lo puntúa y,
si flojea, se reescribe una vez. Todo se valida antes de dibujar nada."""
import json
import os
import re

from nutria.guion import llm
from .audio import EFECTOS
from .catalogo import ELEMENTOS, FORMATOS, VOCES, libre, nombre

EMOCIONES = ('neutral', 'enfado', 'sorpresa', 'miedo', 'risa', 'triste')
VOCES_PERSONAJE = [v for v in VOCES if v not in ('locutor', 'presentador_canal')]

ESTILO_VISUAL = ('animación 2D original de trazo grueso, ciencia ficción retro, plató de televisión interdimensional, colores '
                 'intensos y contrastados, personajes expresivos y ligeramente grotescos, interferencias de señal, decorado '
                 'imposible, formato vertical 9:16, sin texto ni letras en la imagen')

MUSICAS = ('normal', 'tension', 'silencio', 'triunfo')

SISTEMA = """Eres el guionista jefe de TELE-DIMENSIONAL, una serie de vídeos de un minuto (TikTok, Reels, Shorts) en español de España.
Es un canal de televisión ficticio que emite desde universos alternativos. Cada episodio es un programa de tele distinto.

TONO: ciencia ficción absurda para adultos. Humor seco, sátira de la tele y de la vida cotidiana, dilemas existenciales
tratados como un trámite. Los personajes se toman lo absurdo completamente en serio. Nunca se explica el chiste.
ORIGINALIDAD: todo inventado. Prohibido copiar o aludir a personajes, frases, nombres o mundos de series, películas o marcas
que existan. Sin personas reales, sin política actual, sin religiones concretas, sin sexo ni insultos fuertes.

LO MÁS IMPORTANTE: QUE SE ENTIENDA A LA PRIMERA.
Quien lo ve no sabe nada y solo tiene un minuto. Por eso el episodio cuenta UNA sola cosa, que se pueda resumir así:
«X quiere Y, pero Z». Si necesitas más de una frase para resumirlo, simplifica. Mejor una idea clara que tres ingeniosas.

ESTRUCTURA OBLIGATORIA (una escena por paso, o dos en la escalada):
1. GANCHO (1 o 2 frases): una situación imposible dicha como si fuera rutina. Máximo 12 palabras la primera.
   (Justo después el canal mete solo su cortinilla; no la escribas.)
2. PLANTEAMIENTO: queda clarísimo quién quiere qué, qué se lo impide y cuál es la regla rara de este mundo. Dilo con palabras
   sencillas, por boca de los personajes. Sin esto, lo demás no funciona.
3. ESCALADA (1 o 2 escenas, musica "tension"): intentan resolverlo y cada intento lo empeora. Aquí van las réplicas rápidas.
4. CLÍMAX (musica "silencio"): el momento de decidir. Frases cortísimas, una "pausa" antes de la frase clave. Que se pueda cortar el aire.
5. GIRO: la última frase lo cambia todo y ES el concepto filosófico hecho chiste. Márcala con "golpe": true. Mejor si cierra
   el círculo con el gancho (misma frase, otro significado), para que el vídeo se pueda ver en bucle.

DIÁLOGO NATURAL (lo segundo más importante):
- Es una CONVERSACIÓN, no turnos de monólogo. Los personajes se contestan, se interrumpen, repiten incrédulos lo que acaban de oír
  («¿Cómo que un lunar?»), dudan («A ver, a ver…»), se corrigen, sueltan una sola palabra («Ya.» «¿Perdón?» «Supongo.»).
- Mezcla frases de una a cinco palabras con alguna más larga. Ninguna pasa de 15 palabras.
- Cada personaje habla distinto: uno pedante, otra seca, otro nervioso. Que se note quién habla sin mirar.
- Nadie describe lo que ya se ve ni cuenta la trama. El narrador como mucho abre, sitúa y cierra (máximo 3 frases suyas).
- Que suene a gente hablando en España, no a texto: «pues», «a ver», «hombre», «oiga». Nada de «fascinante», «increíble»,
  «en un mundo donde», ni moralejas.

OTRAS REGLAS:
- Los tres elementos del sorteo son IMPRESCINDIBLES para la trama: si quitas uno, la historia se cae. Lo normal es que sean los
  personajes (objetos y animales que hablan) o el objeto que todos quieren.
- El concepto filosófico no se nombra nunca: se vive.
- El mundo es absurdo pero tiene una regla, y se respeta hasta el final.
- Nombres de personaje inventados, sonoros y fáciles de pronunciar. Números con letras. No numeres episodios.

RECURSOS DE REALIZACIÓN (úsalos con intención, como un realizador de tele):
- "musica" por escena: "normal" (fondo ligero), "tension" (pulso que aprieta), "silencio" (se corta la música: clímax), "triunfo".
- "pausa" en una línea: segundos de silencio ANTES de decirla (0.3 a 1.0). Para que un chiste respire o una decisión pese.
- "golpe": true en una línea: mazazo sonoro, zoom y fogonazo. Solo en 1 o 2 momentos del episodio (el giro siempre).
- "sello": una o dos palabras que se estampan en pantalla con el golpe («¿CÓMO?», «EMPATE», «ZAS»).
Responde SOLO con JSON."""

PLANTILLA = """SORTEO DE HOY (no lo cambies):
- Elementos cotidianos: {elementos}
- Concepto filosófico: {concepto} — {idea}
- Programa de tele: {genero} (plató: {plato})
- Conflicto: {conflicto}{opcionales}

CUERPOS DE LOS PERSONAJES: "cuerpo" puede ser un dibujo de esta lista (identificador exacto) o CUALQUIER otra palabra
(una sola, en minúsculas: «patrocinador», «alienigena», «vecina»…), que se dibuja como criatura de cartoon:
{ids}
"prop" (objeto que se enseña flotando) solo puede ser uno de esa lista, o null.
Los tres elementos del sorteo tienen estos identificadores: {ids_sorteo}. Cada uno debe aparecer como "cuerpo" de un personaje
o como "prop" de alguna escena.

VOCES disponibles para "voz" (una distinta por personaje): {voces}
"quien" de cada línea es el id de un personaje o "narrador" (la voz en off del canal).
EFECTOS para "sfx" (suenan al arrancar la escena): {efectos} (o null).
EMOCIONES para "emocion": {emociones}.

Devuelve este JSON:
{{
 "resumen": "X quiere Y, pero Z (una sola frase; si no cabe, simplifica la historia)",
 "titulo": "título del episodio, con gracia, máximo 45 caracteres",
 "titulo_corto": "título para TikTok/Reels/Shorts, máximo 55 caracteres, que dé ganas de pulsar, como mucho 1 emoji",
 "premisa": "la premisa en dos frases",
 "personajes": [{{"id": "corto_sin_espacios", "nombre": "Nombre inventado", "cuerpo": "identificador de dibujo", "personalidad": "una frase, con su manera de hablar", "voz": "una de las voces",
   "aspecto": "IN ENGLISH, 25-45 words: what this character looks like for an illustrator (species or object, body shape, face, clothes, colours, one memorable absurd detail). Make each character very different from the others"}}],
 "escenas": [
  {{"plano": "qué se ve y qué pasa en esta escena (una idea visual clara)",
    "decorado": "IN ENGLISH, 25-50 words: the empty background set of this scene for an illustrator, faithful to the TV genre (a cooking show looks like a real cooking show set, a newscast like a news desk, a trial like a courtroom...) but twisted by the alternate universe. Reuse the same text in scenes that happen in the same place",
    "rotulo": "texto del faldón en pantalla, máximo 30 caracteres, que ayude a seguir la historia",
    "musica": "normal | tension | silencio | triunfo",
    "sfx": "efecto o null",
    "prop": "identificador del objeto que se enseña en esta escena o null",
    "presentes": ["ids de personajes que están en el plató en esta escena aunque no hablen (opcional)"],
    "lineas": [{{"quien": "id o narrador", "texto": "frase", "emocion": "...", "pausa": 0, "golpe": false, "sello": ""}}],
    "prompt_visual": "prompt en español para generar este plano con una IA de imagen: personajes, acción, decorado, encuadre y luz (sin texto en la imagen)",
    "movimiento": "indicación de movimiento para convertir esa imagen en vídeo (cámara y acción, 1 frase)"}}
 ],
 "giro": "el giro final en una frase",
 "relacion": "por qué ese giro ES el concepto filosófico, en 1 o 2 frases",
 "descripcion": "texto de la publicación: 2 líneas con gancho y una pregunta final que apetezca contestar, sin hashtags",
 "hashtags": ["5 hashtags en español, sin espacios, el primero #teledimensional"]
}}
LÍMITES: 2 o 3 personajes; 5 o 6 escenas; de 1 a 6 líneas por escena; de 16 a 24 líneas en total; entre 130 y 170 palabras
de diálogo en total. La primera línea de la primera escena es el gancho. La última línea lleva "golpe": true."""


def _ejemplo():
    """El guion del piloto, en corto, como muestra de ritmo, longitud y diálogo."""
    try:
        d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'piloto.json')))['guion']
    except (OSError, ValueError, KeyError):
        return ''
    nombres = {p['id']: p['nombre'] for p in d['personajes']}
    L = [f"EJEMPLO DEL NIVEL QUE SE ESPERA (es OTRO sorteo: no copies la historia, fíjate en el ritmo, la longitud, "
         f"cómo se plantea el problema y cómo se contestan). «{d['titulo']}». Resumen: {d['resumen']}"]
    for i, e in enumerate(d['escenas'], 1):
        L.append(f"Escena {i} (música {e.get('musica', 'normal')}):")
        for l in e['lineas']:
            marca = (f" [pausa {l['pausa']}]" if l.get('pausa') else '') + (f" [GOLPE «{l['sello']}»]" if l.get('golpe') else '')
            L.append(f"  {nombres.get(l['quien'], 'Narrador')}{marca}: {l['texto']}")
    L.append(f"Giro: {d['giro']}")
    return '\n'.join(L) + '\n\n'


def _opcionales(s):
    t = ''
    if s.get('idea'):
        i = s['idea']
        t += ("\n\nIDEA DE LA SEMANA (la ha pensado el jefe de ideas: desarróllala tal cual, respetando premisa, chiste y giro; "
              "tú pones el diálogo, el ritmo y los recursos):"
              + (f"\n- Título provisional: {i['titulo']}" if i.get('titulo') else '')
              + f"\n- Premisa: {i.get('premisa', '')}\n- Chiste central: {i.get('chiste', '')}\n- Giro final: {i.get('giro', '')}"
              + (f"\n- Gancho (primera frase): {i['gancho']}" if i.get('gancho') else '')
              + (f"\n- Protagonista: {i['protagonista']}" if i.get('protagonista') else '')
              + (f"\n- Desarrollo previsto: {i['desarrollo']}" if i.get('desarrollo') else '')
              + (f"\n- Tono y género: {i['genero']}" if i.get('genero') else '')
              + (f"\n- Formato original de la idea: {i['formato_texto']} (adáptalo al programa de tele indicado)" if i.get('formato_texto') else '')
              + (f"\n- Imagen que tiene en la cabeza: {i['audiovisual']}" if i.get('audiovisual') else ''))
    if s.get('contexto'):
        t += f"\n- Universo donde pasa todo: {s['contexto']}"
    if s.get('fijo'):
        q = s['fijo']
        t += (f"\n- Personaje fijo de la serie que DEBE salir (con este mismo id, nombre, cuerpo y voz): "
              f"id \"{q.get('id', q['nombre'].split()[0].lower())}\", nombre \"{q['nombre']}\", cuerpo \"{q['cuerpo']}\", "
              f"voz \"{q.get('voz', '')}\". Personalidad: {q.get('personalidad', '')}")
    return t


def _sin_sorteo(texto, s):
    """Si la idea no trae objetos o concepto, se quitan esas exigencias del encargo."""
    if not s['elementos']:
        texto = re.sub(r'- Elementos cotidianos:.*', '- Elementos cotidianos: los que salgan de la idea (personajes con cualquier palabra)', texto)
        texto = re.sub(r'Los tres elementos del sorteo tienen estos identificadores:.*?alguna escena\.', '', texto, flags=re.S)
    if not s.get('concepto'):
        texto = re.sub(r'- Concepto filosófico:.*', '- Concepto filosófico: el que ya lleva dentro la idea; no añadas otro', texto)
    return texto


def _pedir(s, extra=''):
    f = FORMATOS[s['formato']]
    usuario = PLANTILLA.format(
        elementos=', '.join(nombre(e) for e in s['elementos']), concepto=s['concepto'], idea=s['concepto_idea'],
        genero=f[0], plato=f[1], conflicto=s['conflicto'], opcionales=_opcionales(s), ids=', '.join(ELEMENTOS), ids_sorteo=', '.join(s['elementos']),
        voces=', '.join(f'{v} ({VOCES[v][3]})' for v in VOCES_PERSONAJE), efectos=', '.join(EFECTOS),
        emociones=', '.join(EMOCIONES))
    usuario = _sin_sorteo(usuario, s) + extra
    return llm([{'role': 'system', 'content': SISTEMA}, {'role': 'user', 'content': _ejemplo() + usuario}], temperatura=1.0, espera=300)


def _palabras(g):
    return sum(len(l['texto'].split()) for e in g['escenas'] for l in e['lineas'])


def validar(g, s, min_lineas=12, min_palabras=110):
    """Corrige lo que se puede corregir solo y lanza ValueError si el guion no sirve."""
    for k in ('titulo', 'premisa', 'personajes', 'escenas', 'giro', 'descripcion'):
        if not g.get(k):
            raise ValueError(f'falta «{k}»')
    pers = g['personajes']
    if not 2 <= len(pers) <= 3:
        raise ValueError(f'{len(pers)} personajes')
    libres = [v for v in VOCES_PERSONAJE if v not in {p.get('voz') for p in pers}]
    vistos, ids = set(), set()
    for p in pers:
        p['id'] = re.sub(r'\W+', '_', str(p.get('id') or p.get('nombre', ''))).strip('_').lower()
        if not p['id'] or p['id'] in ids or p['id'] == 'narrador' or not p.get('nombre'):
            raise ValueError('personaje sin id o repetido')
        ids.add(p['id'])
        p['cuerpo'] = libre(p.get('cuerpo') or p['nombre'])      # cualquier palabra vale: se dibuja como criatura
        if p.get('voz') not in VOCES_PERSONAJE or p['voz'] in vistos:
            p['voz'] = libres.pop(0)
        vistos.add(p['voz'])
        p.setdefault('personalidad', '')
        p['aspecto'] = str(p.get('aspecto') or '')[:400]
    esc = g['escenas']
    if not 3 <= len(esc) <= 6:
        raise ValueError(f'{len(esc)} escenas')
    for e in esc:
        if not e.get('lineas') or len(e['lineas']) > 7:
            raise ValueError('escena sin líneas o con demasiadas')
        e['sfx'] = e.get('sfx') if e.get('sfx') in EFECTOS else None
        e['musica'] = e.get('musica') if e.get('musica') in MUSICAS else 'normal'
        e['prop'] = libre(e['prop']) if e.get('prop') else None
        e['prop'] = e['prop'] if e['prop'] in ELEMENTOS else None
        e['rotulo'] = str(e.get('rotulo') or g['titulo'])[:44]
        for k in ('plano', 'prompt_visual', 'movimiento', 'decorado'):
            e[k] = str(e.get(k) or '')
        for l in e['lineas']:
            l['quien'] = str(l.get('quien', '')).lower()
            if l['quien'] not in ids and l['quien'] != 'narrador':
                raise ValueError(f"habla alguien que no existe: {l['quien']}")
            l['texto'] = re.sub(r'\s+', ' ', str(l.get('texto', '')).replace('—', ',').replace('*', '')).strip()
            if not 1 <= len(l['texto'].split()) <= 20:
                raise ValueError(f"línea vacía o larguísima: {l['texto'][:50]}")
            l['emocion'] = l.get('emocion') if l.get('emocion') in EMOCIONES else 'neutral'
            try:
                l['pausa'] = min(max(float(l.get('pausa') or 0), 0), 1.2)
            except (TypeError, ValueError):
                l['pausa'] = 0
            l['golpe'] = bool(l.get('golpe')) and l.get('golpe') not in ('false', 'False')
            l['sello'] = str(l.get('sello') or '').strip()[:14] if l['golpe'] else ''
    todas = [l for e in esc for l in e['lineas']]
    todas[-1]['golpe'] = True
    for l in [l for l in todas if l['golpe']][:-1][2:]:        # como mucho tres golpes, contando el del giro
        l['golpe'], l['sello'] = False, ''
    if len(todas) < min_lineas:
        raise ValueError(f'solo {len(todas)} líneas: falta conversación (deben ser 16-24)')
    if sum(l['quien'] == 'narrador' for l in todas) > 4:
        raise ValueError('el narrador habla demasiado: la historia la llevan los personajes')
    n = _palabras(g)
    if not min_palabras <= n <= 185:
        raise ValueError(f'{n} palabras de diálogo (deben ser 130-170)')
    usados = {p['cuerpo'] for p in pers} | {e['prop'] for e in esc}
    faltan = [x for x in s['elementos'] if x not in usados]
    if faltan:
        raise ValueError(f'elementos del sorteo que no se ven: {faltan}')
    mudos = ids - {l['quien'] for e in esc for l in e['lineas']}
    if mudos:
        raise ValueError(f'personajes que no hablan: {mudos}')
    g['titulo'] = g['titulo'][:80]
    g['titulo_corto'] = str(g.get('titulo_corto') or g['titulo'])[:70]
    hs = ['#' + re.sub(r'[^\wáéíóúñü]', '', str(h).lstrip('#').lower()) for h in (g.get('hashtags') or [])]
    hs = list(dict.fromkeys(['#teledimensional'] + [h for h in hs if len(h) > 2]))
    g['hashtags'] = (hs + ['#humorabsurdo', '#cienciaficcion', '#filosofia', '#animacion'])[:5]
    g.setdefault('relacion', '')
    return g


def revisar(g, s):
    """Segunda IA, con otro modelo: puntúa el episodio como jefe de guion."""
    texto = '\n'.join(f"[{e['rotulo']}] " + ' / '.join(f"{l['quien']}: {l['texto']}" for l in e['lineas']) for e in g['escenas'])
    try:
        r = llm([
            {'role': 'system', 'content': 'Eres un jefe de guion de comedia muy exigente. Responde solo JSON.'},
            {'role': 'user', 'content': f"Serie de humor absurdo de ciencia ficción en vídeos de un minuto.\nElementos obligatorios: "
             f"{', '.join(nombre(e) for e in s['elementos'])}. Concepto: {s['concepto']} ({s['concepto_idea']}). "
             f"Programa: {FORMATOS[s['formato']][0]}.\n\nGUION:\n{texto}\n\nGiro: {g['giro']}\n\n"
             'Puntúa de 1 a 10, siendo duro. Lo primero: ¿alguien que no sabe nada entiende en el primer tercio quién quiere qué y '
             'qué se lo impide? Si no, la nota no pasa de 5. Después: ¿hay tensión que sube hasta el final?, ¿el diálogo suena a '
             'conversación de verdad (réplicas, interrupciones, frases cortas) o a monólogos por turnos?, ¿la primera frase engancha?, '
             '¿los tres elementos son imprescindibles?, ¿el giro sorprende y encaja con el concepto?, ¿tiene gracia? '
             'Responde {"nota": n, "fallos": ["lo que hay que arreglar, concreto"]}'},
        ], temperatura=0.2, rol='verificar')
        return float(r.get('nota', 7)), [str(x) for x in r.get('fallos', [])][:5]
    except Exception as e:
        print('  revisión no disponible:', str(e)[:100], flush=True)
        return 7.0, []


def escribir(s):
    errores, mejor = [], None
    extra = ''
    for intento in range(5):
        try:
            g = validar(_pedir(s, extra), s)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            errores.append(str(e)); extra = f'\n\nTu intento anterior no valía: {e}. Corrígelo.'
            print('  guion rechazado:', e, flush=True); continue
        nota, fallos = revisar(g, s)
        print(f"  guion «{g['titulo']}»: nota {nota}", flush=True)
        g['nota'] = nota
        if mejor is None or nota > mejor['nota']:
            mejor = g
        if nota >= 7.5:
            break
        extra = ('\n\nUn jefe de guion ha leído tu versión anterior y pide arreglar esto:\n- ' + '\n- '.join(fallos) +
                 '\nEscribe una versión nueva y mejor (puedes cambiar la historia entera).')
    if mejor is None:
        raise RuntimeError('No ha salido ningún guion válido: ' + ' | '.join(errores[-3:]))
    return mejor

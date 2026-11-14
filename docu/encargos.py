"""Microdocumentales de La Nutria Roja: encargos para ChatGPT y guiones recibidos.
1) preparar: el domingo deja un encargo por cada día de publicación (lunes, miércoles, viernes) en docu/encargos/N.txt,
   con la lista de temas ya hechos para que no se repitan.
2) guardar: el atajo del iPhone devuelve cada guion (con su "fecha") → docu/guiones/FECHA.json (si pasa la validación).
3) escribir: reserva con Gemini si ese día no llegó guion de ChatGPT.
Uso: python -m docu.encargos preparar [--desde AAAA-MM-DD]  |  python -m docu.encargos guardar < respuesta"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ENCARGOS = os.path.join(AQUI, 'encargos')
GUIONES = os.path.join(AQUI, 'guiones')
HISTORIAL = os.path.join(AQUI, 'historial.json')
DIAS_PUBLICACION = (0, 2, 4)          # lunes, miércoles, viernes
AREAS = ['CIELO, CLIMA Y ESPACIO (tormentas, nubes, auroras, Luna, Sol, estrellas, Tierra desde el espacio)',
         'ANIMALES (salvajes, marinos, aves, insectos: comportamientos y adaptaciones sorprendentes)',
         'PLANETA (océano, hielo, volcanes, desiertos, ríos, bosques, plantas)']

PLANTILLA = """Eres el guionista jefe de LA NUTRIA ROJA, canal de microdocumentales verticales (YouTube Shorts, TikTok, Reels).
Eslogan: «Lo extraordinario está más cerca de lo que crees». Narra una voz de mujer: neutra, dinámica, cercana y rigurosa. Español de España.
Este guion se publica el {fecha_txt}.

ÁREA DE ESTE GUION: {area}. Elige un tema de esa área.
NADA de historia, guerras, biografías ni política. Debe ser cierto, verificable y explicable en menos de un minuto. Una sola idea.

EL VÍDEO SE MONTA CON PLANOS DE UN BANCO DE VÍDEO GRATIS (Pixabay). Tiene mucho y bueno de: paisajes, montañas, glaciares, hielo, nieve, océano, olas,
cascadas, ríos, desiertos, bosques, volcanes, tormentas, rayos, nubes, auroras, cielo nocturno, Tierra desde el espacio, Luna, Sol, animales salvajes y
marinos, aves, insectos en macro, flores y plantas (timelapse). NO tiene objetos domésticos concretos, laboratorios, gráficos ni personas haciendo
acciones concretas: no elijas temas que los necesiten. Cada escena debe poder ilustrarse con un plano genérico de esa lista.

TEMAS YA HECHOS (no repitas ninguno ni algo parecido): {excluidos}

ESTRUCTURA OBLIGATORIA:
- La PRIMERA frase de la escena 1 es LA PREGUNTA que responde el vídeo, dicha tal cual (ej.: «¿Por qué el hielo de los glaciares es azul?»). Luego un remate corto que enganche.
- Después, la explicación clara, escena a escena, y al final una revelación o conclusión satisfactoria.
- Que suene a persona, no a IA: nada de «¿sabías que…?», «increíble», «fascinante», «sumérgete», rayas largas (—). Sin «comenta abajo».

Devuelve SOLO este JSON válido, sin texto fuera ni ```:
{{
 "fecha": "{fecha}",
 "topic_id": "slug-unico-del-tema",
 "categoria": "naturaleza|ciencia|mundo|mente",
 "pregunta": "la pregunta del vídeo, máx 50 caracteres (sale en grande al principio)",
 "titulo": "máx 60 caracteres",
 "escenas": [
  {{"n": 1, "locucion": "fragmento exacto que se locuta (la escena 1 empieza por la pregunta)", "busqueda_en": "2-3 palabras en inglés, genéricas", "alternativa_en": "otra búsqueda genérica", "texto_pantalla": "máx 4 palabras o vacío"}}
 ],
 "fuentes": [{{"afirmacion": "...", "titulo": "...", "url": "...", "editor": "..."}}],
 "metadatos": {{"titulo": "título de YouTube, máx 70 caracteres", "descripcion": "1-2 frases", "hashtags": ["#LaNutriaRoja", "..."]}},
 "riesgos": ["dudas de exactitud, si las hay"]
}}
Reglas: 7-8 escenas; entre todas, 110-135 palabras. Fuentes solo reales y que conozcas con seguridad (NASA, NOAA, USGS, National Geographic,
universidades, Wikipedia); si dudas de una URL, no la pongas.
"""

DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def historial():
    try:
        return json.load(open(HISTORIAL))
    except Exception:
        return []


def excluidos():
    temas = [h['titulo'] for h in historial()]
    for f in glob.glob(os.path.join(GUIONES, '*.json')):
        try:
            temas.append(json.load(open(f))['titulo'])
        except Exception:
            pass
    temas += ['El agua que aparece de la nada en tu vaso (condensación)', 'Por qué el hielo de los glaciares es azul']
    return '; '.join(dict.fromkeys(temas))


def fechas_semana(lunes):
    return [lunes + dt.timedelta(days=d) for d in DIAS_PUBLICACION]


def encargo(fecha):
    area = AREAS[(fecha.toordinal() // 2) % len(AREAS)] if fecha.weekday() not in DIAS_PUBLICACION else AREAS[DIAS_PUBLICACION.index(fecha.weekday())]
    return PLANTILLA.format(fecha=fecha.isoformat(), excluidos=excluidos(), area=area,
                            fecha_txt=f'{DIAS[fecha.weekday()]} {fecha.day} de {MESES[fecha.month - 1]}')


def preparar(lunes):
    os.makedirs(ENCARGOS, exist_ok=True)
    for f in glob.glob(os.path.join(ENCARGOS, '*.txt')):
        os.remove(f)
    for n, fecha in enumerate(fechas_semana(lunes), 1):
        open(os.path.join(ENCARGOS, f'{n}.txt'), 'w').write(encargo(fecha))
        print(f'✔ encargo {n}: {fecha}')


def _json(texto):
    t = re.sub(r'^```(?:json)?|```$', '', texto.strip(), flags=re.M).strip()
    a, b = t.find('{'), t.rfind('}')
    if a < 0 or b < a:
        raise ValueError('La respuesta no trae JSON')
    return json.loads(t[a:b + 1])


def validar(g):
    fallos = []
    for k in ('topic_id', 'pregunta', 'titulo', 'escenas', 'metadatos'):
        if not g.get(k):
            fallos.append(f'falta «{k}»')
    esc = g.get('escenas') or []
    if not 6 <= len(esc) <= 9:
        fallos.append(f'{len(esc)} escenas (deben ser 6-9)')
    for e in esc:
        if not str(e.get('locucion', '')).strip() or not str(e.get('busqueda_en', '')).strip():
            fallos.append(f'escena {e.get("n")} sin locución o sin búsqueda')
    palabras = sum(len(str(e.get('locucion', '')).split()) for e in esc)
    if not 85 <= palabras <= 160:
        fallos.append(f'{palabras} palabras (deben ser ~110-135)')
    if esc and '?' not in str(esc[0].get('locucion', ''))[:120]:
        fallos.append('la escena 1 no empieza por la pregunta')
    return fallos


def guardar(texto):
    g = _json(texto)
    fecha = str(g.get('fecha', ''))[:10]
    dt.date.fromisoformat(fecha)
    fallos = validar(g)
    if fallos:
        raise ValueError('Guion no válido: ' + '; '.join(fallos))
    g['autor'] = 'chatgpt'
    os.makedirs(GUIONES, exist_ok=True)
    json.dump(g, open(os.path.join(GUIONES, f'{fecha}.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'✔ guion {fecha}: {g["titulo"]}')


def escribir(fecha, evitar=()):
    """Reserva: Gemini escribe el guion con el mismo encargo."""
    from nutria.guion import llm
    texto = encargo(fecha)
    if evitar:
        texto += '\nTAMBIÉN DESCARTADOS (no hay metraje bueno): ' + '; '.join(evitar)
    for _ in range(3):
        g = llm([{'role': 'user', 'content': texto}], temperatura=0.9)
        g['fecha'] = fecha.isoformat()
        if not validar(g):
            g['autor'] = 'gemini'
            return g
        print('  guion de Gemini no válido:', validar(g), flush=True)
    raise RuntimeError('Gemini no ha escrito un guion válido')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('accion', choices=['preparar', 'guardar'])
    ap.add_argument('--desde', help='lunes de la semana (AAAA-MM-DD); por defecto, el próximo lunes')
    a = ap.parse_args()
    if a.accion == 'preparar':
        hoy = dt.date.today()
        lunes = dt.date.fromisoformat(a.desde) if a.desde else hoy + dt.timedelta(days=(7 - hoy.weekday()) % 7 or 7)
        preparar(lunes)
    else:
        try:
            guardar(sys.stdin.read())
        except Exception as e:
            sys.exit(f'✖ {e}')

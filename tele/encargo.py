"""Encargo de guion para ChatGPT (lo descarga el atajo del iPhone cada domingo, y después pega la idea al final).
Se genera a partir del guionista del motor para que las reglas sean las mismas: python -m tele.encargo > tele/encargo_guion.txt"""
from .catalogo import FORMATOS, VOCES
from .guion import EMOCIONES, MUSICAS, SISTEMA, VOCES_PERSONAJE, _ejemplo
from .audio import EFECTOS

ESQUEMA = """
TU TAREA: escribe el guion COMPLETO del episodio a partir de la IDEA que va al final de este mensaje.
Respeta su premisa, su humor y su final; tú pones la historia, el diálogo, el ritmo y los recursos.

PROGRAMA DE TELE ("formato"): elige el que mejor encaje con la idea, uno de estos identificadores:
{formatos}

PERSONAJES: de 2 a 3. "cuerpo" es UNA palabra en minúsculas que dice qué es (calcetin, pavo_real, tostadora, vecina, alienigena...).
"aspecto" (EN INGLÉS) describe cómo es para un ilustrador: especie u objeto, forma, cara, ropa, colores y un detalle absurdo.
Que los personajes sean muy distintos entre sí.
VOCES (una distinta por personaje): {voces}
EMOCIONES para "emocion": {emociones}. MÚSICA por escena: {musicas}. EFECTOS para "sfx": {efectos} (o null).

Devuelve SOLO este JSON, sin nada más:
{{
 "titulo": "título del episodio, máximo 45 caracteres",
 "titulo_corto": "título para TikTok/Reels/Shorts, máximo 55 caracteres, como mucho 1 emoji",
 "formato": "uno de los identificadores de programa",
 "resumen": "X quiere Y, pero Z (una frase)",
 "premisa": "la premisa en dos frases",
 "personajes": [{{"id": "corto_sin_espacios", "nombre": "Nombre inventado", "cuerpo": "una_palabra", "personalidad": "una frase, con su manera de hablar", "voz": "una de las voces", "aspecto": "IN ENGLISH, 25-45 words"}}],
 "escenas": [
  {{"plano": "qué se ve y qué pasa", "rotulo": "faldón en pantalla, máximo 30 caracteres",
    "decorado": "IN ENGLISH, 25-50 words: the empty background set, faithful to the TV genre (a cooking show looks like a real cooking show...) but twisted by the alternate universe; reuse the same text if the place repeats",
    "musica": "normal | tension | silencio | triunfo", "sfx": "efecto o null", "prop": null,
    "presentes": ["ids de quien está aunque no hable"],
    "lineas": [{{"quien": "id o narrador", "texto": "frase", "emocion": "...", "pausa": 0, "golpe": false, "sello": ""}}]}}
 ],
 "giro": "el giro final en una frase",
 "descripcion": "texto de la publicación: 2 líneas con gancho y una pregunta final, sin hashtags",
 "hashtags": ["5 hashtags en español, el primero #teledimensional"]
}}
LÍMITES: 5 o 6 escenas; de 16 a 24 líneas en total; entre 130 y 170 palabras de diálogo; ninguna frase de más de 15 palabras.
La primera línea es el gancho. La última lleva "golpe": true.
"""


def texto():
    esquema = ESQUEMA.format(formatos=', '.join(f'{k} ({v[0]})' for k, v in FORMATOS.items()),
                             voces=', '.join(f'{v} ({VOCES[v][3]})' for v in VOCES_PERSONAJE),
                             emociones=', '.join(EMOCIONES), musicas=', '.join(MUSICAS), efectos=', '.join(EFECTOS))
    return SISTEMA.replace('Responde SOLO con JSON.', '') + '\n' + _ejemplo() + esquema + '\nIDEA:\n'


if __name__ == '__main__':
    print(texto())

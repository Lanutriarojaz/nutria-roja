"""La ficha de cada episodio, con los 15 apartados del formato de la serie."""
from .catalogo import ELEMENTOS, FORMATOS, VOCES, nombre
from .guion import ESTILO_VISUAL

FLUJO = """1. **Sorteo** (código propio): tres elementos, concepto, programa y conflicto al azar, sin repetir los recientes.
2. **Guion** (Gemini, plan gratuito): un modelo escribe, otro puntúa y, si flojea, se reescribe.
3. **Voces** (edge-tts, gratis): una voz distinta por personaje, con los tiempos de cada palabra.
4. **Animación** (código propio con Pillow + numpy): plató, personajes con boca sincronizada, cámara, rótulos e interferencias.
5. **Sonido** (numpy): sintonía y efectos sintetizados; nada con derechos de autor.
6. **Montaje y control de calidad** (ffmpeg): vídeo vertical 1080×1920; si falla el control, no se publica.
7. **Publicación** (GitHub Actions + GitHub Pages + Buffer, planes gratuitos): TikTok, Reels y Shorts.

Alternativa a mano con aplicaciones gratuitas, usando los prompts de esta ficha: imágenes con Microsoft Designer o Leonardo
(plan gratis), imagen a vídeo con Kling o Luma (créditos gratis diarios), voces con ElevenLabs gratis o edge-tts, y montaje en CapCut."""


def escribir(info):
    g, s = info['guion'], info['sorteo']
    pers = {p['id']: p for p in g['personajes']}
    L = [f"# {g['titulo']}", '', f"_Tele-Dimensional · {info['fecha']} · dimensión {s['dimension']} · {info['calidad']['duracion']} s_", '',
         '## 1. Título', g['titulo'], '',
         '## 2. Elementos aleatorios' + (f" (idea de {s['idea_fuente']})" if s.get('idea_fuente') else ''), ', '.join(nombre(e) for e in s['elementos']), '',
         '## 3. Concepto filosófico', f"{s['concepto']}: {s['concepto_idea']}.", '',
         '## 4. Programa', f"{FORMATOS[s['formato']][0].capitalize()}. Conflicto: {s['conflicto']}.", '',
         '## 5. Premisa', g['premisa'], '',
         '## 6. Personajes']
    L += [f"- **{p['nombre']}** ({nombre(p['cuerpo'])}): {p['personalidad']}" for p in g['personajes']]
    L += ['', '## 7. Guion']
    for i, e in enumerate(g['escenas'], 1):
        L += [f'### Escena {i}', f"- **Imagen:** {e['plano']}", f"- **Texto en pantalla:** {e['rotulo']}",
              f"- **Sonido:** música «{e.get('musica', 'normal')}» · efecto: {e['sfx'] or 'interferencia'}" + (f" · se enseña {ELEMENTOS[e['prop']][0]}" if e['prop'] else '')]
        L += [f"- **{pers[l['quien']]['nombre'] if l['quien'] in pers else 'Narrador'}** ({l['emocion']}"
              + (f", pausa {l['pausa']} s" if l.get('pausa') else '') + (f", GOLPE «{l['sello']}»" if l.get('golpe') else '') + f"): {l['texto']}"
              for l in e['lineas']]
        L.append('')
    L += ['## 8. Prompt visual de cada plano']
    L += [f"{i}. {e['prompt_visual'] or e['plano']} Estilo: {ESTILO_VISUAL}." for i, e in enumerate(g['escenas'], 1)]
    L += ['', '## 9. Movimiento de cada plano']
    L += [f"{i}. {e['movimiento'] or 'Zoom lento hacia quien habla; interferencia al cortar.'}" for i, e in enumerate(g['escenas'], 1)]
    L += ['', '## 10. Voces']
    L += [f"- {p['nombre']}: {VOCES[p['voz']][3]} ({VOCES[p['voz']][0]})" for p in g['personajes']]
    L += [f"- Narrador: {VOCES['locutor'][3]} ({VOCES['locutor'][0]})", '',
          '## 11. Giro final', g['giro'], '', g.get('relacion', ''), '',
          '## 12. Texto de la publicación', g['descripcion'], '',
          '## 13. Título corto', g['titulo_corto'], '',
          '## 14. Hashtags', ' '.join(g['hashtags']), '',
          '## 15. Flujo de producción', FLUJO, '']
    return '\n'.join(L)

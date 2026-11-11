# 📺 Tele-Dimensional — qué se puede cambiar y dónde

Lo más fácil es pedírselo a Claude («añade estos temas», «quiero un personaje fijo»). Si lo tocas tú, todo está en dos ficheros.

## `tele/catalogo.py` — lo que sale en el sorteo

| Lista | Qué es | Cómo añadir |
|---|---|---|
| `CONCEPTOS` | Paradojas, mitos y conceptos filosóficos | `('nombre', 'explicación en una línea'),` |
| `CONFLICTOS` | El problema del episodio | `'frase del conflicto',` |
| `FORMATOS` | Programas de tele (juicio, concurso…) | Cada uno necesita su plató dibujado en `dibujo.py` (pídeselo a Claude) |
| `ELEMENTOS` | Objetos, comida, animales y conceptos cotidianos | Necesitan dibujo: tras añadir, `python -m tele.preparar` |
| `CONTEXTOS` | **Vacía.** Universos o ambientaciones | `'una dimensión donde todo está en oferta',` |
| `PERSONAJES_FIJOS` | **Vacía.** Personajes que se repiten | Ver el ejemplo en el propio fichero; `PROB_FIJO` = cada cuánto salen |
| `VOCES` | Voces gratuitas de edge-tts | — |

El sorteo no repite elementos de los últimos 12 episodios, conceptos de los últimos 60, ni formato de los últimos 4
(se apunta todo en `tele/historial.json`).

## `tele/guion.py` — cómo escribe el guionista

- `SISTEMA`: tono, estructura (gancho → planteamiento → escalada → clímax → giro), diálogo natural y recursos
  (música, pausas, golpes, sellos). Aquí se cambia el estilo del humor.
- `revisar()`: lo que exige el jefe de guion para aprobar (nota mínima 7,5; si no llega, se reescribe).

## Horario y publicación

- `.github/workflows/tele.yml`: se prepara a las 10:00 (11:00 en verano) y se publica a las **13:00** en TikTok, YouTube e Instagram vía Buffer.
- Cada episodio deja su ficha completa en `tele/episodios/AAAA-MM-DD.md`.
- Probar sin publicar: Actions → Tele-Dimensional → Run workflow (con «Programar en Buffer» desmarcado).

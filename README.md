# 🦦 La Nutria Roja

Vídeos cortos automáticos de «Un día como hoy» para TikTok, YouTube Shorts e Instagram Reels.

**Cada lunes** (GitHub Actions, gratis):
1. Busca en Wikipedia los hechos de cada día de la semana.
2. Una IA gratuita (GitHub Models) escribe el guion solo con datos de la fuente; otra pasada verifica que no se inventa nada.
3. Fotos reales y libres de Wikimedia Commons, voz neuronal (edge-tts), subtítulos palabra a palabra y montaje con ffmpeg.
4. **Control de calidad**: si el audio tiene saltos o silencios, la imagen sale negra o la duración no cuadra, se rehace; si sigue mal, no se publica.
5. Los vídeos se sirven desde GitHub Pages (rama `media`) y se programan en **Buffer**, uno al día, a las 19:00.
6. Se abre un *issue* con el resumen → llega por correo.

Lanzar a mano: pestaña **Actions → Tirada semanal → Run workflow**.

Secretos necesarios: `BUFFER_API_KEY`.

Fuente tipográfica: Anton (SIL Open Font License, ver `assets/OFL-Anton.txt`). Fotos: Wikimedia Commons (autor y licencia en cada publicación).

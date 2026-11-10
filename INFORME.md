# 🦦 La Nutria Roja — cómo funciona (y por qué no cuesta nada)

## Qué pasa cada semana, sin que nadie toque nada

| Cuándo | Quién | Qué hace |
|---|---|---|
| Lunes 06:00 (07:00 en verano) | GitHub Actions | Arranca solo el flujo «Tirada semanal» |
| | Wikipedia | Da los hechos de cada día, de lunes a domingo |
| | Gemini (gratis) | Un modelo elige el hecho, otro escribe el guion y otro comprueba que no hay datos inventados |
| | Wikimedia Commons | Fotos reales y libres del tema |
| | edge-tts + ffmpeg | Voz, subtítulos palabra a palabra y montaje vertical |
| | Control de calidad | Rechaza vídeos con silencios, saltos de audio, imagen negra o duración rara |
| | GitHub Pages | Aloja los vídeos en una dirección pública |
| | Buffer | Recibe los 7 vídeos programados a las 19:00, uno por día, en TikTok, YouTube e Instagram |
| | Correo | Llega el resumen de la semana (o el aviso de fallo) a lanutriarojaz@gmail.com |
| Cada día 19:00 | Buffer | Publica el vídeo del día en las 3 redes |

## Qué NO interviene

- Claude: nada. Solo hizo falta para construirlo. Volvería a hacer falta solo para cambiar algo o arreglar una avería.
- ChatGPT, Codex, tu Mac, tu PC y tu iPhone: nada. Pueden estar apagados.

## Coste: 0 €

| Servicio | Plan | Límite gratis | Uso real |
|---|---|---|---|
| GitHub Actions | Repositorio público | Ilimitado | ~40 min/semana |
| GitHub Pages | Gratis | 1 GB | ~200 MB |
| Gemini | Gratis | Cupo diario por modelo y cuenta | ~30 peticiones/semana |
| Buffer | Free | 3 canales, 10 vídeos en cola por canal | 3 canales, 7 en cola |
| Wikipedia, Commons, voz, ffmpeg | Libres | — | — |

## Protecciones

- Si una IA falla, se prueba otro modelo, otra cuenta de Google y una IA de reserva.
- Si un guion trae un dato que no está en Wikipedia, ese día no se publica.
- Si se relanza la tirada, no duplica días que ya están en cola ni pisa sus vídeos.
- El repositorio se mantiene activo solo (GitHub apaga los cron tras 60 días sin cambios).

## Cosas que sí pueden requerir una mano algún día

- Que Buffer pida reconectar una red (avisa por correo; se hace en buffer.com con dos clics).
- Que Google, Buffer o las redes cambien sus condiciones.

## Controles manuales (opcionales)

- Quitar un vídeo: borrarlo de la cola en buffer.com antes de su hora.
- Lanzar la tirada a mano: GitHub → Actions → Tirada semanal → Run workflow.
- Publicar un vídeo suelto ya subido: Actions → Publicar un vídeo suelto.

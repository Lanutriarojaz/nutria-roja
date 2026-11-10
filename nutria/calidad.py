"""Control de calidad: un vídeo no se publica si no pasa TODAS estas pruebas."""
import array
import json
import math
import subprocess


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def revisar(ruta):
    fallos = []
    info = json.loads(_run(['ffprobe', '-v', 'error', '-show_entries',
                            'stream=codec_type,codec_name,width,height,channels,sample_rate:format=duration',
                            '-of', 'json', ruta]))
    dur = float(info['format']['duration'])
    v = [s for s in info['streams'] if s['codec_type'] == 'video']
    a = [s for s in info['streams'] if s['codec_type'] == 'audio']
    if not v or (v[0].get('width'), v[0].get('height')) != (1080, 1920) or v[0].get('codec_name') != 'h264':
        fallos.append('El vídeo no es 1080x1920 H.264')
    if not a or a[0].get('codec_name') != 'aac':
        fallos.append('No hay audio AAC')
    if not 20 <= dur <= 80:
        fallos.append(f'Duración rara: {dur:.1f} s')

    # 1) Marcas de tiempo del audio sin saltos ni retrocesos (la causa del fallo de sonido de la muestra)
    pts = [float(x.strip(b',')) for x in _run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'packet=pts_time',
                                   '-of', 'csv=p=0', ruta]).split() if x.strip(b', ')]
    saltos = [(p, q) for p, q in zip(pts, pts[1:]) if q - p > 0.1 or q <= p]
    if saltos:
        fallos.append(f'Audio con {len(saltos)} saltos de tiempo (p. ej. {saltos[0][0]:.2f}→{saltos[0][1]:.2f} s)')

    # 2) El audio decodificado dura lo mismo que el vídeo
    sr = 8000
    pcm = array.array('h', _run(['ffmpeg', '-v', 'quiet', '-i', ruta, '-vn', '-ac', '1', '-ar', str(sr), '-f', 's16le', '-']))
    dur_audio = len(pcm) / sr
    if abs(dur_audio - dur) > 0.6:
        fallos.append(f'El audio decodificado dura {dur_audio:.1f} s y el vídeo {dur:.1f} s')

    # 3) Suena todo el rato: ningún hueco de silencio de más de 1,5 s (salvo el último segundo)
    ventana = sr // 2
    niveles = []
    for i in range(0, len(pcm) - ventana, ventana):
        seg = pcm[i:i + ventana]
        rms = math.sqrt(sum(x * x for x in seg) / len(seg)) or 1
        niveles.append(20 * math.log10(rms / 32768))
    racha = peor = 0
    for n in niveles[:-2]:
        racha = racha + 1 if n < -45 else 0
        peor = max(peor, racha)
    if peor * 0.5 > 1.5:
        fallos.append(f'Silencio de {peor * 0.5:.1f} s en medio del vídeo')
    if niveles and sum(niveles) / len(niveles) < -32:
        fallos.append('El volumen general es demasiado bajo')

    # 4) La imagen no está en negro
    frame = _run(['ffmpeg', '-v', 'quiet', '-ss', '1.5', '-i', ruta, '-frames:v', '1', '-vf', 'scale=54:96,format=gray',
                  '-f', 'rawvideo', '-'])
    if frame and sum(frame) / len(frame) < 12:
        fallos.append('La imagen sale negra')
    return fallos, {'duracion': round(dur, 1), 'peor_silencio_s': peor * 0.5,
                    'volumen_medio_db': round(sum(niveles) / max(len(niveles), 1), 1)}

"""Panel de estadísticas: recoge de Buffer las métricas de todos los vídeos publicados en las 6 cuentas
(La Nutria Roja y The Red Otter × TikTok, Instagram y YouTube), las agrupa por vídeo, guarda una foto diaria
para ver la evolución y deja los datos CIFRADOS con la contraseña del panel (solo los ve quien la sepa).
Uso: BUFFER_API_KEY=… BUFFER_API_KEY_EN=… PANEL_CLAVE=… python -m nutria.panel_datos SALIDA_DIR
Sin IA: solo lee Buffer (gratis) y los ficheros del propio repositorio."""
import base64
import datetime as dt
import glob
import json
import os
import re
import sys

import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HISTORIAL = os.path.join(RAIZ, 'panel', 'historial.json')        # {día: {post_id: {métrica: valor}}}
API = 'https://api.buffer.com'
CUENTAS = [('es', 'La Nutria Roja', 'BUFFER_API_KEY'), ('en', 'The Red Otter', 'BUFFER_API_KEY_EN')]


def gql(clave, query, variables=None):
    for i in range(4):
        r = requests.post(API, json={'query': query, 'variables': variables or {}},
                          headers={'Authorization': f'Bearer {clave}'}, timeout=60)
        if r.status_code == 429:
            import time; time.sleep(30 * (i + 1)); continue
        j = r.json()
        if j.get('errors'):
            raise RuntimeError(f"Buffer: {j['errors'][0].get('message')}")
        return j['data']
    raise RuntimeError('Buffer: demasiadas peticiones')


def posts_enviados(clave):
    """Todos los posts publicados de esa cuenta de Buffer, con sus métricas."""
    out = []
    for o in gql(clave, 'query { account { organizations { id } } }')['account']['organizations']:
        canales = {c['id']: c for c in gql(clave, 'query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id name service } }',
                                            {'o': o['id']})['channels']}
        cursor = None
        for _ in range(30):
            d = gql(clave, 'query($o: OrganizationId!, $a: String) { posts(input: {organizationId: $o, filter: {status: [sent]}}, first: 100, after: $a) '
                           '{ edges { node { id sentAt dueAt channelId channelService externalLink metricsUpdatedAt text metrics { name value } } } '
                           'pageInfo { hasNextPage endCursor } } }', {'o': o['id'], 'a': cursor})['posts']
            for e in d['edges']:
                n = e['node']; n['canal'] = (canales.get(n['channelId']) or {}).get('name', '')
                out.append(n)
            if not d['pageInfo']['hasNextPage']:
                break
            cursor = d['pageInfo']['endCursor']
    return out


MAPA = {'Video Views': 'vistas', 'Views': 'vistas', 'Reactions': 'megusta', 'Comments': 'comentarios', 'Shares': 'compartidos',
        'Saves': 'guardados', 'Reach': 'alcance', 'Watch Time (min)': 'minutos_vistos', 'Avg. Watch Time (sec)': 'seg_medios',
        'Eng. Rate': 'interaccion'}


def _serie(texto):
    t = (texto or '').lower()
    if '#teledimensional' in t:
        return 'Tele-Dimensional'
    if '#undiacomohoy' in t or 'un día como hoy' in t:
        return 'Efemérides'
    return 'Documentales'


def _titulo(texto):
    primera = (texto or '').strip().split('\n')[0]
    primera = re.split(r'(?<=[.!?])\s', primera)[0]
    return re.sub(r'\s*#\S+', '', primera).strip()[:110] or '(sin texto)'


def _año(texto):
    for a in re.findall(r'\b(1[0-9]{3}|20[0-2][0-9])\b', texto or ''):
        if a not in ('2026',):
            return int(a)
    return None


def _epoca(año):
    if not año:
        return None
    if año < 500:
        return 'Antigüedad'
    if año < 1500:
        return 'Edad Media'
    if año < 1800:
        return 'Siglos XVI-XVIII'
    if año < 1900:
        return 'Siglo XIX'
    if año < 1950:
        return '1900-1949'
    if año < 2000:
        return '1950-1999'
    return 'Siglo XXI'


def _autores():
    """Qué vídeo escribió ChatGPT: los textos de los guiones de ChatGPT guardados en el repositorio."""
    chatgpt = set()
    for f in glob.glob(os.path.join(RAIZ, 'nutria', 'guiones', '*.json')):
        try:
            g = json.load(open(f))
            for d in (g, g.get('plan_b') or {}):
                if d.get('descripcion'):
                    chatgpt.add(d['descripcion'].strip()[:40].lower())
        except (OSError, ValueError):
            pass
    docu = {}
    try:
        for h in json.load(open(os.path.join(RAIZ, 'docu', 'historial.json'))):
            docu[h['fecha']] = h.get('autor')
    except (OSError, ValueError):
        pass
    return chatgpt, docu


def recoger():
    chatgpt, docu_autor = _autores()
    videos = {}
    for idioma, cuenta, var in CUENTAS:
        clave = os.environ.get(var)
        if not clave:
            print(f'⚠️ Falta la clave de Buffer de {cuenta} ({var}): se queda fuera'); continue
        ps = posts_enviados(clave)
        print(f'{cuenta}: {len(ps)} publicaciones')
        for p in ps:
            texto = p.get('text') or ''
            fecha = (p.get('sentAt') or p.get('dueAt') or '')[:10]
            clave_video = f"{idioma}|{fecha}|{re.sub(r'[^a-z0-9]', '', texto.lower())[:60]}"
            serie = _serie(texto)
            if serie == 'Tele-Dimensional':          # se borró de las redes el 13-nov: no cuenta
                continue
            v = videos.setdefault(clave_video, {
                'id': clave_video, 'idioma': idioma, 'cuenta': cuenta, 'fecha': fecha, 'serie': serie,
                'titulo': _titulo(texto), 'texto': texto[:600], 'año': _año(texto) if serie == 'Efemérides' else None,
                'redes': {}})
            v['epoca'] = _epoca(v['año'])
            if serie == 'Efemérides':
                v['autor'] = 'ChatGPT' if texto.strip()[:40].lower() in chatgpt else 'Gemini'
            elif serie == 'Documentales' and idioma == 'es':
                v['autor'] = {'chatgpt': 'ChatGPT', 'gemini': 'Gemini'}.get(docu_autor.get(fecha) or '', None)
            m = {MAPA[x['name']]: x['value'] for x in (p.get('metrics') or []) if x.get('name') in MAPA and x.get('value') is not None}
            v['redes'][p['channelService']] = {'post': p['id'], 'enlace': p.get('externalLink'), 'hora': (p.get('sentAt') or '')[11:16],
                                               'actualizado': (p.get('metricsUpdatedAt') or '')[:16], 'canal': p.get('canal'), **m}
    return sorted(videos.values(), key=lambda v: v['fecha'], reverse=True)


CANALES_YT = {'es': 'UCYBRd4-WO871UN7Yqn-nSPg', 'en': 'UCu6T5HbDJiAp3Q1nHeVjufw'}


def youtube(videos):
    """Con la clave gratuita de la API de YouTube: textos de los comentarios de cada Short y datos de los dos canales."""
    clave = os.environ.get('YOUTUBE_API_KEY')
    if not clave:
        return {}
    api = 'https://www.googleapis.com/youtube/v3'
    canales = {}
    try:
        r = requests.get(f'{api}/channels', params={'part': 'statistics,snippet', 'id': ','.join(CANALES_YT.values()), 'key': clave}, timeout=30).json()
        for it in r.get('items', []):
            idioma = next(k for k, v in CANALES_YT.items() if v == it['id'])
            st = it['statistics']
            canales[idioma] = {'nombre': it['snippet']['title'], 'suscriptores': int(st.get('subscriberCount', 0)),
                               'vistas': int(st.get('viewCount', 0)), 'videos': int(st.get('videoCount', 0))}
    except Exception as e:
        print(f'⚠️ YouTube (canales): {str(e)[:120]}')
    n = 0
    for v in videos:
        yt = v['redes'].get('youtube') or {}
        m = re.search(r'(?:shorts/|v=|youtu\.be/)([\w-]{11})', yt.get('enlace') or '')
        if not m:
            continue
        try:
            r = requests.get(f'{api}/commentThreads', params={'part': 'snippet', 'videoId': m.group(1), 'maxResults': 30, 'order': 'relevance',
                                                              'textFormat': 'plainText', 'key': clave}, timeout=30).json()
            v['comentarios_yt'] = [{'autor': c['snippet']['topLevelComment']['snippet'].get('authorDisplayName', ''),
                                    'texto': c['snippet']['topLevelComment']['snippet'].get('textDisplay', '')[:500],
                                    'megusta': c['snippet']['topLevelComment']['snippet'].get('likeCount', 0),
                                    'fecha': c['snippet']['topLevelComment']['snippet'].get('publishedAt', '')[:10],
                                    'respuestas': c['snippet'].get('totalReplyCount', 0)} for c in r.get('items', [])]
            n += len(v['comentarios_yt'])
        except Exception as e:
            print(f'⚠️ YouTube (comentarios de {m.group(1)}): {str(e)[:100]}')
    print(f'YouTube: {n} comentarios, canales: {list(canales)}')
    return canales


def guardar_historial(videos):
    """Foto del día (una por día; la última del día manda) para dibujar la evolución."""
    hoy = dt.date.today().isoformat()
    try:
        h = json.load(open(HISTORIAL))
    except (OSError, ValueError):
        h = {}
    h[hoy] = {r['post']: {k: r.get(k) for k in ('vistas', 'megusta', 'comentarios', 'compartidos', 'guardados')}
              for v in videos for r in v['redes'].values()}
    os.makedirs(os.path.dirname(HISTORIAL), exist_ok=True)
    json.dump(h, open(HISTORIAL, 'w'), ensure_ascii=False, separators=(',', ':'))
    return h


def resumen_historial(h, videos):
    """Totales por día y cuenta/red, para el gráfico de evolución."""
    red_de = {r['post']: (v['idioma'], red) for v in videos for red, r in v['redes'].items()}
    out = []
    for dia in sorted(h):
        tot = {}
        for pid, m in h[dia].items():
            idioma, red = red_de.get(pid, ('?', '?'))
            for k in ('vistas', 'megusta', 'comentarios', 'compartidos'):
                tot[f'{idioma}|{red}|{k}'] = tot.get(f'{idioma}|{red}|{k}', 0) + (m.get(k) or 0)
        out.append({'dia': dia, 'totales': tot})
    return out


def cifrar(datos, clave):
    """AES-GCM con clave derivada de la contraseña (PBKDF2-SHA256, 200.000 vueltas): el navegador lo descifra con la misma contraseña."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    sal, iv = os.urandom(16), os.urandom(12)
    k = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal, iterations=200000).derive(clave.encode())
    cif = AESGCM(k).encrypt(iv, json.dumps(datos, ensure_ascii=False).encode(), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {'v': 1, 'sal': b64(sal), 'iv': b64(iv), 'datos': b64(cif)}


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else 'build-panel'
    clave = os.environ.get('PANEL_CLAVE')
    if not clave:
        sys.exit('Falta la contraseña del panel (secreto PANEL_CLAVE)')
    videos = recoger()
    canales = youtube(videos)
    h = guardar_historial(videos)
    datos = {'canales': canales, 'actualizado': dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes'), 'videos': videos,
             'evolucion': resumen_historial(h, videos)}
    os.makedirs(salida, exist_ok=True)
    json.dump(cifrar(datos, clave), open(os.path.join(salida, 'datos.json'), 'w'))
    print(f"✔ {len(videos)} vídeos, {sum(len(v['redes']) for v in videos)} publicaciones → {salida}/datos.json (cifrado)")


if __name__ == '__main__':
    main()

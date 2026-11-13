"""Hechos reales e imágenes libres: Wikipedia en español + Wikimedia Commons."""
import re
import time
import requests

UA = {'User-Agent': 'LaNutriaRoja/1.0 (bot de efemerides; contacto via GitHub lanutriaroja)'}
S = requests.Session(); S.headers.update(UA)


def _get(url, **params):
    for i in range(4):
        try:
            r = S.get(url, params=params or None, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (i + 1)); continue
            r.raise_for_status()
        except requests.RequestException:
            if i == 3: raise
            time.sleep(5 * (i + 1))
    raise RuntimeError(f'No responde {url}')


def efemerides(mes, dia):
    """Lista de hechos del día: primero los destacados por Wikipedia, luego el resto."""
    base = 'https://api.wikimedia.org/feed/v1/wikipedia/es/onthisday'
    sel = _get(f'{base}/selected/{mes:02d}/{dia:02d}').get('selected', [])
    ev = _get(f'{base}/events/{mes:02d}/{dia:02d}').get('events', [])
    vistos, out = set(), []
    for e, destacado in [(e, True) for e in sel] + [(e, False) for e in ev]:
        paginas = [p for p in e.get('pages', []) if p.get('titles')]
        if not paginas or e['text'] in vistos:
            continue
        vistos.add(e['text'])
        out.append({
            'id': len(out), 'año': e['year'], 'texto': e['text'], 'destacado': destacado,
            'articulos': [p['titles']['normalized'] for p in paginas[:3]],
            'resumen': (paginas[0].get('extract') or '')[:500],
        })
    return out


def articulo(titulo, max_chars=6000):
    d = _get('https://es.wikipedia.org/w/api.php', action='query', prop='extracts', explaintext=1,
             titles=titulo, format='json', redirects=1)
    p = next(iter(d['query']['pages'].values()))
    return (p.get('extract') or '')[:max_chars]


_MALAS = re.compile(r'(logo|icon|flag|bandera|escudo|coat_of_arms|map|mapa|locator|signature|firma|\.svg$|commons-logo|wiki)', re.I)


def _info_imagenes(titulos):
    if not titulos:
        return []
    d = _get('https://commons.wikimedia.org/w/api.php', action='query', titles='|'.join(titulos[:50]),
             prop='imageinfo', iiprop='url|size|mime|extmetadata', iiurlwidth=1280, format='json')
    out = []
    for p in d.get('query', {}).get('pages', {}).values():
        ii = (p.get('imageinfo') or [{}])[0]
        if not ii.get('thumburl') or ii.get('mime') not in ('image/jpeg', 'image/png'):
            continue
        m = ii.get('extmetadata', {})
        lic = (m.get('LicenseShortName', {}).get('value') or '')
        if not re.search(r'(public domain|dominio p|cc0|cc[ -]by)', lic, re.I):
            continue
        autor = re.sub('<[^>]+>', '', m.get('Artist', {}).get('value') or '').strip()[:60]
        desc = re.sub('<[^>]+>', '', m.get('ImageDescription', {}).get('value') or '').strip()[:300]
        cats = (m.get('Categories', {}).get('value') or '').replace('|', ', ')[:200]
        out.append({'titulo': p['title'], 'url': ii['thumburl'], 'ancho': ii.get('width', 0),
                    'alto': ii.get('height', 0), 'licencia': lic, 'autor': autor or 'Wikimedia Commons',
                    'desc': desc, 'cats': cats})
    return out


def imagenes_articulo(titulo):
    d = _get('https://es.wikipedia.org/w/api.php', action='query', prop='images', titles=titulo,
             imlimit=40, format='json', redirects=1)
    p = next(iter(d['query']['pages'].values()))
    nombres = [i['title'].replace('Archivo:', 'File:') for i in p.get('images', [])]
    nombres = [n for n in nombres if not _MALAS.search(n)]
    return _info_imagenes(nombres)


def buscar_commons(consulta, n=6):
    d = _get('https://commons.wikimedia.org/w/api.php', action='query', list='search', srsearch=consulta,
             srnamespace=6, srlimit=n * 2, format='json')
    nombres = [r['title'] for r in d.get('query', {}).get('search', []) if not _MALAS.search(r['title'])]
    return _info_imagenes(nombres[:n * 2])[:n]


def descargar(url, destino):
    for i in range(4):
        r = S.get(url, timeout=60)
        if r.status_code == 200 and r.headers.get('content-type', '').startswith('image/'):
            open(destino, 'wb').write(r.content); return destino
        time.sleep(4 * (i + 1))
    raise RuntimeError(f'No se pudo bajar {url}')

"""Prueba: modelos de imagen gratis de Cloudflare Workers AI. Lista los de texto→imagen y genera un decorado y un personaje con cada uno."""
import base64, json, os, requests
CTA, TOK = os.environ['CLOUDFLARE_ACCOUNT_ID'], os.environ['CLOUDFLARE_API_TOKEN']
H = {'Authorization': f'Bearer {TOK}'}
BASE = f'https://api.cloudflare.com/client/v4/accounts/{CTA}/ai'
r = requests.get(f'{BASE}/models/search', headers=H, params={'task': 'Text-to-Image', 'per_page': 50}, timeout=60)
modelos = [m['name'] for m in r.json().get('result', [])]
print('MODELOS:', modelos, flush=True)
ESTILO = ('2D adult animated sitcom cartoon style, thick black outlines, flat bold colors, cel shading, '
          'expressive grotesque but likable design, no text, no letters, no logos, no watermark')
PRUEBAS = {
    'decorado': f'Vertical TV studio set of an absurd cooking show in an alternate dimension: marble counter in front, stoves with steaming pots, '
                f'shelves full of impossible ingredient jars, studio lights, window showing two suns. Empty, no people. {ESTILO}',
    'personaje': f'Full body character design of a striped sock with arms, legs and a big angry face, wearing a tiny revolutionary beret, '
                 f'giving a speech, standing, centered, plain flat light grey background. {ESTILO}',
}
os.makedirs('salida-img', exist_ok=True)
for m in [x for x in modelos if any(k in x for k in ('flux', 'lucid', 'phoenix', 'stable-diffusion-xl-lightning'))][:5]:
    for nombre, prompt in PRUEBAS.items():
        cuerpo = {'prompt': prompt, 'steps': 8, 'width': 768, 'height': 1344} if 'schnell' not in m else {'prompt': prompt, 'steps': 8}
        try:
            r = requests.post(f'{BASE}/run/{m}', headers=H, json=cuerpo, timeout=180)
        except Exception as e:
            print(m, nombre, 'ERROR', e); continue
        ok = r.status_code == 200
        print(m, nombre, r.status_code, '' if ok else r.text[:250], flush=True)
        if not ok:
            continue
        if r.headers.get('content-type', '').startswith('image'):
            data = r.content
        else:
            j = r.json().get('result', {}); data = base64.b64decode(j.get('image', '')) if j.get('image') else b''
        if data:
            open(f"salida-img/{m.split('/')[-1]}-{nombre}.png", 'wb').write(data)

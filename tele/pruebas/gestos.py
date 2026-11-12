"""Prueba: ¿puede FLUX.2 klein (Cloudflare) editar un personaje manteniéndolo igual pero con otro gesto?"""
import base64, io, json, os, sys, requests
from PIL import Image
CTA, TOK = os.environ['CLOUDFLARE_ACCOUNT_ID'], os.environ['CLOUDFLARE_API_TOKEN']
H = {'Authorization': f'Bearer {TOK}'}
os.makedirs('salida-img', exist_ok=True)
GESTOS = {'boca': 'the exact same character, same design, same colors, same clothes, same pose, but with the mouth wide open as if talking',
          'enfado': 'the exact same character, same design, same colors, same clothes, but furious: angry eyebrows, shouting with mouth open, clenched fists',
          'miedo': 'the exact same character, same design, same colors, same clothes, but terrified: huge eyes, trembling, hands near the face',
          'risa': 'the exact same character, same design, same colors, same clothes, but laughing hysterically with eyes closed and mouth wide open'}
FIN = ' Plain flat light grey background, full body, 2D cartoon, thick black outlines, no text.'
for base in sys.argv[1:]:
    img = open(base, 'rb').read()
    small = io.BytesIO(); Image.open(io.BytesIO(img)).convert('RGB').resize((512, 512)).save(small, 'PNG'); small = small.getvalue()
    for modelo in ('@cf/black-forest-labs/flux-2-klein-4b', '@cf/black-forest-labs/flux-2-dev'):
        for gesto, txt in GESTOS.items():
            ok = False
            for campo in ('input_image_0', 'image', 'input_image'):
                try:
                    r = requests.post(f'https://api.cloudflare.com/client/v4/accounts/{CTA}/ai/run/{modelo}', headers=H, timeout=180,
                                      files={campo: ('base.png', small, 'image/png')},
                                      data={'prompt': txt + FIN, 'width': '768', 'height': '768', 'steps': '20' if 'dev' in modelo else '4'})
                except Exception as e:
                    print(modelo, gesto, campo, 'EXC', e); continue
                print(modelo.split('/')[-1], gesto, campo, r.status_code, '' if r.status_code == 200 else r.text[:200], flush=True)
                if r.status_code == 200:
                    ct = r.headers.get('content-type', '')
                    datos = r.content if ct.startswith('image') else base64.b64decode((r.json().get('result') or {}).get('image') or '')
                    if datos:
                        nombre = os.path.basename(base).split('.')[0]
                        open(f"salida-img/{nombre}-{modelo.split('/')[-1]}-{gesto}.png", 'wb').write(datos); ok = True
                    break
            if not ok and gesto == 'boca':
                break                      # si ni el primero funciona con este modelo, siguiente modelo

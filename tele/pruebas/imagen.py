"""Prueba: ¿generan imagen gratis las claves de Gemini? Guarda una imagen por modelo en salida-img/."""
import base64, json, os, sys, requests
PROMPT = ("Fondo vertical 9:16 para animación 2D de dibujos animados para adultos, estilo cartoon con contornos negros gruesos y "
          "colores planos intensos: plató de un programa de cocina de televisión retro-futurista en otra dimensión. Encimera de "
          "mármol en primer plano, fogones con ollas humeantes, estanterías con tarros de ingredientes imposibles, luces de plató, "
          "ventana con dos soles. Sin personas, sin personajes, sin texto, sin letras, sin logotipos. Espacio libre en la mitad "
          "inferior para colocar personajes.")
os.makedirs('salida-img', exist_ok=True)
claves = [os.environ.get(k) for k in ('GEMINI_API_KEY_2', 'GEMINI_API_KEY_3', 'GEMINI_API_KEY') if os.environ.get(k)]
for modelo in sys.argv[1:]:
    for n, k in enumerate(claves):
        r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent', params={'key': k},
                          json={'contents': [{'parts': [{'text': PROMPT}]}],
                                'generationConfig': {'responseModalities': ['IMAGE'], 'imageConfig': {'aspectRatio': '9:16'}}}, timeout=180)
        print(f'{modelo} clave{n}: HTTP {r.status_code}', flush=True)
        if r.status_code != 200:
            print('   ', r.text[:300].replace('\n', ' ')); continue
        partes = r.json()['candidates'][0]['content']['parts']
        img = next((p['inlineData'] for p in partes if 'inlineData' in p), None)
        if img:
            open(f'salida-img/{modelo}.png', 'wb').write(base64.b64decode(img['data'])); print('    ✔ imagen guardada'); break

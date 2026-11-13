"""Rodaje de Tele-Dimensional v2: pide al animador gratuito (LTX-Video en Hugging Face) los clips del episodio en curso,
tantos como deje el cupo del día, y los guarda. Cuando están todos, el episodio queda «listo» para montar.
Uso: python -m tele.rodaje --dir rodaje [--guion fichero.json]
     python -m tele.rodaje --dir rodaje --estado          (dice en qué punto está, sin pedir nada)
Salida: escribe «listo=CLAVE» en $GITHUB_OUTPUT (o lo imprime) cuando el episodio tiene todos sus clips."""
import argparse
import json
import os
import shutil
import sys
import time

from . import guiones, serie

ESPACIO = 'Lightricks/ltx-video-distilled'
ANCHO, ALTO = 512, 896          # vertical, múltiplos de 32
DURACION = 8.5


def _clave(ruta):
    return os.path.basename(ruta)


def _es_v2(g):
    g = g.get('guion', g)
    return bool(g.get('escenas')) and all(e.get('video') for e in g['escenas']) and bool(g.get('lugar'))


def siguiente():
    """El guion v2 más antiguo de ChatGPT que no se ha usado todavía."""
    for p in guiones.pendientes():
        if _es_v2(p):
            return p['clave'], p['guion']
    return None, None


def _cliente(token):
    from gradio_client import Client
    return Client(ESPACIO, hf_token=token, verbose=False) if token else Client(ESPACIO, verbose=False)


def _sin_cupo(e):
    t = str(e).lower()
    return 'quota' in t or 'cupo' in t


def pedir_clip(cliente, prompt, destino):
    r = cliente.predict(prompt=prompt, negative_prompt=serie.NEGATIVO, height_ui=ALTO, width_ui=ANCHO, mode='text-to-video',
                        duration_ui=DURACION, randomize_seed=True, api_name='/text_to_video')
    shutil.copy(r[0]['video'] if isinstance(r[0], dict) else r[0], destino)


def rodar(carpeta, g, maximo=12):
    """Pide los clips que falten. Usa primero la cuenta (HF_TOKEN) y, si se agota, prueba sin cuenta. Devuelve cuántos faltan."""
    os.makedirs(carpeta, exist_ok=True)
    faltan = [n for n in range(1, len(g['escenas']) + 1) if not os.path.exists(os.path.join(carpeta, f'escena{n}.mp4'))]
    accesos = [t for t in (os.environ.get('HF_TOKEN'), None)]
    hechos = 0
    for acceso in accesos:
        if not faltan or hechos >= maximo:
            break
        quien = 'cuenta' if acceso else 'sin cuenta'
        try:
            cli = _cliente(acceso)
        except Exception as e:
            print(f'  ⚠️ No puedo conectar con el animador ({quien}): {str(e)[:160]}'); continue
        while faltan and hechos < maximo:
            n = faltan[0]
            prompt = serie.prompt_escena(g, g['escenas'][n - 1])
            for intento in range(3):
                try:
                    t = time.time()
                    pedir_clip(cli, prompt, os.path.join(carpeta, f'escena{n}.mp4'))
                    print(f'  ✔ escena {n} ({quien}, {time.time() - t:.0f} s)', flush=True)
                    faltan.pop(0); hechos += 1
                    break
                except Exception as e:
                    if _sin_cupo(e):
                        print(f'  ⏸ cupo gratis agotado ({quien}): {str(e)[:140]}', flush=True)
                        intento = None
                        break
                    print(f'  ✖ escena {n}, intento {intento + 1}: {str(e)[:160]}', flush=True)
                    time.sleep(20)
            else:
                return len(faltan)                      # el animador falla por otra cosa: mañana se reintenta
            if intento is None:
                break                                   # sin cupo con este acceso: pasamos al siguiente
    return len(faltan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='rodaje')
    ap.add_argument('--guion', help='guion v2 concreto (para el piloto); si no, el siguiente pendiente de ChatGPT')
    ap.add_argument('--estado', action='store_true')
    ap.add_argument('--montado', action='store_true', help='apunta que el episodio ya está montado y espera visto bueno')
    ap.add_argument('--cerrar', action='store_true', help='episodio publicado: gasta el guion y deja el rodaje vacío')
    a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)
    est_ruta = os.path.join(a.dir, 'estado.json')
    est = json.load(open(est_ruta)) if os.path.exists(est_ruta) else {}
    if a.montado or a.cerrar:
        if not est.get('clave'):
            return
        if a.montado:
            est['montado'] = True; json.dump(est, open(est_ruta, 'w'), ensure_ascii=False, indent=1)
        else:
            if est['clave'].startswith('20'):
                guiones.gastar(est['clave'])
            shutil.rmtree(os.path.join(a.dir, est['clave'].removesuffix('.json')), ignore_errors=True)
            os.remove(est_ruta)
        print(f"  {'montado' if a.montado else 'cerrado'}: {est['clave']}"); return
    if est.get('montado') and not a.guion:
        print(f"⏸ «{est['guion']['titulo']}» está montado y espera visto bueno: no ruedo nada más."); return
    if a.guion:
        clave, g = _clave(a.guion), json.load(open(a.guion))
        g = g.get('guion', g)
        if est.get('clave') != clave:
            est = {'clave': clave, 'guion': g}
    elif est.get('clave'):
        clave, g = est['clave'], est['guion']
    else:
        clave, g = siguiente()
        if not clave:
            print('No hay guiones nuevos de ChatGPT (formato v2). Llegan los domingos con el atajo.'); return
        est = {'clave': clave, 'guion': g}
    g = serie.validar(g)
    est['guion'] = g
    json.dump(est, open(est_ruta, 'w'), ensure_ascii=False, indent=1)
    carpeta = os.path.join(a.dir, clave.removesuffix('.json'))
    print(f'▶ Episodio en rodaje: «{g["titulo"]}» ({clave})')
    if a.estado:
        hechos = len([f for f in os.listdir(carpeta)]) if os.path.isdir(carpeta) else 0
        print(f'  {hechos}/{len(g["escenas"])} clips'); return
    faltan = rodar(carpeta, g)
    print(f'  quedan {faltan} de {len(g["escenas"])} clips')
    if faltan == 0:
        salida = os.environ.get('GITHUB_OUTPUT')
        linea = f'listo={clave}\n'
        open(salida, 'a').write(linea) if salida else print(linea.strip())


if __name__ == '__main__':
    sys.exit(main())

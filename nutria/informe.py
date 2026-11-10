"""Escribe el resumen de la semana (cuerpo del correo/issue)."""
import json, os, sys

def main(carpeta, pages):
    t = json.load(open(os.path.join(carpeta, 'tirada.json')))
    p = os.path.join(carpeta, 'programados.json')
    prog = json.load(open(p)) if os.path.exists(p) else []
    L = ['# 🦦 La Nutria Roja — tirada de la semana', '']
    for v in t:
        if v.get('ok'):
            redes = [f"{'✅' if r['ok'] else '❌'} {r['red']}" for r in prog if r['fecha'] == v['fecha']]
            L += [f"## {v['fecha']} — {v['titulo']}", f"_{v['hecho']}_", '',
                  f"▶️ [Ver vídeo]({pages}/{v['fecha']}.mp4) · {v['calidad']['duracion']} s · " + (' · '.join(redes) or 'sin programar'),
                  '', '> ' + ' '.join(v['guion']), '']
        else:
            L += [f"## {v['fecha']} — ❌ no se ha podido hacer", f"`{v.get('error','')[:400]}`", '']
    malos = [r for r in prog if not r['ok']]
    if malos:
        L += ['## ⚠️ Fallos al programar en Buffer'] + [f"- {r['fecha']} {r['red']}: {r['detalle']}" for r in malos]
    L += ['', 'Para quitar un vídeo: bórralo de la cola en buffer.com antes de su hora.']
    print('\n'.join(L))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])

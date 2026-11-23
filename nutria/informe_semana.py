"""Informe de una semana: métricas de cada vídeo (suma de TikTok + Instagram + YouTube) y media por IA. Solo lee de Buffer.
Uso: python -m nutria.informe_semana AAAA-MM-DD AAAA-MM-DD"""
import sys
from collections import defaultdict
from nutria import panel_datos as P

K = ('vistas', 'megusta', 'comentarios', 'compartidos', 'guardados')


def main():
    desde, hasta = sys.argv[1], sys.argv[2]
    vids = [v for v in P.recoger() if desde <= v['fecha'] <= hasta]
    medias = defaultdict(lambda: [0, defaultdict(int)])
    for v in sorted(vids, key=lambda v: (v['fecha'], v['idioma'], v['serie'])):
        t = {k: sum((r.get(k) or 0) for r in v['redes'].values()) for k in K}
        por_red = ' '.join(f"{red[:2]}={r.get('vistas') or 0}" for red, r in sorted(v['redes'].items()))
        autor = v.get('autor') or '?'
        print(f"{v['fecha']} {v['idioma']} {v['serie'][:5]:5} {autor:7} vistas={t['vistas']:6} ♥={t['megusta']:4} 💬={t['comentarios']:3} ↗={t['compartidos']:3} 🔖={t['guardados']:3} [{por_red}] {v['titulo'][:70]}")
        g = medias[(v['idioma'], v['serie'], autor)]
        g[0] += 1
        for k in K:
            g[1][k] += t[k]
    print('\nMEDIAS por vídeo:')
    for (idioma, serie, autor), (n, s) in sorted(medias.items()):
        print(f"  {idioma} {serie:12} {autor:7} n={n}  vistas={s['vistas'] / n:7.0f}  ♥={s['megusta'] / n:5.1f}  💬={s['comentarios'] / n:4.1f}  ↗={s['compartidos'] / n:4.1f}")


if __name__ == '__main__':
    main()

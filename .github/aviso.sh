#!/usr/bin/env bash
# Abre una incidencia (= un correo) SOLO si no hay ya una abierta con el mismo título.
# Así un fallo que se repite o un flujo que se relanza no llena el correo de mensajes iguales.
# Uso: .github/aviso.sh "Título" "Texto"     |     .github/aviso.sh "Título" --body-file fichero.md
titulo="$1"; shift
if gh issue list --state open --limit 100 --json title -q '.[].title' | grep -Fxq "$titulo"; then
  echo "Ya hay un aviso abierto «$titulo»: no mando otro correo."; exit 0
fi
if [ "$1" = "--body-file" ]; then gh issue create --title "$titulo" --body-file "$2"; else gh issue create --title "$titulo" --body "$1"; fi

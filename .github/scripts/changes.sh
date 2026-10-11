#!/usr/bin/env bash
# Quels contrôles lancer pour une PR, d'après les fichiers qu'elle change (un par ligne sur
# l'entrée standard). Écrit `backend=…`, `frontend=…` et `e2e=…` (true ou false).
#
#   documents, maquettes, skills        → rien
#   frontend/                           → front + parcours
#   backend/, docs/ecole-pilote/        → serveur + parcours
#   tout le reste (Makefile, infra…)    → tout : dans le doute, on teste
#
# Essayer : printf 'docs/06-suivi.md\n' | .github/scripts/changes.sh
set -euo pipefail

backend=false
frontend=false
seen=false

while IFS= read -r file; do
  [ -n "$file" ] || continue
  seen=true
  case "$file" in
    # `make demo` (tests du serveur, parcours) lit le logo de l'école pilote dans ce dossier.
    backend/* | docs/ecole-pilote/*) backend=true ;;
    # Le serveur vérifie que le schéma commité correspond à son code.
    frontend/packages/api/openapi.yaml) backend=true frontend=true ;;
    frontend/*) frontend=true ;;
    docs/* | maquettes/* | .claude/* | *.md) ;;
    *) backend=true frontend=true ;;
  esac
done

# Liste vide (diff impossible) : tout lancer.
if [ "$seen" = false ]; then
  backend=true
  frontend=true
fi

e2e=false
if [ "$backend" = true ] || [ "$frontend" = true ]; then e2e=true; fi

echo "backend=$backend"
echo "frontend=$frontend"
echo "e2e=$e2e"

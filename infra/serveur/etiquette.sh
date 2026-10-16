#!/usr/bin/env bash
# Étiquette des images de production (PERF.5c) : empreinte du seul contenu qui entre dans les images
# (`.dockerignore`) — code du serveur, du front, Dockerfile, Caddyfile. Un changement de documents,
# de maquettes ou de scripts du serveur ne change pas l'étiquette : aucune image n'est reconstruite.
# Utilisé par `deployer.sh` et par `.github/workflows/images.yml` : même calcul des deux côtés.
#   etiquette.sh [REF]   (HEAD par défaut) → 12 caractères
set -euo pipefail
ref=${1:-HEAD}
for chemin in backend frontend infra/Dockerfile infra/Caddyfile infra/routes.caddy infra/production/Caddyfile .dockerignore; do
  printf '%s %s\n' "$chemin" "$(git rev-parse "$ref:$chemin")"
done | sha1sum | cut -c1-12

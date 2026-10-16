#!/usr/bin/env bash
# Mémoire et état de chaque conteneur (PERF.4, PERF.5b), notés dans Redis pour la carte « Santé »
# de la console : un conteneur ne voit pas les autres, donc cette tâche (cron, toutes les
# 5 minutes, posée par `make deploy`) lit `docker stats` et `docker inspect`. Les valeurs
# s'effacent seules au bout de 15 minutes : si le cron s'arrête, la console n'affiche plus rien
# plutôt que des chiffres périmés.
set -euo pipefail
COMPOSE=${COMPOSE:-docker compose}
set_key() { $COMPOSE exec -T redis redis-cli -x SETEX "$1" 900 >/dev/null; }

docker stats --no-stream --format '{{.Name}};{{.MemUsage}}' | set_key mwangaza:containers
# nom;arrêté par manque de mémoire (true/false);redémarrages;dernier démarrage
# shellcheck disable=SC2046
docker inspect --format '{{.Name}};{{.State.OOMKilled}};{{.RestartCount}};{{.State.StartedAt}}' \
  $(docker ps -aq) | sed 's#^;\?/##' | set_key mwangaza:containers:state

#!/usr/bin/env bash
# Mémoire de chaque conteneur (PERF.4), notée dans Redis pour la carte « Santé » de la console :
# un conteneur ne voit pas les autres, donc cette tâche (cron, toutes les 5 minutes, posée par
# `make deploy`) lit `docker stats`. La valeur s'efface seule au bout de 15 minutes : si le cron
# s'arrête, la console n'affiche plus rien plutôt que des chiffres périmés.
set -euo pipefail
COMPOSE=${COMPOSE:-docker compose}
docker stats --no-stream --format '{{.Name}};{{.MemUsage}}' \
  | $COMPOSE exec -T redis redis-cli -x SETEX mwangaza:containers 900 >/dev/null

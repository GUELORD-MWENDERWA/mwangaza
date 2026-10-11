#!/usr/bin/env bash
# Serveur de démonstration en ligne (4.6.2), piloté depuis cette machine par SSH (`make deploy…`).
# Valeurs dans `infra/serveur/serveur.env` (hors Git, créé au premier lancement).
#
#   setup            une seule fois : préparer le serveur (`preparer.sh`, en root)
#   deploy [REF]     mettre en ligne REF (origin/main par défaut) : code envoyé par SSH, images
#                    construites sur le serveur (l'ancienne version reste en ligne pendant ce
#                    temps), migrations au démarrage de Django ; tâche de chaque nuit installée
#   demo             données fictives (mot de passe : DJANGO_DEMO_PASSWORD de serveur.env)
#   superuser        créer un compte super-admin (questions posées sur le serveur)
#   logs [SERVICE]   derniers journaux (caddy, django, celery, db, redis)
#   ssh              ouvrir une session sur le serveur
set -euo pipefail
cd "$(dirname "$0")/../.."

essai() { (cd backend && uv run python ../infra/reseau/essai.py --serveur "$@"); }
essai init
SERVEUR=$(sed -n 's/^SERVEUR=//p' infra/serveur/serveur.env)
# Sur le serveur : ~/mwangaza/code ; données dans les volumes Docker du projet « mwangaza ».
COMPOSE="docker compose -f infra/docker-compose.yml -f infra/docker-compose.reseau.yml \
--env-file infra/serveur/serveur.env -p mwangaza"
SSH=(ssh -o StrictHostKeyChecking=accept-new "$SERVEUR")
# Tâche de chaque nuit (`infra/backup/sauvegarde.sh`, 0 h 30 du serveur) : purge des sessions
# expirées ; sauvegarde chiffrée dans ~/mwangaza/sauvegardes si serveur.env a une clé
# BACKUP_PASSPHRASE. Journal sur le serveur : journalctl -t mwangaza.
CRON="30 0 * * * cd \$HOME/mwangaza/code && COMPOSE='$COMPOSE' VALEURS=infra/serveur/serveur.env \
BACKUP_DIR=\$HOME/mwangaza/sauvegardes infra/backup/sauvegarde.sh backup 2>&1 | logger -t mwangaza"

case "${1:-}" in
  setup)
    "${SSH[@]}" "sudo bash -s" <infra/serveur/preparer.sh
    ;;
  deploy)
    ref=${2:-origin/main}
    git fetch --quiet origin
    commit=$(git rev-parse --short "$ref")
    echo "Mise en ligne de $ref ($commit) sur $SERVEUR"
    essai ip
    essai accueil
    git archive --format=tar "$ref" |
      "${SSH[@]}" "rm -rf mwangaza/nouveau && mkdir -p mwangaza/nouveau && tar -x -C mwangaza/nouveau"
    tar -c -C infra/serveur serveur.env accueil |
      "${SSH[@]}" "tar -x -C mwangaza/nouveau/infra/serveur"
    # Mise à jour sur place : les dossiers montés dans les conteneurs restent les mêmes.
    "${SSH[@]}" "set -e; cd mwangaza && mkdir -p code \
      && rsync -a --delete --exclude /infra/certs nouveau/ code/ && rm -rf nouveau \
      && cd code && echo $commit >VERSION && chmod 600 infra/serveur/serveur.env \
      && mkdir -p infra/certs && $COMPOSE build && $COMPOSE up --detach --wait --remove-orphans \
      && docker image prune --force >/dev/null"
    # Crontab du compte, remis à chaque mise en ligne (pas de planificateur Celery).
    "${SSH[@]}" "(crontab -l 2>/dev/null | grep -v sauvegarde.sh; echo \"$CRON\") | crontab -"
    essai adresses
    ;;
  demo)
    "${SSH[@]}" "cd mwangaza/code && $COMPOSE exec -T django python manage.py demo"
    ;;
  superuser)
    ssh -t "$SERVEUR" "cd mwangaza/code && $COMPOSE exec django python manage.py createsuperuser"
    ;;
  logs)
    "${SSH[@]}" "cd mwangaza/code && cat VERSION && $COMPOSE logs --tail 80 ${2:-}"
    ;;
  ssh)
    ssh "$SERVEUR"
    ;;
  *)
    sed -n '2,13p' "$0"
    exit 1
    ;;
esac

#!/usr/bin/env bash
# Vrai serveur (AWS Lightsail, 4.6.3), piloté depuis cette machine par SSH (`make deploy…`).
# Valeurs dans `infra/serveur/serveur.env` (hors Git, créé au premier lancement).
#
#   init             créer serveur.env (secrets neufs) puis vérifier qu'il est rempli
#   setup            une seule fois : préparer le serveur (`preparer.sh`, en root)
#   deploy [REF]     mettre en ligne REF (origin/main par défaut) : code envoyé par SSH, images
#                    construites sur le serveur (l'ancienne version reste en ligne pendant ce
#                    temps), migrations et droits du compte PostgreSQL de l'application par le
#                    conteneur `migrate`, avant Django ; tâche de chaque nuit installée
#   superuser        créer un compte super-admin (questions posées sur le serveur)
#   logs [SERVICE]   derniers journaux (caddy, django, celery, celery-print, db, redis)
#   backup [ARGS]    sauvegarde.sh sur le serveur : `backup` (sauvegarde du jour, copie hors du
#                    serveur comprise), `fetch` (rapatrier la dernière copie), `restore` (essai)
#   ssh              ouvrir une session sur le serveur
#   check            HTTPS, certificat et santé de l'API, depuis cette machine
#
set -euo pipefail
cd "$(dirname "$0")/../.."

ENV_FILE=infra/serveur/serveur.env
[ "${1:-}" = init ] && {
  (cd backend && uv run python ../infra/serveur/init.py)
  echo "Garde-en une copie en lieu sûr, puis make deploy-setup."; exit 0; }
[ -f "$ENV_FILE" ] || { echo "serveur.env manque : make deploy-init"; exit 1; }
SERVEUR=$(sed -n 's/^SERVEUR=//p' "$ENV_FILE")
DOMAIN=$(sed -n 's/^MWANGAZA_DOMAIN=//p' "$ENV_FILE")
# Sur le serveur : ~/mwangaza/code ; données dans les volumes Docker du projet « mwangaza ».
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
KEY=$(sed -n 's/^SSH_KEY=//p' "$ENV_FILE")
KEY=${KEY/#\~/$HOME}
[ -r "$KEY" ] || { echo "Clé SSH illisible : $KEY (SSH_KEY dans serveur.env)"; exit 1; }
SSH_OPTS+=(-i "$KEY" -o IdentitiesOnly=yes)
OVERLAY=docker-compose.production.yml
COMPOSE="docker compose -f infra/docker-compose.yml -f infra/$OVERLAY \
--env-file infra/serveur/serveur.env -p mwangaza"
SSH=(ssh "${SSH_OPTS[@]}" "$SERVEUR")
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
    # Compte PostgreSQL de l'application (S.5) : un serveur.env d'avant ne l'a pas.
    grep -q '^POSTGRES_APP_PASSWORD=.' "$ENV_FILE" ||
      { echo "POSTGRES_APP_PASSWORD manque dans serveur.env : make deploy-init l'ajoute."; exit 1; }
    git fetch --quiet origin
    commit=$(git rev-parse --short "$ref")
    # Garde-fou : sans swap, la construction (2 Go de RAM) peut figer le serveur, SSH compris.
    "${SSH[@]}" "swapon --show --noheadings | grep -q ." ||
      { echo "Pas de swap sur le serveur : make deploy-setup d'abord (relançable sans danger)."; exit 1; }
    echo "Mise en ligne de $ref ($commit) sur $SERVEUR"
    git archive --format=tar "$ref" |
      "${SSH[@]}" "rm -rf mwangaza/nouveau && mkdir -p mwangaza/nouveau && tar -x -C mwangaza/nouveau"
    tar -c -C infra/serveur serveur.env |
      "${SSH[@]}" "tar -x -C mwangaza/nouveau/infra/serveur"
    # Mise à jour sur place : les dossiers montés dans les conteneurs restent les mêmes.
    # Après : anciennes images supprimées, cache de construction ramené à 2 Go (il grossissait à
    # chaque mise en ligne : 8 Go mesurés le 2026-10-13, assez pour la construction suivante).
    "${SSH[@]}" "set -e; cd mwangaza && chmod 700 . && mkdir -p code \
      && rsync -a --delete --exclude /infra/certs nouveau/ code/ && rm -rf nouveau \
      && cd code && echo $commit >VERSION && chmod 600 infra/serveur/serveur.env \
      && mkdir -p infra/certs && COMPOSE_PARALLEL_LIMIT=1 nice -n 10 $COMPOSE build && $COMPOSE up --detach --wait --remove-orphans \
      && docker image prune --force >/dev/null \
      && { docker builder prune --force --reserved-space 2GB >/dev/null \
        || echo 'Cache de construction non purgé (option de docker builder prune à revoir).'; }"
    # Crontab du compte, remis à chaque mise en ligne (pas de planificateur Celery).
    "${SSH[@]}" "(crontab -l 2>/dev/null | grep -v sauvegarde.sh; echo \"$CRON\") | crontab -"
    echo "Vérification : make deploy-check"
    ;;
  check)
    ok=1
    for host in "admin.$DOMAIN" "parents.$DOMAIN" "itig.$DOMAIN"; do
      printf '%s : ' "$host"
      # Pas de -k : le certificat doit être valide. Code 000 = connexion ou certificat refusé.
      if code=$(curl -sS --max-time 15 -o /dev/null -w '%{http_code}' "https://$host/") && [ "$code" != 000 ]; then
        echo "HTTP $code, certificat valide"
      else
        echo "ÉCHEC (connexion ou certificat)"; ok=
      fi
    done
    printf 'santé : '
    curl -fsS --max-time 15 "https://admin.$DOMAIN/api/health/" && echo || ok=
    [ -n "$ok" ] || { echo "Vérification en échec."; exit 1; }
    ;;
  superuser)
    ssh -t "${SSH_OPTS[@]}" "$SERVEUR" "cd mwangaza/code && $COMPOSE exec django python manage.py createsuperuser"
    ;;
  logs)
    "${SSH[@]}" "cd mwangaza/code && cat VERSION && $COMPOSE logs --tail 80 ${2:-}"
    ;;
  backup)
    shift
    ssh -t "${SSH_OPTS[@]}" "$SERVEUR" "cd mwangaza/code && COMPOSE='$COMPOSE' \
VALEURS=infra/serveur/serveur.env BACKUP_DIR=\$HOME/mwangaza/sauvegardes infra/backup/sauvegarde.sh ${*:-backup}"
    ;;
  ssh)
    ssh "${SSH_OPTS[@]}" "$SERVEUR"
    ;;
  *)
    sed -n '2,22p' "$0"
    exit 1
    ;;
esac

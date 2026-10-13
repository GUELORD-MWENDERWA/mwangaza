#!/usr/bin/env bash
# Serveur de démonstration en ligne (4.6.2), piloté depuis cette machine par SSH (`make deploy…`).
# Valeurs dans `infra/serveur/serveur.env` (hors Git, créé au premier lancement).
#
#   init             créer serveur.env du vrai serveur (MODE=production, AWS Lightsail, 4.6.3)
#   setup            une seule fois : préparer le serveur (`preparer.sh`, en root)
#   deploy [REF]     mettre en ligne REF (origin/main par défaut) : code envoyé par SSH, images
#                    construites sur le serveur (l'ancienne version reste en ligne pendant ce
#                    temps), migrations au démarrage de Django ; tâche de chaque nuit installée
#   demo             données fictives (mot de passe : DJANGO_DEMO_PASSWORD de serveur.env)
#   superuser        créer un compte super-admin (questions posées sur le serveur)
#   logs [SERVICE]   derniers journaux (caddy, django, celery, db, redis)
#   ssh              ouvrir une session sur le serveur
#   check            (production) HTTPS, certificat et santé de l'API, depuis cette machine
#
# MODE=production dans serveur.env : vrai serveur (Cloudflare pour le DNS, Caddyfile de
# `infra/production/`, clé SSH SSH_KEY, ni DuckDNS ni données fictives). Sans : serveur de
# démonstration DuckDNS (4.6.2). `make reseau` n'est jamais touché : autre fichier de valeurs,
# autre projet Docker.
set -euo pipefail
cd "$(dirname "$0")/../.."

ENV_FILE=infra/serveur/serveur.env
PROD=
if [ -f "$ENV_FILE" ] && grep -qx 'MODE=production' "$ENV_FILE"; then PROD=1; fi
if [ "${1:-}" = init ]; then PROD=1; fi
FLAG=--serveur
if [ -n "$PROD" ]; then FLAG=--production; fi
essai() { (cd backend && uv run python ../infra/reseau/essai.py $FLAG "$@"); }
essai init
[ "${1:-}" = init ] && { echo "Remplis serveur.env si besoin, garde-en une copie, puis make deploy-setup."; exit 0; }
SERVEUR=$(sed -n 's/^SERVEUR=//p' "$ENV_FILE")
DOMAIN=$(sed -n 's/^MWANGAZA_DOMAIN=//p' "$ENV_FILE")
# Sur le serveur : ~/mwangaza/code ; données dans les volumes Docker du projet « mwangaza ».
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
OVERLAY=docker-compose.reseau.yml
if [ -n "$PROD" ]; then
  KEY=$(sed -n 's/^SSH_KEY=//p' "$ENV_FILE")
  KEY=${KEY/#\~/$HOME}
  [ -r "$KEY" ] || { echo "Clé SSH illisible : $KEY (SSH_KEY dans serveur.env)"; exit 1; }
  SSH_OPTS+=(-i "$KEY" -o IdentitiesOnly=yes)
  OVERLAY=docker-compose.production.yml
fi
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
    git fetch --quiet origin
    commit=$(git rev-parse --short "$ref")
    echo "Mise en ligne de $ref ($commit) sur $SERVEUR"
    if [ -z "$PROD" ]; then essai ip; essai accueil; fi
    git archive --format=tar "$ref" |
      "${SSH[@]}" "rm -rf mwangaza/nouveau && mkdir -p mwangaza/nouveau && tar -x -C mwangaza/nouveau"
    tar -c -C infra/serveur serveur.env $([ -z "$PROD" ] && echo accueil) |
      "${SSH[@]}" "tar -x -C mwangaza/nouveau/infra/serveur"
    # Mise à jour sur place : les dossiers montés dans les conteneurs restent les mêmes.
    "${SSH[@]}" "set -e; cd mwangaza && mkdir -p code \
      && rsync -a --delete --exclude /infra/certs nouveau/ code/ && rm -rf nouveau \
      && cd code && echo $commit >VERSION && chmod 600 infra/serveur/serveur.env \
      && mkdir -p infra/certs && $COMPOSE build && $COMPOSE up --detach --wait --remove-orphans \
      && docker image prune --force >/dev/null"
    # Crontab du compte, remis à chaque mise en ligne (pas de planificateur Celery).
    "${SSH[@]}" "(crontab -l 2>/dev/null | grep -v sauvegarde.sh; echo \"$CRON\") | crontab -"
    if [ -z "$PROD" ]; then essai adresses; else echo "Vérification : make deploy-check"; fi
    ;;
  check)
    [ -n "$PROD" ] || { echo "check : vrai serveur seulement (MODE=production)"; exit 1; }
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
  demo)
    [ -z "$PROD" ] || { echo "Pas de données fictives sur le vrai serveur : crée l'espace de démonstration depuis la console."; exit 1; }
    "${SSH[@]}" "cd mwangaza/code && $COMPOSE exec -T django python manage.py demo"
    ;;
  superuser)
    ssh -t "${SSH_OPTS[@]}" "$SERVEUR" "cd mwangaza/code && $COMPOSE exec django python manage.py createsuperuser"
    ;;
  logs)
    "${SSH[@]}" "cd mwangaza/code && cat VERSION && $COMPOSE logs --tail 80 ${2:-}"
    ;;
  ssh)
    ssh "${SSH_OPTS[@]}" "$SERVEUR"
    ;;
  *)
    sed -n '2,20p' "$0"
    exit 1
    ;;
esac

#!/usr/bin/env bash
# Vrai serveur (AWS Lightsail, 4.6.3), piloté depuis cette machine par SSH (`make deploy…`).
# Valeurs dans `infra/serveur/serveur.env` (hors Git, créé au premier lancement).
#
#   init             créer serveur.env (secrets neufs) puis vérifier qu'il est rempli
#   setup            une seule fois : préparer le serveur (`preparer.sh`, en root)
#   deploy [REF]     mettre en ligne REF (origin/main par défaut) : code envoyé par SSH, images
#                    construites par GitHub Actions (`images.yml`, seulement si le code des images a
#                    changé) et téléchargées par le serveur (l'ancienne version reste en ligne pendant
#                    ce temps), migrations et droits du compte PostgreSQL de l'application par le
#                    conteneur `migrate`, avant Django ; tâche de chaque nuit installée.
#                    Secours (quota d'Actions épuisé) : CONSTRUIRE_SUR_SERVEUR=oui make deploy
#   superuser        créer un compte super-admin (questions posées sur le serveur)
#   logs [SERVICE]   derniers journaux (caddy, django, worker, worker-heavy, scheduler, db, redis)
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
# Mémoire des conteneurs, toutes les 5 minutes (carte « Santé » de la console, PERF.4).
CRON_MEMORY="*/5 * * * * cd \$HOME/mwangaza/code && COMPOSE='$COMPOSE' infra/serveur/conteneurs.sh 2>&1 | logger -t mwangaza"

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
    "${SSH[@]}" "set -e; cd mwangaza && chmod 700 . && mkdir -p code \
      && rsync -a --delete --exclude /infra/certs nouveau/ code/ && rm -rf nouveau \
      && cd code && echo $commit >VERSION && chmod 600 infra/serveur/serveur.env \
      && mkdir -p infra/certs"
    if [ "${CONSTRUIRE_SUR_SERVEUR:-}" = oui ]; then
      # Secours (PERF.5c) : l'ancienne façon, lente et lourde pour 2 Go de RAM. Après : anciennes
      # images supprimées, cache de construction ramené à 2 Go.
      echo "Construction sur le serveur (secours) : compte 15 minutes."
      "${SSH[@]}" "set -e; cd mwangaza/code && COMPOSE_PARALLEL_LIMIT=1 nice -n 10 $COMPOSE build \
        && $COMPOSE up --detach --wait --remove-orphans && docker image prune --force >/dev/null \
        && { docker builder prune --force --reserved-space 2GB >/dev/null || true; }"
    else
      GHCR_USER=$(sed -n 's/^GHCR_USER=//p' "$ENV_FILE")
      GHCR_TOKEN=$(sed -n 's/^GHCR_TOKEN=//p' "$ENV_FILE")
      { [ -n "$GHCR_USER" ] && [ -n "$GHCR_TOKEN" ]; } ||
        { echo "GHCR_USER et GHCR_TOKEN manquent dans serveur.env : make deploy-init, puis A-FAIRE.md § 9 quinquies."; exit 1; }
      REGISTRY="ghcr.io/$(printf '%s' "$GHCR_USER" | tr '[:upper:]' '[:lower:]')"
      tag=$(infra/serveur/etiquette.sh "$ref")
      echo "Images $tag (empreinte du code contenu dans les images)"
      # Le jeton passe par l'entrée standard : jamais dans une ligne de commande ni un journal.
      printf '%s' "$GHCR_TOKEN" | "${SSH[@]}" "docker login ghcr.io -u '$GHCR_USER' --password-stdin >/dev/null"
      if ! "${SSH[@]}" "docker manifest inspect $REGISTRY/mwangaza-backend:$tag >/dev/null 2>&1 \
          && docker manifest inspect $REGISTRY/mwangaza-caddy-production:$tag >/dev/null 2>&1"; then
        command -v gh >/dev/null || { echo "gh (GitHub CLI) manque : installe-le, ou CONSTRUIRE_SUR_SERVEUR=oui."; exit 1; }
        full=$(git rev-parse "$ref")
        git branch -r --contains "$full" | grep -q . ||
          { echo "Le commit $commit n'est pas sur GitHub : git push d'abord."; exit 1; }
        echo "Images absentes du registre : construction par GitHub Actions (≈ 10 à 15 minutes la première fois)."
        started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        gh workflow run images.yml --ref main -f ref="$full"
        run_id=
        for _ in $(seq 1 30); do
          sleep 4
          run_id=$(gh run list --workflow images.yml --event workflow_dispatch --limit 5 \
            --json databaseId,createdAt -q "[.[] | select(.createdAt >= \"$started\")] | first | .databaseId // empty")
          [ -n "$run_id" ] && break
        done
        [ -n "$run_id" ] || { echo "Le passage d'Actions n'est pas apparu : gh run list --workflow images.yml"; exit 1; }
        gh run watch "$run_id" --exit-status ||
          { echo "Construction en échec : gh run view $run_id --log-failed (secours : CONSTRUIRE_SUR_SERVEUR=oui make deploy)"; exit 1; }
      fi
      # Téléchargées sous leur nom de registre, puis re-étiquetées comme `docker-compose.yml` les attend.
      # `--no-build` : jamais de construction sur le serveur. Les anciennes images du registre sont
      # supprimées après la mise en ligne (disque de 60 Go).
      "${SSH[@]}" "set -e; cd mwangaza/code \
        && docker pull -q $REGISTRY/mwangaza-backend:$tag && docker pull -q $REGISTRY/mwangaza-caddy-production:$tag \
        && docker tag $REGISTRY/mwangaza-backend:$tag mwangaza-backend:latest \
        && docker tag $REGISTRY/mwangaza-caddy-production:$tag mwangaza-caddy-production:latest \
        && $COMPOSE up --detach --wait --remove-orphans --no-build \
        && { docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^ghcr.io/.*/mwangaza-' \
             | grep -v ':$tag\$' | xargs -r docker rmi >/dev/null 2>&1 || true; } \
        && docker image prune --force >/dev/null"
    fi
    # Crontab du compte, remis à chaque mise en ligne (pas de planificateur Celery).
    "${SSH[@]}" "(crontab -l 2>/dev/null | grep -v -e sauvegarde.sh -e conteneurs.sh; echo \"$CRON\"; echo \"$CRON_MEMORY\") | crontab -"
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

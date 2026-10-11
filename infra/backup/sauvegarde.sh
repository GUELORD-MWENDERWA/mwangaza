#!/usr/bin/env bash
# Sauvegardes (4.7.1) : la tâche du jour et la restauration. Lancé par `make backup` et
# `make restore` sur la machine ; sur le serveur, chaque nuit par cron (ligne installée par
# `make deploy`). Pas de planificateur Celery ni de conteneur en plus.
#
#   backup                         purge des sessions expirées, puis dump de la base et archive
#                                  des fichiers (logos, photos, pièces jointes), chiffrés, puis
#                                  rotation
#   restore [FICHIER]              essai : la sauvegarde (la dernière par défaut) est restaurée
#                                  dans une base à part, comparée table par table à la base en
#                                  service, puis la base à part est effacée
#   restore --remplacer [FICHIER]  remettre la sauvegarde en service : la base en service est
#                                  renommée (gardée, rien n'est effacé), les fichiers sont remis
#
# Variables : COMPOSE (commande docker compose de la pile, obligatoire) ; BACKUP_PASSPHRASE (clé
# de chiffrement, sinon lue dans le fichier VALEURS ; vide : purge seulement) ; BACKUP_DIR
# (dossier des sauvegardes) ; BACKUP_KEEP_DAYS (base, 30) et BACKUP_KEEP_FILES_DAYS (fichiers,
# 7) ; MEDIA_DIR (fichiers sur la machine, en développement ; vide : conteneur `django`).
set -euo pipefail
umask 077
cd "$(dirname "$0")/../.."

: "${COMPOSE:?COMPOSE manque : lancer par make backup, make restore ou la tâche planifiée}"
BACKUP_DIR=${BACKUP_DIR:-sauvegardes}
RESTAUREE=mwangaza_restauration
if [ -z "${BACKUP_PASSPHRASE:-}" ] && [ -n "${VALEURS:-}" ]; then
  BACKUP_PASSPHRASE=$(sed -n 's/^BACKUP_PASSPHRASE=//p' "$VALEURS")
fi

# Dans le conteneur de la base : `pg_dump` et `pg_restore` de la même version que PostgreSQL.
# db COMMANDE [ARGUMENTS] — les arguments sont $1, $2… de la commande. `exec` lit l'entrée : les
# appels qui n'en ont pas besoin la ferment, pour ne pas avaler la réponse à une question.
db() { $COMPOSE exec -T db sh -c "$1" sh "${@:2}"; }
# sql BASE REQUÊTE
sql() { db 'psql -U "$POSTGRES_USER" -d "$1" -At -v ON_ERROR_STOP=1 -c "$2"' "$@" </dev/null; }

# « table nombre » pour chaque table de la base : sert à comparer deux bases.
lignes() {
  db 'psql -U "$POSTGRES_USER" -d "$1" -AtF" " -v ON_ERROR_STOP=1' "$1" <<'SQL'
SELECT format('SELECT %L, count(*) FROM %I', tablename, tablename) FROM pg_tables
WHERE schemaname = 'public' ORDER BY tablename COLLATE "C" \gexec
SQL
}

# Fichiers des écoles : sur la machine en développement, sinon dans le volume du conteneur
# django. fichiers -c . (archive sur la sortie) · fichiers -x (archive lue sur l'entrée)
fichiers() {
  if [ -n "${MEDIA_DIR:-}" ]; then
    mkdir -p "$MEDIA_DIR"
    tar -z "$1" -f - -C "$MEDIA_DIR" "${@:2}"
  else
    $COMPOSE exec -T django tar -z "$1" -f - -C /app/media "${@:2}"
  fi
}
compter() { tar -tz | grep -vc '/$' || true; }

# AES-256, clé lue sur le descripteur 3 (jamais dans la liste des processus). Sans le cache de
# gpg : un essai de restauration doit prouver que la clé qu'on a est la bonne.
GPG=(gpg --batch --yes --quiet --no-symkey-cache --pinentry-mode loopback --passphrase-fd 3)
chiffrer() { "${GPG[@]}" --symmetric --cipher-algo AES256 --compress-algo none --output "$1" 3<<<"$BACKUP_PASSPHRASE"; }
dechiffrer() { "${GPG[@]}" --decrypt "$1" 3<<<"$BACKUP_PASSPHRASE"; }

EFFACER='PGOPTIONS="-c client_min_messages=warning" dropdb -U "$POSTGRES_USER" --force --if-exists "$1"'

# Un dump de PostgreSQL, déchiffré avec la clé qu'on a ?
lisible() {
  if [ "$(dechiffrer "$1" 2>/dev/null | head -c 5)" != PGDMP ]; then
    echo "Sauvegarde illisible : mauvaise clé BACKUP_PASSPHRASE, ou fichier abîmé ($1)." >&2
    exit 1
  fi
}

derniere() {
  local trouvees=("$BACKUP_DIR"/mwangaza-*."$1")
  [ -e "${trouvees[-1]}" ] && echo "${trouvees[-1]}"
}

sauvegarder() {
  local nom effacees
  # D'abord la purge : rien d'autre n'efface les sessions finies, et le dump ne les emporte pas.
  effacees=$(sql "$BASE" "WITH d AS (DELETE FROM django_session WHERE expire_date < now() RETURNING 1) SELECT count(*) FROM d")
  echo "Sessions expirées effacées : $effacees"
  if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
    echo "Pas de clé BACKUP_PASSPHRASE : aucune sauvegarde (acceptable pour des données fictives seulement)."
    return
  fi
  mkdir -p "$BACKUP_DIR"
  nom="$BACKUP_DIR/mwangaza-$(date +%Y%m%d-%H%M%S)"
  # Nom provisoire jusqu'au bout : une sauvegarde interrompue ne passe jamais pour une bonne.
  db 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' </dev/null | chiffrer "$nom.base.dump.gpg.partiel"
  fichiers -c . </dev/null | chiffrer "$nom.fichiers.tar.gz.gpg.partiel"
  lisible "$nom.base.dump.gpg.partiel"
  mv "$nom.base.dump.gpg.partiel" "$nom.base.dump.gpg"
  mv "$nom.fichiers.tar.gz.gpg.partiel" "$nom.fichiers.tar.gz.gpg"
  echo "Base : $nom.base.dump.gpg ($(du -h "$nom.base.dump.gpg" | cut -f1))"
  echo "Fichiers : $nom.fichiers.tar.gz.gpg ($(du -h "$nom.fichiers.tar.gz.gpg" | cut -f1))"

  # Rotation, seulement après une sauvegarde réussie. Les fichiers (archive complète, plus
  # lourde) sont gardés moins longtemps que la base.
  find "$BACKUP_DIR" -name 'mwangaza-*.base.dump.gpg' -mtime "+${BACKUP_KEEP_DAYS:-30}" -delete
  find "$BACKUP_DIR" -name 'mwangaza-*.fichiers.tar.gz.gpg' -mtime "+${BACKUP_KEEP_FILES_DAYS:-7}" -delete
  find "$BACKUP_DIR" -name 'mwangaza-*.partiel' -mtime +1 -delete
  echo "Gardées dans $BACKUP_DIR : $(find "$BACKUP_DIR" -name '*.base.dump.gpg' | wc -l) sauvegarde(s) de la base, $(du -sh "$BACKUP_DIR" | cut -f1) en tout"
}

restaurer() {
  local remplacer="" fichier archive avant apres ancienne reponse
  if [ "${1:-}" = --remplacer ]; then
    remplacer=oui
    shift
  fi
  fichier=${1:-$(derniere base.dump.gpg || true)}
  if [ ! -f "$fichier" ]; then
    echo "Aucune sauvegarde à restaurer dans $BACKUP_DIR : make backup d'abord." >&2
    exit 1
  fi
  : "${BACKUP_PASSPHRASE:?BACKUP_PASSPHRASE manque : la clé qui a chiffré la sauvegarde}"
  # Fichiers du même moment ; sinon (rotation plus courte) l'archive la plus récente.
  archive=${fichier%.base.dump.gpg}.fichiers.tar.gz.gpg
  [ -f "$archive" ] || archive=$(derniere fichiers.tar.gz.gpg || true)

  lisible "$fichier"
  echo "Restauration de $fichier dans la base à part « $RESTAUREE »…"
  db "$EFFACER"' && createdb -U "$POSTGRES_USER" "$1"' "$RESTAUREE" </dev/null
  # La base à part ne reste jamais derrière un essai ou un échec : une copie de vraies données.
  trap 'db "$EFFACER" "$RESTAUREE" </dev/null' EXIT
  dechiffrer "$fichier" | db 'pg_restore -U "$POSTGRES_USER" -d "$1" --no-owner --exit-on-error' "$RESTAUREE"

  apres=$(lignes "$RESTAUREE")
  avant=$(lignes "$BASE")
  if ! grep -q '^django_migrations [1-9]' <<<"$apres"; then
    echo "Restauration incomplète : pas de migrations dans la base restaurée." >&2
    exit 1
  fi
  awk '{ n++; s += $2 } END { printf "Base restaurée : %d tables, %d lignes\n", n, s }' <<<"$apres"
  if [ "$avant" = "$apres" ]; then
    echo "Identique à la base en service, table par table."
  else
    echo "Écarts avec la base en service (normaux si elle a servi depuis la sauvegarde) — table : en service → restaurée"
    LC_ALL=C join -a1 -a2 -e - -o 0,1.2,2.2 <(echo "$avant") <(echo "$apres") |
      awk '$2 != $3 { print "  " $1 " : " $2 " → " $3 }'
  fi
  if [ -f "$archive" ]; then
    echo "Fichiers : $(dechiffrer "$archive" | compter) dans $(basename "$archive"), $(fichiers -c . </dev/null | compter) en service"
  else
    echo "Fichiers : aucune archive à restaurer."
  fi

  if [ -z "$remplacer" ]; then
    echo "Essai réussi : la sauvegarde se déchiffre et se restaure. Base à part effacée."
    return
  fi
  ancienne="${BASE}_avant_$(date +%Y%m%d_%H%M%S)"
  echo "Remettre cette sauvegarde en service : tout ce qui a été saisi depuis sera absent de l'application."
  echo "La base en service n'est pas effacée : elle est gardée sous le nom « $ancienne »."
  read -r -p "Taper REMPLACER pour continuer : " reponse
  if [ "$reponse" != REMPLACER ]; then
    echo "Abandonné : rien n'a changé."
    exit 1
  fi
  # Une seule transaction : les deux bases changent de nom ensemble, ou rien ne change.
  sql postgres "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$BASE', '$RESTAUREE') AND pid <> pg_backend_pid();
    ALTER DATABASE \"$BASE\" RENAME TO \"$ancienne\";
    ALTER DATABASE \"$RESTAUREE\" RENAME TO \"$BASE\";" >/dev/null
  trap - EXIT
  [ ! -f "$archive" ] || dechiffrer "$archive" | fichiers -x
  echo "Sauvegarde remise en service. Relancer l'application (make deploy sur le serveur, make dev sur la machine)."
  echo "Ancienne base gardée : « $ancienne » (à effacer à la main quand elle ne sert plus)."
}

BASE=$(db 'echo "$POSTGRES_DB"' </dev/null)
case "${1:-}" in
  backup) sauvegarder ;;
  restore) restaurer "${@:2}" ;;
  *)
    sed -n '2,13p' "$0"
    exit 1
    ;;
esac

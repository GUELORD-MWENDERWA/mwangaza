"""Crée `infra/serveur/serveur.env` du vrai serveur (AWS Lightsail, 4.6.3) avec des secrets neufs,
puis vérifie qu'il est rempli (`make deploy-init`). Hors Git. Ne réécrit jamais un fichier
existant : il y ajoute seulement, à la fin, un secret apparu depuis sa création (`ADDED_LATER`).

Lancé depuis `backend/` par `uv run` : la création des clés Web Push vient du projet.
"""

import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / "serveur.env"
sys.path.insert(0, str(HERE.parent.parent / "backend"))

from apps.notifications.management.commands.webpush_keys import vapid_keys  # noqa: E402

TEMPLATE = """\
# Vrai serveur (AWS Lightsail, 4.6.3) : jamais dans Git. Copié sur le serveur à chaque
# `make deploy`. En garder une copie en lieu sûr (gestionnaire de mots de passe) : sans
# DJANGO_SECRET_KEY, chacun devrait relier son application d'authentification ; sans
# BACKUP_PASSPHRASE, les sauvegardes chiffrées sont illisibles ; sans les clés Web Push, il faut
# réabonner chaque appareil. Changer l'un de ces secrets après de vraies données : ne pas le faire.
MODE=production
# À remplir
SERVEUR=ubuntu@15.237.26.123
SSH_KEY=~/.ssh/LightsailDefaultKey-eu-west-3.pem
MWANGAZA_DOMAIN=mwangazaschool.com
ACME_EMAIL=
CLOUDFLARE_API_TOKEN=
# La suite est remplie toute seule.
CADDY_TLS=unused
DJANGO_SECRET_KEY={secret}
POSTGRES_PASSWORD={password}
POSTGRES_APP_PASSWORD={app_password}
BACKUP_PASSPHRASE={backup}
# Copie des sauvegardes hors du serveur (Backblaze B2, 4.7.2) : bucket privé et clé limitée à ce
# bucket. Vide : sauvegardes gardées sur le serveur seulement.
BACKUP_B2_BUCKET=
BACKUP_B2_ACCOUNT=
BACKUP_B2_KEY=
# Alerte si la sauvegarde de la nuit manque ou échoue (adresse de ping Healthchecks.io). Facultatif.
BACKUP_PING_URL=
# Suivi d'erreurs (Sentry, adresse « DSN » du projet). Facultatif.
SENTRY_DSN=
WEBPUSH_VAPID_PUBLIC_KEY={public}
WEBPUSH_VAPID_PRIVATE_KEY={private}
GUNICORN_WORKERS=3
DJANGO_HSTS_SECONDS=2592000
DJANGO_LOG_LEVEL=INFO
"""

REQUIRED = ("SERVEUR", "SSH_KEY", "MWANGAZA_DOMAIN", "ACME_EMAIL", "CLOUDFLARE_API_TOKEN")
# Secrets apparus après la création des premiers `serveur.env`. `POSTGRES_APP_PASSWORD` (S.5) :
# compte PostgreSQL de l'application, remis à cette valeur à chaque mise en ligne.
ADDED_LATER = ("POSTGRES_APP_PASSWORD",)


def read_env() -> dict[str, str]:
    values = {}
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def init() -> None:
    if not ENV_FILE.exists():
        public, private = vapid_keys()
        ENV_FILE.write_text(
            TEMPLATE.format(
                secret=secrets.token_urlsafe(50),
                password=secrets.token_urlsafe(24),
                app_password=secrets.token_urlsafe(24),
                backup=secrets.token_urlsafe(32),
                public=public,
                private=private,
            )
        )
        ENV_FILE.chmod(0o600)
    values = read_env()
    for key in ADDED_LATER:
        if key not in values:
            text = ENV_FILE.read_text()
            ENV_FILE.write_text(f"{text.rstrip()}\n{key}={secrets.token_urlsafe(24)}\n")
            print(f"{key} ajouté à infra/serveur/serveur.env : mets à jour ta copie en lieu sûr.")
    missing = [key for key in REQUIRED if not values.get(key)]
    if missing:
        sys.exit(f"Remplis {', '.join(missing)} dans infra/serveur/serveur.env.")


if __name__ == "__main__":
    init()

# Production : images construites sur le serveur par `docker compose build` (`docker-compose.yml`).
# Contexte : la racine du dépôt, filtrée par `.dockerignore` (jamais `prive/`, `depot/` ni `.env`).
#   backend : Django (gunicorn) et Celery
#   caddy   : HTTPS, les deux PWA construites et les fichiers statiques de Django
#   caddy-production : la même, avec le module Cloudflare, pour le vrai serveur (4.6.3)

# --- Front : Gestion et Portail construits (vérification des types comprise)
FROM node:22-slim AS front
# Téléchargements gardés en cache entre deux constructions (`--mount=type=cache`) et délais
# longs : une connexion lente ou coupée reprend où elle s'était arrêtée.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    CI=true \
    pnpm_config_store_dir=/pnpm-store \
    pnpm_config_fetch_timeout=300000 \
    pnpm_config_workspace_concurrency=1 \
    NODE_OPTIONS=--max-old-space-size=1024
# Une application à la fois (tsc + Vite) et 1 Go de mémoire pour Node : sur le serveur de 2 Go,
# les trois ensemble saturaient la mémoire et figeaient la machine (2026-10-13).
RUN corepack enable
WORKDIR /front
# Paquets téléchargés d'après le seul fichier de verrouillage : refait seulement s'il change.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN --mount=type=cache,id=mwangaza-pnpm,target=/pnpm-store pnpm fetch
COPY frontend/ ./
RUN --mount=type=cache,id=mwangaza-pnpm,target=/pnpm-store \
    pnpm install --offline --frozen-lockfile && pnpm build

# --- Backend : Django, gunicorn, Celery
# FORWARDED_ALLOW_IPS : seul Caddy joint gunicorn (réseau interne), ses en-têtes X-Forwarded-* sont crus.
FROM python:3.12-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_HTTP_TIMEOUT=300 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    FORWARDED_ALLOW_IPS="*"

# Pango, HarfBuzz et une police pour WeasyPrint (PDF).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN --mount=type=cache,id=mwangaza-uv,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
# Fichiers statiques de l'administration, copiés ensuite dans l'image de Caddy. La clé ne sert
# qu'à cette commande (`settings/prod.py` refuse de démarrer sans clé).
RUN DJANGO_SECRET_KEY=collectstatic-seulement python manage.py collectstatic --noinput \
    && useradd --system --uid 10001 app \
    && mkdir -p media && chown app media
USER app
EXPOSE 8000
# Les migrations tournent avant, dans le service `migrate` (`docker-compose.yml`) : ce conteneur-ci
# n'a que le compte PostgreSQL à droits réduits (S.5).
CMD ["sh", "-c", "exec gunicorn config.wsgi --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout 120"]

# --- Caddy : HTTPS, PWA et fichiers statiques
FROM caddy:2-alpine AS caddy
COPY infra/Caddyfile infra/routes.caddy /etc/caddy/
COPY --from=front /front/apps/gestion/dist /srv/gestion
COPY --from=front /front/apps/portail/dist /srv/portail
COPY --from=front /front/apps/console/dist /srv/console
COPY --from=backend /app/staticfiles /srv/static

# --- Vrai serveur : Caddy avec le module Cloudflare (certificat joker par DNS)
FROM caddy:2-builder AS caddy-production-builder
# La compilation Go ne démarre qu'après la construction du front : jamais les deux en même temps
# (mémoire du serveur de 2 Go) ; ce fichier n'existe que pour créer cet ordre.
COPY --from=front /front/pnpm-workspace.yaml /tmp/ordre
ENV GOMAXPROCS=1 GOMEMLIMIT=700MiB
RUN xcaddy build --with github.com/caddy-dns/cloudflare@v0.2.4

FROM caddy AS caddy-production
COPY --from=caddy-production-builder /usr/bin/caddy /usr/bin/caddy
COPY infra/production/Caddyfile /etc/caddy/Caddyfile

# Commandes du projet Mwangaza — `make` ou `make help` pour la liste.

ifneq (,$(wildcard .env))
include .env
export $(shell sed -n 's/^\([A-Z_][A-Z0-9_]*\)=.*/\1/p' .env)
endif

COMPOSE := docker compose -f infra/docker-compose.dev.yml
MANAGE := cd backend && uv run python manage.py

.DEFAULT_GOAL := help
.PHONY: help install hooks dev services db-up stop reset-db dev-local migrate makemigrations demo demo-excel totp messages superuser shell \
	test test-back test-front test-e2e lint lint-back lint-front format api api-schema build

help: ## Afficher les commandes
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-15s %s\n", $$1, $$2}'

install: ## Installer les dépendances (Python avec uv, front avec pnpm) et les contrôles avant commit
	cd backend && uv sync
	cd frontend && pnpm install
	$(MAKE) hooks

hooks: ## Installer les contrôles automatiques avant chaque commit (pre-commit)
	cd backend && uv run pre-commit install

dev: ## Tout lancer dans Docker : base, Redis, Django, Celery, Gestion, Portail
	cd frontend && pnpm install --frozen-lockfile
	$(COMPOSE) up --build

services: ## Lancer seulement PostgreSQL (port 5433) et Redis dans Docker (automatique avec dev-local, migrate, demo, test…)
	$(COMPOSE) up -d --wait db redis

# PostgreSQL et Redis lancés et prêts avant les commandes qui s'en servent, sans bruit (rien à
# faire s'ils tournent déjà). Pas en CI : GitHub Actions fournit sa propre base.
db-up:
ifndef CI
	@$(COMPOSE) --progress quiet up -d --wait db redis
endif

stop: ## Arrêter les conteneurs
	$(COMPOSE) down

# Pour une base de développement qu'une migration ne peut plus suivre (ex. nouveau modèle
# d'utilisateur en 1.2). Seulement la base de Docker : rien que des données fictives.
reset-db: ## Effacer la base de développement (et celle des tests), puis la recréer : migrations et données fictives
	$(COMPOSE) down --volumes
	$(MAKE) migrate demo

# Ctrl+C arrête les trois serveurs proprement : bash laisse chacun recevoir le Ctrl+C (sh le leur
# ferait ignorer), puis attend qu'ils aient fini. Vite lancé app par app : `pnpm dev` signalerait
# à tort un échec (« Failed », ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL) à chaque arrêt.
dev-local: SHELL := /bin/bash
dev-local: db-up ## Lancer Django et Vite sur la machine (base décrite dans .env) ; Ctrl+C pour arrêter
	@(cd backend && exec uv run python manage.py runserver) & \
	(cd frontend/apps/gestion && exec pnpm exec vite) & \
	(cd frontend/apps/portail && exec pnpm exec vite) & \
	trap 'wait; exit 0' INT; wait

migrate: db-up ## Appliquer les migrations
	$(MANAGE) migrate

makemigrations: db-up ## Créer des migrations : make makemigrations app=finance name=exchange_rate
	$(MANAGE) makemigrations $(app) $(if $(name),--name $(name))

demo: db-up ## Créer ou remettre à jour les données fictives de démonstration (écoles itig et volcans)
	$(MANAGE) demo

demo-excel: ## Liste d'élèves fictive (eleves-fictifs.xlsx, ~800 élèves) pour essayer l'import
	$(MANAGE) demo_excel ../eleves-fictifs.xlsx

totp: ## Code de double authentification du moment : comptes fictifs, ou make totp key=<clé>
	@$(MANAGE) totp $(if $(key),--key "$(key)")

messages: ## Traductions du serveur (backend/locale) : extraire les textes, puis compiler (demande gettext)
	$(MANAGE) makemessages -l fr --no-obsolete
	$(MANAGE) compilemessages -l fr --ignore=.venv

superuser: db-up ## Créer un compte super-administrateur
	$(MANAGE) createsuperuser

shell: db-up ## Console Django
	$(MANAGE) shell

test: test-back test-front ## Lancer tous les tests

test-back: db-up ## Tests backend (pytest)
	cd backend && uv run pytest

test-front: ## Tests front : vérification des types puis Vitest
	cd frontend && pnpm typecheck && pnpm test

test-e2e: db-up ## Parcours dans Chromium (Playwright) : Django + Gestion ; remet les données de make demo à zéro
	cd frontend && pnpm exec playwright test

lint: lint-back lint-front ## Vérifier le code sans rien modifier (ruff, ESLint, Prettier)

lint-back: ## Vérifier le code Python (ruff)
	cd backend && uv run ruff check . && uv run ruff format --check .

lint-front: ## Vérifier le code front (ESLint, Prettier)
	cd frontend && pnpm lint && pnpm format:check

format: ## Corriger automatiquement le format et ce qui peut l'être (ruff, ESLint, Prettier)
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm lint --fix && pnpm format

api: api-schema ## Schéma OpenAPI (frontend/packages/api/openapi.yaml) puis types TypeScript du client
	cd frontend && pnpm --filter @mwangaza/api generate

api-schema: ## Seulement le schéma OpenAPI (CI du backend, sans pnpm)
	$(MANAGE) spectacular --validate --fail-on-warn --file ../frontend/packages/api/openapi.yaml

build: ## Construire les deux PWA
	cd frontend && pnpm build

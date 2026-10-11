# Commandes du projet Mwangaza — `make` ou `make help` pour la liste.

ifneq (,$(wildcard .env))
include .env
DEV_VARS := $(shell sed -n 's/^\([A-Z_][A-Z0-9_]*\)=.*/\1/p' .env)
export $(DEV_VARS)
endif
# Les essais de la production ne voient pas les variables du développement : docker compose les
# préférerait aux valeurs de leur fichier --env-file.
WITHOUT_DEV_ENV := env $(addprefix -u ,$(DEV_VARS))

COMPOSE := docker compose -f infra/docker-compose.dev.yml
# Essai de la production sur la machine : mêmes images que le serveur, valeurs de infra/local.env.
PROD_LOCAL := $(WITHOUT_DEV_ENV) docker compose -f infra/docker-compose.yml --env-file infra/local.env -p mwangaza-essai
# Essai sur plusieurs appareils du même réseau (adresse DuckDNS, vrai certificat) : valeurs de
# infra/reseau/reseau.env (hors Git), créé par `make reseau`.
RESEAU := $(WITHOUT_DEV_ENV) docker compose -f infra/docker-compose.yml -f infra/docker-compose.reseau.yml --env-file infra/reseau/reseau.env -p mwangaza-reseau
ESSAI := cd backend && uv run python ../infra/reseau/essai.py
# Serveur de démonstration en ligne (Oracle Cloud + DuckDNS), piloté par SSH : valeurs de
# infra/serveur/serveur.env (hors Git), créé au premier lancement.
DEPLOYER := infra/serveur/deployer.sh
# Sauvegardes (4.7.1) : la pile du développement, ou les images du serveur avec pile=reseau ou
# pile=essai. Un dossier par pile : on ne restaure pas la sauvegarde d'une pile dans une autre.
pile ?= dev
SAUVEGARDE_dev := COMPOSE='$(COMPOSE)' MEDIA_DIR=backend/media
SAUVEGARDE_essai := COMPOSE='$(PROD_LOCAL)'
SAUVEGARDE_reseau := COMPOSE='$(RESEAU)'
SAUVEGARDE := $(SAUVEGARDE_$(pile)) BACKUP_DIR=sauvegardes/$(pile) infra/backup/sauvegarde.sh
MANAGE := cd backend && uv run python manage.py

.DEFAULT_GOAL := help
.PHONY: help install hooks dev services db-up stop reset-db dev-local migrate makemigrations demo demo-excel totp messages superuser shell \
	test test-back test-front test-e2e lint lint-back lint-front format api api-schema build \
	prod-local prod-local-stop reseau reseau-ip reseau-demo reseau-superuser reseau-stop \
	deploy-setup deploy deploy-demo deploy-superuser deploy-logs deploy-ssh backup restore

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
	(cd frontend/apps/console && exec pnpm exec vite) & \
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

guide: db-up ## Guide de la version en PDF (docs/guide/) : captures des écrans de chaque rôle sur make demo
	cd frontend && pnpm exec playwright test -c guide/playwright.config.ts

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
	$(MANAGE) spectacular --lang en --validate --fail-on-warn --file ../frontend/packages/api/openapi.yaml

build: ## Construire les deux PWA
	cd frontend && pnpm build

prod-local: ## Essayer la production sur la machine (images du serveur, Caddy) : https://itig.localhost/app/
	mkdir -p infra/certs
	$(PROD_LOCAL) up --build --detach --wait
	@echo "Prêt : https://itig.localhost/app/ · https://parents.localhost/ · https://admin.localhost/admin/ (certificat local : accepter l'avertissement)"

prod-local-stop: ## Arrêter l'essai de la production (données gardées ; tout effacer : ajouter --volumes à la commande)
	$(PROD_LOCAL) down

reseau: ## Essai sur plusieurs appareils du même réseau, vrai certificat (A-FAIRE.md § 9 bis) : https://www.<adresse>.duckdns.org/
	$(ESSAI) init
	$(ESSAI) ip
	$(ESSAI) accueil
	mkdir -p infra/certs
	$(PROD_LOCAL) down
	$(RESEAU) up --build --detach --wait
	@$(ESSAI) adresses

reseau-ip: ## Remettre l'adresse de la machine dans DuckDNS (réseau changé) ; make reseau-ip ip=… pour la choisir
	$(ESSAI) ip $(ip)

reseau-demo: ## Données fictives dans l'essai sur plusieurs appareils (espaces de démonstration, sans code)
	$(RESEAU) exec django python manage.py demo

reseau-superuser: ## Créer un compte super-admin dans l'essai sur plusieurs appareils (console)
	$(RESEAU) exec django python manage.py createsuperuser

reseau-stop: ## Arrêter l'essai sur plusieurs appareils (données et certificat gardés)
	$(RESEAU) down

deploy-setup: ## Serveur de démonstration en ligne : le préparer, une seule fois (A-FAIRE.md § 9 ter)
	$(DEPLOYER) setup

deploy: ## Mettre en ligne main sur le serveur de démonstration ; make deploy ref=origin/<branche> pour une autre
	$(DEPLOYER) deploy $(ref)

deploy-demo: ## Données fictives sur le serveur de démonstration (mot de passe propre au serveur, dans serveur.env)
	$(DEPLOYER) demo

deploy-superuser: ## Créer un compte super-admin sur le serveur de démonstration
	$(DEPLOYER) superuser

deploy-logs: ## Derniers journaux du serveur de démonstration ; make deploy-logs service=django
	$(DEPLOYER) logs $(service)

deploy-ssh: ## Ouvrir une session sur le serveur de démonstration
	$(DEPLOYER) ssh

# Clé de la machine (données fictives) si `.env` n'en donne pas ; un vrai serveur a la sienne.
backup restore: export BACKUP_PASSPHRASE ?= mwangaza-dev

backup: $(if $(filter dev,$(pile)),db-up) ## Sauvegarde chiffrée de la base et des fichiers dans sauvegardes/ (sessions expirées purgées, rotation)
	@$(SAUVEGARDE) backup

restore: $(if $(filter dev,$(pile)),db-up) ## Essai de restauration dans une base à part ; make restore file=<sauvegarde> ; remplacer=oui : la remettre en service
	@$(SAUVEGARDE) restore $(if $(remplacer),--remplacer) $(file)

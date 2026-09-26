# Commandes du projet Mwangaza — `make` ou `make help` pour la liste.

ifneq (,$(wildcard .env))
include .env
export $(shell sed -n 's/^\([A-Z_][A-Z0-9_]*\)=.*/\1/p' .env)
endif

COMPOSE := docker compose -f infra/docker-compose.dev.yml
MANAGE := cd backend && uv run python manage.py

.DEFAULT_GOAL := help
.PHONY: help install dev services stop dev-local migrate makemigrations superuser shell \
	test test-back test-front lint api build

help: ## Afficher les commandes
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-15s %s\n", $$1, $$2}'

install: ## Installer les dépendances (Python avec uv, front avec pnpm)
	cd backend && uv sync
	cd frontend && pnpm install

dev: ## Tout lancer dans Docker : base, Redis, Django, Celery, Gestion, Portail
	$(COMPOSE) up --build

services: ## Lancer seulement PostgreSQL (port 5433) et Redis dans Docker, pour dev-local
	$(COMPOSE) up -d db redis

stop: ## Arrêter les conteneurs
	$(COMPOSE) down

dev-local: ## Lancer Django et Vite sur la machine (base décrite dans .env)
	@trap 'kill 0' INT TERM; \
	(cd backend && uv run python manage.py runserver) & \
	(cd frontend && pnpm dev) & \
	wait

migrate: ## Appliquer les migrations
	$(MANAGE) migrate

makemigrations: ## Créer des migrations : make makemigrations app=finance name=exchange_rate
	$(MANAGE) makemigrations $(app) $(if $(name),--name $(name))

superuser: ## Créer un compte super-administrateur
	$(MANAGE) createsuperuser

shell: ## Console Django
	$(MANAGE) shell

test: test-back test-front ## Lancer tous les tests

test-back: ## Tests backend (pytest)
	cd backend && uv run pytest

test-front: ## Tests front (Vitest arrive en 0.2 ; en attendant, vérification des types)
	cd frontend && pnpm typecheck

lint: ## Lint et format (ruff, ESLint, Prettier arrivent en 0.2)
	@echo "Lint : mis en place par la tâche 0.2."

api: ## Écrire le schéma OpenAPI dans frontend/packages/api/openapi.yaml
	$(MANAGE) spectacular --validate --fail-on-warn --file ../frontend/packages/api/openapi.yaml

build: ## Construire les deux PWA
	cd frontend && pnpm build

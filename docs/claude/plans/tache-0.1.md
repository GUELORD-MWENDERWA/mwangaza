# Plan — Tâche 0.1 : monorepo, Docker Compose de développement, commandes

Issue GitHub : #5 · Branche prévue : `tache/0.1-monorepo` · Statut : **validé le 2026-09-25** — Docker (installé par l’utilisateur), uv, commit + PR à chaque tâche

## But

Poser la structure du dépôt décrite dans `docs/03-architecture-technique.md` § 3, pouvoir lancer toute l'application en développement avec une commande, et remplir la section « Commandes » de `CLAUDE.md`. Aucune fonction métier : elle commence en 1.1.

## Ce que la machine a déjà

| Outil | État |
|---|---|
| Python 3.12.3, `venv` | ✔ |
| Node 22 (nvm), corepack | ✔ — pnpm s'active par `corepack enable pnpm`, sans sudo |
| PostgreSQL 16 | ✔ installé et démarré (port 5432) |
| Redis | ✘ absent |
| Docker | ✘ absent — l'installation demande sudo |
| make | ✔ |
| Sous-domaines locaux | ✔ `itig.localhost` résout vers la machine → test du multi-écoles par sous-domaine possible en dev |

## Fichiers créés

```
backend/
├── pyproject.toml          dépendances + configuration ruff et pytest
├── manage.py
├── config/
│   ├── settings/ base.py, dev.py, test.py, prod.py   (lecture de l'environnement avec os.environ, sans bibliothèque)
│   ├── urls.py             /api/health/ + /api/schema/ (drf-spectacular)
│   ├── celery.py, wsgi.py, asgi.py
├── apps/__init__.py        les apps métier arrivent avec leurs tâches (core en 1.1…)
├── tests/test_health.py    premier test : /api/health/ répond 200 et vérifie la base
└── Dockerfile.dev
frontend/
├── package.json, pnpm-workspace.yaml, tsconfig.base.json
├── apps/gestion/           Vite + React + TypeScript minimal (le vrai squelette PWA / Tailwind / shadcn est la tâche 1.6)
├── apps/portail/           idem
└── packages/api, ui, i18n, money/   package.json vide + README d'une ligne (remplis dans leurs tâches)
infra/
├── docker-compose.dev.yml  postgres 16, redis 7, django (runserver), celery, vite gestion, vite portail
└── README.md               ce qui viendra en 4.6 / 4.7 (Caddyfile, compose de prod, sauvegardes)
firmware/README.md          « V1.2 — lecteurs RFID ESP32 »
Makefile                    commandes du projet
.env.example                variables (base, secret, domaine) — jamais de vraie valeur
.editorconfig
```

## Commandes prévues (section « Commandes » de CLAUDE.md)

| Commande | Effet |
|---|---|
| `make install` | venv Python + dépendances, `pnpm install` |
| `make dev` | Docker : tout le système ; sans Docker : Django + Vite en local sur PostgreSQL local |
| `make migrate` / `make makemigrations app=…` | migrations |
| `make test` | pytest + Vitest |
| `make lint` / `make format` | ruff, ESLint, Prettier (outils posés en 0.2) |
| `make api` | schéma OpenAPI → client TypeScript `packages/api` (branché en 1.x) |
| `make build` | build des deux PWA |

En dev : Gestion sur `http://itig.localhost:5173/app`, Portail sur `http://localhost:5174`, API derrière le proxy Vite (`/api` → Django :8000) pour garder les cookies sur la même origine. Sans Redis, Celery s'exécute en mode synchrone (`CELERY_TASK_ALWAYS_EAGER`).

## Dépendances ajoutées (toutes prévues par la stack, sauf mention)

- Python : `django~=5.2`, `djangorestframework`, `drf-spectacular`, `celery`, `redis`, **`psycopg[binary]`** (pilote PostgreSQL, indispensable), `pytest`, `pytest-django`, `factory-boy`. *(Réalisé : `ruff` reporté à 0.2 avec sa configuration.)*
- Front : `pnpm`, `vite`, `react`, `react-dom`, `typescript`, `@vitejs/plugin-react`, `@types/react`, `@types/react-dom`. *(Réalisé : React 19.3, Vite 8.3, TypeScript 7.0 ; `@types/node` évité en sortant `vite.config.ts` de la vérification de types.)*
- Rien d'autre : pas de `django-environ` ni de `python-dotenv` (lecture de l'environnement faite à la main).
- UUID v7 (tâche 1.1) : Python 3.12 n'a pas `uuid7` → petite fonction maison de ~20 lignes testée, sans dépendance.

## Décisions à valider

1. **Docker** : l'installer maintenant (`sudo`, ~5 min) — recommandé, c'est la stack décidée et la production l'utilise. En attendant, tout marche aussi en local.
2. **Gestionnaire Python** : `uv` (recommandé : rapide, fichier de verrouillage, gère le venv) ou `pip` + `requirements.txt` verrouillé.
3. **Commits** : autorisation de commiter, pousser et ouvrir la PR à la fin de chaque tâche sans redemander.

## Tests et vérification

- `make test` : le test de santé passe (base joignable).
- `make dev` : `http://itig.localhost:5173/app` affiche la page minimale de la Gestion, `/api/health/` répond via le proxy, `/api/schema/` renvoie l'OpenAPI.
- `/verifier` → `docs/claude/revues/tache-0.1.md`.

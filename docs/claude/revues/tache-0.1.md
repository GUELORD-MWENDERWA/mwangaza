# Revue — Tâche 0.1 (2026-09-25)

Périmètre : branche `tache/0.1-monorepo` (backend, frontend, infra, Makefile, documents). Aucun modèle métier.

| # | Règle | Résultat | Preuve |
|---|---|---|---|
| 1 | Isolation des écoles | sans objet | aucun modèle ; `ALLOWED_HOSTS = [".localhost", …]` et proxy `changeOrigin: false` préparent le sous-domaine pour 1.1 |
| 2 | Argent en entiers | sans objet | aucun montant |
| 3 | Paiements immuables | sans objet | — |
| 4 | UUID v7 et idempotence | sans objet | prévu en 1.1 (fonction maison, sans dépendance) |
| 5 | Audit | sans objet | — |
| 6 | Permissions serveur | ✔ | `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES = IsAuthenticated` (`backend/config/settings/base.py`) ; seul `/api/health/` est ouvert explicitement (`AllowAny`, ne renvoie aucune donnée) ; `/api/schema/` et `/api/docs/` seulement en `DEBUG` (`backend/config/urls.py`) |
| 7 | i18n | ✔ | pages minimales : seulement la marque « Mwangaza » et des codes d'état ; i18next arrive en 1.6 ; `LANGUAGE_CODE = "fr"`, `LANGUAGES` fr / en |
| 8 | Pas de nouvelle dépendance non acceptée | ✔ | toutes dans la stack ou validées avec le plan : `psycopg[binary]`, `uv`, `@vitejs/plugin-react`, `@types/react*` ; `@types/node` évité (config Vite hors vérification de types) ; `ruff` reporté en 0.2 |
| 9 | Conventions | ✔ | code en anglais ; `backend/apps/` prêt pour une app par domaine ; workspace `frontend/apps` + `frontend/packages` |
| 10 | Périmètre | ✔ | rien au-delà de 0.1 |
| 11 | Design | sans objet | squelette visuel en 1.6 |
| 12 | Secrets | ✔ | `.env` ignoré ; `prod` refuse de démarrer sans `DJANGO_SECRET_KEY` ; mots de passe de `docker-compose.dev.yml` réservés au développement |
| 13 | Tests et qualité | ✔ | `make test-back` : 3 passés ; `make test-front` (types) : OK ; `make build` : OK ; `check --deploy` : seul W021 (préchargement HSTS, décision reportée en 4.6) ; parcours complet vérifié à la main (voir plus bas) |
| 14 | Suivi | ✔ | case cochée, `docs/06-suivi.md` et journal des décisions mis à jour |

## Vérification manuelle (`make dev-local`, base PostgreSQL 16 temporaire)

- `http://localhost:8000/api/health/` → `{"status":"ok","database":"ok"}`
- `http://itig.localhost:5173/app/` → 200 ; `http://itig.localhost:5173/api/health/` (proxy) → ok
- `http://localhost:5174/` → 200 ; `/api/health/` via le proxy du Portail → ok
- `/api/schema/` et `/api/docs/` → 200 en dev

## Non vérifié

- `make dev` (Docker) : Docker pas encore installé ; fichier `infra/docker-compose.dev.yml` validé seulement en lecture YAML. À lancer une fois Docker installé.

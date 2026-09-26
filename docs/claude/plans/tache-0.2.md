# Plan — Tâche 0.2 : qualité (ruff, pytest, ESLint, Prettier, Vitest, pre-commit, GitHub Actions)

Issue GitHub : #6 · Branche : `tache/0.2-qualite` (partie de `docs/decisions-q1-q11`, PR #78, à fusionner avant) · Statut : en cours depuis le 2026-09-26

## But

Mêmes contrôles partout, avec les mêmes commandes : sur la machine (`make lint`, `make test`), avant chaque commit (pre-commit) et sur GitHub à chaque PR (GitHub Actions). Aucune fonction métier.

## Dépendances ajoutées (toutes des outils de développement, rien dans l'application livrée)

Prévues par la stack de `CLAUDE.md` : ruff, pre-commit, ESLint, Prettier, Vitest. Nécessaires pour les faire marcher :

| Paquet | Où | Pourquoi |
|---|---|---|
| `ruff` | `backend`, groupe `dev` | lint + format Python |
| `pre-commit` | `backend`, groupe `dev` | lance les contrôles avant chaque commit ; version verrouillée par `uv.lock` |
| `eslint`, `@eslint/js` | `frontend` (racine) | lint TypeScript / React, règles de base |
| `typescript-eslint` | `frontend` | lecture du TypeScript par ESLint |
| `typescript@~6.0` | `frontend` (racine seulement) | `typescript-eslint` 8.70 n'accepte que TypeScript < 6.1, et le paquet `typescript` 7 (réécrit en Go) n'a plus l'API JavaScript. Les applications gardent TypeScript 7 pour `tsc` ; ESLint lit le code avec la 6.0 (même syntaxe). À retirer quand `typescript-eslint` gérera la 7 |
| `eslint-plugin-react-hooks` | `frontend` | règles des hooks React (vraies erreurs : dépendances d'effet, hooks conditionnels) |
| `globals` | `frontend` | variables globales du navigateur et de Node pour ESLint |
| `eslint-config-prettier` | `frontend` | coupe les règles ESLint de mise en forme, laissées à Prettier |
| `prettier` | `frontend` | format du code front |
| `vitest` | `frontend` | tests du front |

Écartés : `eslint-plugin-react-refresh` (confort du rechargement à chaud, pas indispensable) ; `jsdom` et Testing Library (arrivent en 1.6 avec les premiers composants) ; Oxlint (plus rapide et sans TypeScript, mais ce serait changer la stack).

## Fichiers

| Fichier | Contenu |
|---|---|
| `backend/pyproject.toml` | `[tool.ruff]` : ligne de 100, Python 3.12, règles E, W, F, I, UP, B, DJ, SIM, RUF ; migrations exclues |
| `frontend/package.json` | scripts `lint`, `format`, `format:check`, `test` ; dépendances ci-dessus |
| `frontend/eslint.config.mjs` | configuration plate ESLint 10 |
| `frontend/.prettierrc.json`, `.prettierignore` | style actuel du code (guillemets doubles, points-virgules, 100 colonnes) ; lockfile, `openapi.yaml` généré et Markdown exclus |
| `frontend/vitest.config.ts` | tests `*.test.ts(x)` des applications et des paquets, environnement Node |
| `frontend/apps/{gestion,portail}/vite.config.test.ts` | premiers tests : le proxy de développement garde le sous-domaine de l'école (`changeOrigin: false`), sert `/api`, `/admin`, `/static`, et suit `VITE_API_TARGET` (cas `make dev`) |
| `.pre-commit-config.yaml` | hooks locaux (mêmes versions que `make lint`) : ruff, ESLint, Prettier ; refus d'un `.env` ou d'une clé privée |
| `.github/workflows/ci.yml` | 2 jobs : backend (PostgreSQL 16, `uv sync --locked`, `make lint-back test-back`, schéma OpenAPI à jour) et frontend (`pnpm install --frozen-lockfile`, `make lint-front test-front build`) |
| `Makefile` | `lint` = `lint-back` + `lint-front` (vérifie sans modifier), `format` (corrige), `test-front` = types + Vitest, `hooks` (installe pre-commit ; aussi lancé par `make install`) |
| `CLAUDE.md`, `A-FAIRE.md` § 11 | commandes |

## Tests prévus

- Vitest : 2 fichiers (gestion, portail) — proxy, sous-domaine, cible de l'API, base d'URL.
- pytest : les 7 tests existants, lancés aussi par GitHub Actions contre PostgreSQL 16.
- Vérifier que `make lint` échoue sur une faute volontaire (Python et TypeScript), que pre-commit bloque un `.env`, puis que la CI passe sur la PR.

## Risques

- Premier formatage : ruff et Prettier peuvent reformater quelques fichiers existants (commit séparé).
- Hooks pre-commit : ils appellent `uv` et `frontend/node_modules/.bin` ; si `uv` n'est pas dans le `PATH` du programme qui commite (VS Code), le hook échoue avec un message clair.
- Téléchargements à l'installation (connexion de Goma) : quelques Mo côté front.

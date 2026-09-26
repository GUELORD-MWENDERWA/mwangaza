# Suivi du projet

Ce fichier dit **où en est le projet**. Il est mis à jour à chaque étape (début et fin de tâche, décision, document reçu, blocage). Les cases à cocher restent dans `05-plan-de-travail.md` ; ici on garde l'état, l'avancement et le journal.

## État actuel

| | |
|---|---|
| Phase | V1.0 — semaine 1 (Socle) |
| Lot | V1.0 — semaine 1 (Socle) |
| Tâche en cours | aucune — 1.1 terminée, PR à relire et fusionner |
| Prochaine tâche | 1.2 — app `accounts` : `User`, `Membership`, `Role`, 9 rôles système |
| Issue GitHub | #7 (1.1, fermée à la fusion de la PR) · prochaine : #8 (1.2) |
| Branche | `tache/1.1-core-tenant` (partie de `main`) ; dossier local : `~/Projets/mwangaza` |
| Dernière mise à jour | 2026-09-26 |

## Avancement

| Bloc | Fait | Total |
|---|:-:|:-:|
| Avant de coder (toi) | 2 | 4 |
| Semaine 1 — Socle | 3 | 9 |
| Semaine 2 — Élèves et frais | 0 | 7 |
| Semaine 3 — Caisse et hors-ligne | 0 | 8 |
| Semaine 4 — Rapports, portail, production | 0 | 8 |
| **V1.0** | **3** | **32** |
| V1.1 — semaines 5 à 8 | 0 | 9 |
| V1.2 — semaines 9 à 14 | 0 | 11 |
| V2 | 0 | 15 |

Sur GitHub : onglet *Milestones* — V1.0 (36 issues, dont les 4 « avant de coder »), V1.1 (9), V1.2 (11), V2 (15).

## Bloquants et en attente

Liste complète et détaillée (maquettes M1–M20, informations I1–I18, décisions T1–T6) : `07-a-fournir.md` — plus rien n'y bloque le travail. Ce que l'utilisateur doit faire et comment : `../A-FAIRE.md`. Ici, seulement ce qui bloque bientôt.

| Sujet | Attendu de | Bloque |
|---|---|---|
| Achat du domaine `mwangaza.school` (vérifier d'abord la disponibilité) | toi | 4.6 |
| Comptes VPS, Cloudflare (GitHub : fait) | toi | 4.6 |
| Stockage objet (sauvegardes, photos) | toi | 4.7 |

## Questions ouvertes

À trancher au plus tard pendant la tâche indiquée. Une fois tranchée : déplacer dans le journal.

Aucune : Q1 à Q11 tranchées le 2026-09-26 (voir le journal). Prochain numéro : Q12.

## Journal

Entrée la plus récente en haut. Format : date — titre, puis fait / tests / décisions / suite.

### 2026-09-26 — Tâche 1.1 : app `core` (isolation des écoles, UUID v7, `Money`)

- **Fait** : app `core` : `uuid7()` et `is_uuid7()` ; `BaseModel` (UUID v7, dates) ; `TenantModel` et `TenantManager` (lecture limitée à l'école courante, erreur sans école ; écriture, suppression, déplacement ou lien vers une autre école refusés, `bulk_create` compris) ; école courante (`use_school`) ; `TenantMiddleware` (sous-domaine → école, 404 si inconnue, 403 si suspendue, pas d'école pour `localhost`, `parents.`, `admin.`…) ; `Money` et `Currency` (entiers, conversion Q4) ; format des erreurs de l'API `{code, detail}`. App `schools` : `School` minimal (code = sous-domaine, nom, statut), admin, `GET /api/school/` (public : code et nom, pour l'écran de connexion). `make demo` : écoles `itig` « ITIG Don Bosco Goma (démo) » et `volcans` « Complexe scolaire Les Volcans (fictif) ». Skills `backend` et `argent`, `03` § 4, `07` § 4, `CLAUDE.md`, `A-FAIRE.md` à jour.
- **Tests** : 160 pytest passés (153 nouveaux : 25 d'isolation des modèles, 10 du middleware, 17 de lecture du sous-domaine, 14 UUID v7, 58 `Money`, `School`, `/api/school/`, `make demo`) ; types et 8 Vitest OK ; lint OK ; build OK. 10 erreurs volontaires toutes détectées. Essai réel avec `make dev-local` : `http://itig.localhost:5173/api/school/` → itig, `volcans…` → volcans, `inconnue…` → 404, école suspendue → 403. Revue : `docs/claude/revues/tache-1.1.md`.
- **Décisions** : voir le journal des décisions de `03` (garde-fous de `TenantModel`, sous-domaines réservés, rôle vérifié par les permissions de l'API, UUID v7 écrit sans dépendance, format des erreurs, `make demo` avancé en 1.1, ruff RUF012 désactivé).
- **Reste / suite** : fichiers de traduction du serveur quand un texte du serveur sera montré tel quel (2.4) ; en 1.2, nouveau modèle d'utilisateur → base de développement à recréer (annoncé dans `A-FAIRE.md` à ce moment-là). Prochaine tâche : 1.2.

### 2026-09-26 — Règles de travail avec GitHub

- **Fait** : l'utilisateur a fusionné #78 (décisions) puis #79 (tâche 0.2) ; `make install` relancé par Claude sur sa machine (les outils de la 0.2 manquaient). À sa demande : section « Travail avec GitHub » dans `CLAUDE.md`, skills `tache` (branche partie de `main`, une seule PR, contrôles verts, modèle de description) et `noter` (dans quelle PR va une note), `A-FAIRE.md` § 10 « Comment relire et fusionner une PR » (remplace la routine).
- **Décisions** : Claude est le développeur ; l'utilisateur, chef de projet et relecteur, valide, teste et fusionne. Une seule PR par tâche (corrections et documents compris), toujours `base: main`, jamais empilée ; PR séparée seulement pour une décision à valider avant de continuer ou une réparation urgente, en disant pourquoi. GitHub Actions vert avant de donner la PR. Chaque PR et chaque message de fin se terminent par « À valider », « À tester toi-même », « Après la fusion ».
- **Suite** : ces changements partent dans la PR de la tâche 1.1 (pas de PR séparée, à la demande de l'utilisateur).

### 2026-09-26 — Tâche 0.2 : qualité (ruff, ESLint, Prettier, Vitest, pre-commit, GitHub Actions)

- **Fait** : ruff configuré dans `backend/pyproject.toml` (100 colonnes, règles E, W, F, I, UP, B, DJ, SIM, RUF ; une ligne raccourcie) ; ESLint 10 (`typescript-eslint`, règles des hooks React, `eslint-config-prettier`), Prettier 3.9 (le code existant était déjà conforme), Vitest 5 avec les premiers tests (proxy de développement des deux applications) ; pre-commit avec des hooks locaux (ruff, ESLint, Prettier, refus d'un `.env` ou d'une clé privée) ; GitHub Actions (`.github/workflows/ci.yml`, 2 jobs : backend avec PostgreSQL 16 et vérification du schéma OpenAPI commité, frontend avec lint, types, Vitest, build). `Makefile` : `lint` (= `lint-back` + `lint-front`, sans rien modifier), `format`, `hooks` (lancé aussi par `install`), `test-front` = types + Vitest ; `make help` réparé (depuis l'`include .env`, `grep` préfixait chaque ligne par le nom du fichier). `CLAUDE.md` et `A-FAIRE.md` : commandes, routine (contrôles GitHub verts), dépannage, étape 8 (`make install` après la fusion).
- **Tests** : `make lint` OK ; `make test` : 7 pytest passés, types OK, 8 tests Vitest passés ; `make build` OK ; `make api` ne change pas le schéma commité. Fautes volontaires détectées : variable inutilisée et hook React conditionnel (ESLint), import inutilisé (ruff), `changeOrigin: true` (2 tests Vitest échouent) ; pre-commit refuse un `.env` et une clé privée ; hooks sur tout le dépôt : aucun fichier modifié. GitHub Actions sur la PR #79 : les 2 jobs verts au premier passage (7 pytest contre PostgreSQL 16, schéma OpenAPI à jour, 8 Vitest, build). Revue : `docs/claude/revues/tache-0.2.md`.
- **Décisions** : ESLint lit le code avec TypeScript 6.0, les applications gardent TypeScript 7 (`typescript-eslint` n'accepte pas encore la 7) ; mêmes commandes `make` en local, en pre-commit et en CI ; Prettier seulement sur le code du front (ni Markdown, ni lockfile, ni `openapi.yaml`), ruff seulement sur `backend/` ; actions GitHub à version fixée.
- **Dépendances ajoutées** (outils de développement seulement) : `ruff`, `pre-commit` ; `eslint`, `@eslint/js`, `typescript-eslint`, `typescript@~6.0`, `eslint-plugin-react-hooks`, `globals`, `eslint-config-prettier`, `prettier`, `vitest`. Raisons : `docs/claude/plans/tache-0.2.md`.
- **Suite** : l'utilisateur fusionne #78 puis #79, lance `make install` ; puis `/tache 1.1`.

### 2026-09-26 — Décisions de l'utilisateur : Q1 à Q11, l'ITIG école d'exemple

- **Fait** : l'utilisateur a fusionné #77 ; `make dev` marche chez lui. Ses réponses sont reportées dans `01`, `02`, `03` (§ 4, 6, 7 et journal des décisions), `04`, `05`, `07`, `CLAUDE.md` (principe, règles 1 et 9, glossaire), `A-FAIRE.md`, les skills `argent`, `backend`, `verifier`, `design`, `document-ecole`. Maquettes corrigées pour Q10 : fiche famille, fiche élève (Identité, Famille, Historique), accueil du portail (ajouter un enfant d'une autre école), vérification d'un reçu (reçu hors ligne signé). Logo noir et blanc de l'ITIG préparé (`ecole-pilote/documents/2026-09-26-logo-itig-noir-et-blanc.png`). Domaine `mwangaza.school` dans les documents ; les maquettes HTML affichent encore `mwangaza.cd`.
- **Principe** : l'ITIG est l'école d'exemple, pas la seule. Rien de propre à une école dans le code (nom, logo, couleur, options, frais, formats de reçu, rôles personnalisés : paramètres de l'école). Données manquantes inventées de façon réaliste ; les vraies données, chaque école les saisit. Isolation : chaque modèle, écran ou point d'API a un test qui prouve qu'une école ne peut ni lire ni modifier les données d'une autre (application, API, exports, rapports, recherche, portail).
- **Décisions** :
  - Q1 : pas de `PaymentSchedule` ; échéancier particulier = `StudentCharge` `source=custom`. Q2 : pas de modèle `Receipt` ; le reçu est une vue imprimable du paiement. Glossaire corrigé.
  - Q3 : 9 rôles système, dont `study_director` (directeur des études) et `discipline_master` (directeur de discipline / surveillant) ; plusieurs personnes par rôle. Q7 : chef d'atelier = rôle personnalisé de l'école.
  - Q4 : taux toujours USD → CDF ; FC → USD par division en `Decimal`, arrondi demi supérieur. Devise au choix pour chaque barème (`FeeRule.currency`). Taux fixe pour l'année, saisi par le comptable, corrigeable avec historique ; les paiements gardent leur taux.
  - Q5 : montant en lettres proposé par Claude (« Cent cinquante dollars américains et vingt-cinq centimes »), ajusté quand le reçu de l'ITIG arrivera.
  - Reçu : format au choix de l'école (thermique 58 / 80 mm, ou A6, A5, petit format sur A4 avec traits de découpe), 1 ou 2 exemplaires ; reste à payer, taux utilisé, caissier, zone signature / cachet ; QR code dès la V1.0, page publique minimale, signé par l'appareil pour rester vérifiable hors ligne.
  - Q6 : caisse d'abord ; P1 2026 sur papier ; bulletins avec Mwangaza à partir de la P2 / 1er semestre ; ordre V1.1 / V1.2 inchangé. Q11 : deux modes d'impression du bulletin ; en attendant, formulaires officiels IGE/P.S et données fictives.
  - Q8 : couleur choisie par l'école (défaut `#0E5C6B`, contraste vérifié) ; `#003C6C` pour l'ITIG de démonstration. Q9 : Mwangaza, `mwangaza.school`.
  - Q10 : chaque école a sa propre copie de l'élève et de sa famille (`Student`, `Family`, `Guardian` liés à l'école).
  - Designs des documents imprimables proposés par Claude, validés par la fusion de la PR. Données de démonstration : `itig` ~800 élèves (familles, fratries, paiements sur plusieurs mois), `volcans` plus petite.
- **Plus bloquant** : documents de l'ITIG (2.3, 2.5, 3.2, 4.8), modèle de l'imprimante thermique, logo noir et blanc, date de la P1. Cases « avant de coder » A.1 et A.4 sans objet (issues #1 et #4 fermées par la PR).
- **Propositions de Claude à valider** (fusion de la PR = accord) : permissions des deux nouveaux rôles et nouvelle permission `classes.manage` (`04` § 8) ; portail multi-écoles : un compte parent relié à une famille par école avec le code famille de chaque école, jamais par téléphone (`03` § 4, `04` § 3) ; QR signé ECDSA P-256 par l'appareil (`03` § 7) ; couleur refusée si le texte n'y est pas lisible (`04` § 1).
- **Reste à l'utilisateur** (non bloquant pour 0.2) : acheter `mwangaza.school` et ouvrir VPS et Cloudflare avant 4.6, stockage objet avant 4.7 ; demander à l'ITIG la date de la P1 2026, qui est le promoteur, le reçu actuel, des bulletins vierges et remplis, le code de l'école (I18) ; transmettre les documents dès qu'il les a.
- **Suite** : `/tache 0.2`.

### 2026-09-26 — `make dev` réparé : tout Mwangaza tourne dans Docker

- **Fait** : l'utilisateur a fusionné #76, s'est reconnecté (`docker run hello-world` OK). Premier `make dev` complet : Django, Celery, PostgreSQL, Redis démarrent, mais le conteneur du front s'arrêtait (`pnpm: not found`, code 127 : le script `pnpm dev` rappelle `pnpm`, absent du `PATH` de `node:22-slim`). De plus, `pnpm install` dans le conteneur réécrivait le `node_modules` de la machine (partagé par le volume) avec un store `/app/node_modules/.pnpm-store` inexistant hors de Docker, et pnpm 12 (vérification des dépendances avant `run`) réinstallait tout à chaque lancement (≈ 40 s avec la connexion de Goma). Correctif (branche `fix/docker-front`) : `corepack enable` dans le conteneur (pnpm dans le `PATH`, `COREPACK_HOME` dans `node_modules` pour ne télécharger pnpm qu'une fois) ; plus d'installation dans le conteneur ; `pnpm_config_verify_deps_before_run=false` ; `make dev` lance `pnpm install --frozen-lockfile` sur la machine avant Docker. `A-FAIRE.md` : 3 bis et 5 bis cochées, 5 ter (fusionner ce correctif), dépannage `ERR_PNPM_UNEXPECTED_STORE`. `CLAUDE.md` : ligne `make dev`.
- **Tests** : `make dev` : prêt en 25 s, `/api/health/` → `ok` (direct et via le proxy de la Gestion), Gestion et Portail → 200, `node_modules` de la machine inchangé ; `make test` : 7 passés, types OK.
- **Décision** : le conteneur du front utilise le `node_modules` installé sur la machine (même Linux x64) au lieu d'installer lui-même.
- **Constat** : pnpm 12 ne lit plus les variables `npm_config_*`, seulement `pnpm_config_*`.
- **Suite** : l'utilisateur fusionne la PR, refait `A-FAIRE.md` § 5 lui-même, tranche Q1–Q11 ; puis `/tache 0.2`.

### 2026-09-26 — Docker installé, `.env` réparé, base de développement en marche

- **Fait** : l'utilisateur a fusionné #75 et installé Docker (29.8, Compose 5.5). Son `.env` (copie de `.env.example`) avait `DJANGO_SECRET_KEY=` vide : l'ancienne consigne demandait de coller à la main la clé affichée par `python3 …`. Une valeur vide exportée par le `Makefile` passait avant la valeur par défaut de `dev.py`, et Django refusait la clé vide (`The SECRET_KEY setting must not be empty`). Correctif (branche `fix/env-valeurs-vides`) : `env()`, `env_bool()`, `env_list()` traitent une variable vide comme absente ; `.env.example` explique la clé ; `A-FAIRE.md` mis à jour (étapes 1 à 4 cochées, 3 bis « se reconnecter », 5 bis « fusionner le correctif », tableau des valeurs du `.env`, ligne de dépannage). Clé écrite dans le `.env` de l'utilisateur par script, jamais affichée. L'utilisateur est dans le groupe `docker` mais sa session ne le voit pas encore (reconnexion nécessaire) ; Claude a lancé les commandes via `sg docker`.
- **Tests** : `make services` (PostgreSQL 16 sur 5433, Redis) ; `make test` : 7 passés (3 + 4 nouveaux dans `tests/test_settings.py`), types du front OK ; `make migrate` ; `make dev-local` : `/api/health/` → `ok` (direct et via le proxy de la Gestion), Gestion et Portail → 200. Production : refuse toujours de démarrer sans `DJANGO_SECRET_KEY`.
- **Décision** : une variable d'environnement vide vaut « absente » (valeur par défaut).
- **Suite** : l'utilisateur se reconnecte, fusionne le correctif, refait `A-FAIRE.md` § 5 lui-même, tranche Q1–Q11 ; puis `/tache 0.2`.

### 2026-09-26 — `A-FAIRE.md`, dossier renommé, PR de rattrapage

- **Fait** : `A-FAIRE.md` à la racine, à la demande de l'utilisateur : ce que lui seul peut faire avant que Claude continue (fusionner #75, rouvrir le dossier, installer Docker, créer `.env`, vérifier, trancher Q1–Q11), comment le faire (commandes pas à pas pour Ubuntu 24.04), quoi demander à l'ITIG et quand (avec un message prêt à envoyer), comptes à créer avant 4.6, routine de chaque tâche, toutes les commandes du projet (actuelles et prévues), dépannage. Relié depuis `CLAUDE.md`, `README.md`, `07`, et les skills `tache` et `noter` (tenu à jour à chaque nouvelle commande ou action). Dossier local renommé de `~/Projets/saas` en `~/Projets/mwangaza` (nom du dépôt GitHub) ; mémoire de Claude Code copiée vers le nouveau chemin ; `backend/.venv` recréé.
- **Constat** : la PR #73 a été fermée sans fusion et la PR #74 fusionnée dans `docs/inventaire-manques` au lieu de `main` : `07-a-fournir.md` et les 61 maquettes n'étaient pas sur `main`. La PR #75 (`docs/a-faire`, partie de `docs/inventaire-manques`) les ramène. `make test-back` échoue sur la machine (2 erreurs) faute de base PostgreSQL accessible : bloquant pour 0.2.
- **Décisions** : `A-FAIRE.md` = liste d'actions de l'utilisateur et référence commentée des commandes ; `07` reste l'inventaire de ce qui manque. Règle : vérifier `base: main` avant de fusionner une PR ; plus de PR empilées.
- **Suite** : l'utilisateur fait les étapes 1 à 6 de `A-FAIRE.md`, puis `/tache 0.2`.

### 2026-09-26 — Maquettes manquantes dessinées ; bulletins officiels de la RDC

- **Fait** : T3 tranchée (Claude dessine). 32 maquettes dessinées dans le système de design, à partir des maquettes existantes et des documents : les 20 manquantes de la V1.0 (M1–M20 = 25 écrans Gestion et 4 Portail), cours et maxima (6.1), bulletin 7e–8e, et le bulletin des humanités techniques qui remplace le « gabarit provisoire ». Total : 61 maquettes, 67 captures refaites (50 bureau, 17 mobile). Menu de la Gestion : 5 entrées ajoutées (Crédits d'élèves, Demandes des parents, Paramètres de l'école, Comptes du personnel, Journal d'audit), identique sur toutes les maquettes ; liens entre écrans complétés. Outils sans dépendance dans `maquettes/outils/` (menu, galerie, captures). Recherche web sur les bulletins : formulaires officiels IGE/P.S/100 (Électricité), /094 (Mécanique générale), /005 (1re–2e secondaire = 7e–8e), barème officiel des maxima de l'option Électronique, heures de l'option Électricité, régime pédagogique du cycle terminal de l'éducation de base — `docs/claude/recherches/2026-09-26-bulletins-rdc.md`.
- **Décisions** : fusionner la PR des maquettes = les valider ; une remarque sur un écran se fait en commentaire de PR. Maquettes dessinées : état « à valider » dans `maquettes/README.md` et `index.html`. Bulletin : branches groupées par maximum, examen = 2 × période, pas d'examen pour les cours pratiques (règles lues sur les formulaires).
- **Nouvelles questions** : Q10 (identité et famille partagées entre écoles), Q11 (numérotation et bulletin pré-imprimé). Nouvelle information à demander : I18 (code de l'école, N° ID et N° permanent).
- **Suite** : l'utilisateur fusionne #72, #73 puis #74 ; ensuite tâche 0.2.

### 2026-09-26 — Inventaire de ce qui manque ; nom du projet

- **Fait** : `docs/07-a-fournir.md` — 20 maquettes V1.0 manquantes (M1–M20) + liste V1.1 / V1.2, 17 informations à obtenir de l'ITIG (I1–I17, avec la tâche et la semaine où elles deviennent nécessaires et ce qu'on utilise en attendant), 6 décisions ou comptes (T1–T6), plan des données de démonstration (`make demo`, écoles `itig` et `volcans`). Vérification des noms : `mwangaza.cd`, `.com`, `.app` pris ; `mwangaza.africa` et `mwangaza.school` semblent libres ; « Shule Yetu » déjà utilisé par une plateforme scolaire.
- **Décisions** : on continue avec des données fictives ; une maquette non fournie est dessinée par Claude dans le système de design et validée avant de coder l'écran.
- **Nouvelle question** : Q9 (nom et domaine).
- **Suite** : réponses de l'utilisateur (voir `07-a-fournir.md` — « à faire maintenant »), puis 0.2.

### 2026-09-25 — Tâche 0.1 : monorepo, Docker Compose de développement, commandes

- **Fait** : `backend/` (Django 5.2.17 LTS, DRF, drf-spectacular, Celery, psycopg ; réglages `dev` / `test` / `prod` ; `/api/health/` ; schéma et doc de l'API en dev) ; `frontend/` (workspace pnpm : `apps/gestion` sur `/app/` port 5173, `apps/portail` port 5174, proxy `/api` vers Django en gardant le sous-domaine ; `packages/api|ui|i18n|money` vides) ; `infra/docker-compose.dev.yml` (PostgreSQL 16 sur 5433, Redis 7, Django, Celery, Vite) ; `Makefile` (16 commandes) ; `.env.example`, `.editorconfig`, `firmware/README.md` ; section « Commandes » de `CLAUDE.md`. Outils installés : `uv` 0.12 (`~/.local/bin`), `pnpm` 12.6 (corepack).
- **Tests** : `make test-back` 3 passés (santé, panne de base → 503, schéma OpenAPI valide) ; types et build des deux applications OK ; parcours vérifié à la main sur `itig.localhost:5173/app/` et `localhost:5174` via le proxy ; `check --deploy` : seul W021 (préchargement HSTS, reporté à 4.6). Revue : `docs/claude/revues/tache-0.1.md`.
- **Décisions** : uv ; `make` pour toutes les commandes ; PostgreSQL de Docker exposé sur 5433 ; sous-domaines `{code}.localhost` en dev ; API fermée par défaut (`IsAuthenticated`) ; schéma et doc de l'API seulement en `DEBUG` ; schéma OpenAPI commité dans `packages/api`.
- **Reste** : lancer `make dev` quand Docker sera installé ; ta base locale n'a pas de rôle PostgreSQL pour ton utilisateur → utiliser `make services` (Docker) ou créer le rôle (`sudo -u postgres createuser --createdb --pwprompt mwangaza`) ; en 1.2 (modèle `User` personnalisé), la base de dev sera recréée.
- **Suite** : 0.2 — qualité (ruff, ESLint, Prettier, Vitest, pre-commit, GitHub Actions).

### 2026-09-25 — GitHub, découpage par versions, dossier ITIG, espace de travail de Claude

- **Fait** : premier commit et dépôt GitHub privé `GUELORD-MWENDERWA/mwangaza` ; jalons V1.0, V1.1, V1.2, V2 et 71 issues (une par tâche, #1 à #4 = « avant de coder », #5 = tâche 0.1) ; plan de travail complété jusqu'à la fin : 4 tâches ajoutées pour couvrir tout le cahier des charges (5.8, 5.9, 6.10, 6.11) et section V2 (7.1 à 7.15, ordre à valider) ; dossier ITIG réorganisé (`depot/`, `documents/`, `prive/`, `fiche-itig.md`) ; recherche web sur l'ITIG (logo, adresse, contacts, 4 options, niveaux 7e–8e EB + 1re–4e, organigramme, date de la P1 2025, dégâts de janvier 2025) ; espace de travail `docs/claude/` (plans, recherches, revues) ; skills `tache`, `etat`, `noter`, `document-ecole` reliées à GitHub et à ces dossiers ; plan de la tâche 0.1 écrit.
- **Décisions** : un jalon GitHub par version, une issue par tâche, PR avec `Closes #n` ; `depot/` et `prive/` hors Git ; noms de personnes seulement dans `prive/`.
- **Nouvelles questions** : Q6 (date des bulletins P1), Q7 (rôles réels de l'ITIG), Q8 (couleur de l'école).
- **Suite** : validation du plan 0.1 (Docker, gestionnaire Python, autorisation de commit), puis tâche 0.1.

### 2026-09-25 — Organisation du dossier avant de coder

- **Fait** : dossier réorganisé selon `03-architecture-technique.md` § 3 — `docs/` et `maquettes/` à la racine ; doublons supprimés (anciennes copies des documents, 4 captures identiques, ancien `CLAUDE.md`) ; `CLAUDE.md` fusionné (lien vers les maquettes, règles de suivi, liste des skills) ; `README.md` du projet ; `.gitignore` ; `docs/ecole-pilote/` ; ce fichier de suivi ; 10 skills Claude Code dans `.claude/skills/` ; dépôt Git initialisé sur `main`.
- **Tests** : sans objet (aucun code).
- **Décisions** : suivi dans `docs/06-suivi.md` ; données personnelles réelles de l'ITIG dans `docs/ecole-pilote/prive/`, hors Git.
- **Suite** : premier commit, puis plan de la tâche 0.1.

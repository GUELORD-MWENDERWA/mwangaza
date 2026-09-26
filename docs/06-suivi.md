# Suivi du projet

Ce fichier dit **où en est le projet**. Il est mis à jour à chaque étape (début et fin de tâche, décision, document reçu, blocage). Les cases à cocher restent dans `05-plan-de-travail.md` ; ici on garde l'état, l'avancement et le journal.

## État actuel

| | |
|---|---|
| Phase | V1.0 — semaine 1 (Socle) |
| Lot | V1.0 — semaine 1 (Socle) |
| Tâche en cours | aucune — 0.1 terminée ; correctif de `make dev` en PR ; en attente des actions de l'utilisateur listées dans `A-FAIRE.md` (fusionner la PR, vérifier lui-même, décisions) |
| Prochaine tâche | 0.2 — qualité : ruff, pytest, ESLint, Prettier, Vitest, pre-commit, GitHub Actions |
| Issue GitHub | #5 (0.1, fermée à la fusion de la PR) · prochaine : #6 (0.2) |
| Branche | `fix/docker-front` → PR #77 vers `main` (#75 et #76 fusionnées) ; dossier local : `~/Projets/mwangaza` |
| Dernière mise à jour | 2026-09-26 |

## Avancement

| Bloc | Fait | Total |
|---|:-:|:-:|
| Avant de coder (toi) | 0 | 4 |
| Semaine 1 — Socle | 1 | 9 |
| Semaine 2 — Élèves et frais | 0 | 7 |
| Semaine 3 — Caisse et hors-ligne | 0 | 8 |
| Semaine 4 — Rapports, portail, production | 0 | 8 |
| **V1.0** | **1** | **32** |
| V1.1 — semaines 5 à 8 | 0 | 9 |
| V1.2 — semaines 9 à 14 | 0 | 11 |
| V2 | 0 | 15 |

Sur GitHub : onglet *Milestones* — V1.0 (36 issues, dont les 4 « avant de coder »), V1.1 (9), V1.2 (11), V2 (15).

## Bloquants et en attente

Liste complète et détaillée (maquettes M1–M20, informations I1–I17, décisions T1–T6) : `07-a-fournir.md`. Ce que l'utilisateur doit faire et comment : `../A-FAIRE.md`. Ici, seulement ce qui bloque bientôt.

| Sujet | Attendu de | Bloque |
|---|---|---|
| Documents ITIG (cahier des charges § 11) : grille des frais, liste des élèves Excel, modèle de reçu | ITIG | 2.3, 2.5, 3.2, 4.8 |
| Modèle de l'imprimante thermique | ITIG | 3.2 |
| Date de remise des bulletins de la 1re période 2026-2027 (indice : 8 novembre en 2025) | ITIG | ordre V1.1 / V1.2 — voir Q6 |
| Nom définitif et domaine | toi | 4.6 |
| Comptes VPS, Cloudflare, stockage objet (GitHub : fait) | toi | 4.6, 4.7 |
| Fusion de la PR #77 (correctif de `make dev`) | toi | 0.2 (partir d'un `main` à jour) |
| Logo haute qualité + version noir et blanc pour le reçu thermique | ITIG | 3.2 |

## Questions ouvertes

À trancher au plus tard pendant la tâche indiquée. Une fois tranchée : déplacer dans le journal.

| # | Question | Tâche | Proposition |
|---|---|---|---|
| Q1 | Le glossaire cite `PaymentSchedule` (échéancier) mais `04-modele-de-donnees.md` n'a pas cette entité : l'échéancier est porté par `FeeRule.schedule_kind`, `InstallmentTemplate` et `StudentCharge`. | 2.5 | Suivre `04` ; l'échéancier particulier = `StudentCharge` avec `source=custom`. |
| Q2 | Le glossaire cite `Receipt`, mais `04` ne définit pas de modèle `Receipt` (le numéro est sur `Payment` et `PaymentCancellation`). | 3.2 | Pas de modèle : le reçu est une vue imprimable du paiement. |
| Q3 | Codes des rôles système : seul `head` (directeur) et `promoter` sont fixés dans le glossaire. | 1.2 | `head`, `accountant`, `cashier`, `secretary`, `promoter`, `teacher`, `parent`. |
| Q4 | Paiement en FC d'un frais en USD : `allocation = received × rate_used` avec un taux à 6 décimales donne 1/2 850 ≈ 0,000351, soit jusqu'à ~10 centimes d'erreur par million de FC. | 2.5, 3.1 | Toujours enregistrer le taux dans le sens USD → CDF (tel que saisi) et diviser en `Decimal` pour FC → USD, arrondi demi supérieur au centime. |
| Q5 | Montant en lettres sur le reçu : formulation des centimes et de la devise. | 3.2 | Reprendre la formulation du reçu actuel de l'ITIG. |
| Q6 | En 2025, l'ITIG a proclamé les résultats de la P1 le 8 novembre. Si 2026 est pareil, la P1 tombe en semaine 7 du projet, avant la V1.2 (semaines 9 à 14). | ordre V1.1 / V1.2 | Garder la caisse (V1.0) en priorité ; P1 2026 encore sur papier ; viser les bulletins de la P2 / 1er semestre avec Mwangaza ; confirmer les dates avec l'ITIG. |
| Q7 | L'organigramme ITIG a 2 directeurs des études, 1 directeur de discipline et 2 chefs d'atelier ; « chef d'atelier » n'est pas dans la liste des rôles du cahier des charges, et on ne sait pas qui joue le rôle de promoteur (communauté salésienne ?). | 1.2 | Rôles système V1.0 inchangés ; chef d'atelier = rôle personnalisé créé par l'école (B2) en attendant le module ateliers (V2) ; demander à l'ITIG qui est « promoteur ». |
| Q8 | Couleur de l'ITIG pour la personnalisation (`School.primary_color`). | 1.5 | `#003C6C` (bleu marine du logo). |
| Q9 | Nom et domaine : `mwangaza.cd` est déjà enregistré (sans site), `mwangaza.com` est en vente chez un revendeur, `mwangaza.app` est pris ; « Shule Yetu » est déjà une plateforme de gestion scolaire. | maintenant (domaine avant 4.6) | Garder **Mwangaza** (identité visuelle construite autour : lampe = lumière ; aucun logiciel scolaire de ce nom trouvé) et prendre **`mwangaza.africa`** (semble libre, à confirmer chez le registrar). Autres possibilités : `mwangaza.school` ; `mwanga.cd` (même sens, plus court) ; tenter de racheter `mwangaza.cd`. |
| Q10 | L'identité d'un élève (`Student`) et sa famille (`Family`, `Guardian`) sont partagées entre écoles (modèles globaux). Qui peut les corriger quand l'élève a été inscrit dans deux écoles ? | 2.1, 2.2 | L'école de l'inscription active corrige ; la correction se voit partout, avec auteur et école dans l'historique ; une école où l'élève n'est plus inscrit ne peut que lire. |
| Q11 | Bulletins : les formulaires officiels trouvés (IGE/P.S/094, /100, /005) numérotent les classes à l'ancienne (« 3e année » = 1re des humanités) et sont peut-être pré-imprimés (achetés). | 6.1, 6.3 | Demander à l'ITIG un bulletin vierge et un rempli par niveau (I15, I18) ; prévoir deux modes d'impression : bulletin complet, ou notes seules sur le formulaire pré-imprimé. |

## Journal

Entrée la plus récente en haut. Format : date — titre, puis fait / tests / décisions / suite.

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

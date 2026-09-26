# CLAUDE.md — Mwangaza (nom de travail)

Plateforme de gestion scolaire multi-écoles pour la RDC, lancement à Goma.
École pilote : **ITIG Don Bosco Goma** (institut technique, ~1 200 élèves, ateliers mécanique / auto / électricité / électronique).

**L'ITIG est l'école d'exemple, pas la seule école.** Elle donne un cas concret (niveaux, options, frais, reçus, bulletins, rôles), mais chaque école, l'ITIG comprise, saisit elle-même ses vraies données dans l'application. On n'attend pas les documents de l'ITIG : ce qui manque, Claude l'invente de façon réaliste pour les données de démonstration.

## Au début de chaque session

Lire `docs/06-suivi.md` (état actuel, tâche en cours, bloquants) avant toute autre action.

## À lire avant toute tâche

1. `docs/01-cahier-des-charges.md` — vision complète du produit (toutes les fonctions, présentes et futures)
2. `docs/02-perimetre-v1.md` — **ce qu'on construit maintenant** et ce qu'on ne construit PAS encore
3. `docs/03-architecture-technique.md` — stack, multi-écoles, hors-ligne, sécurité, hébergement
4. `docs/04-modele-de-donnees.md` — entités et règles métier
5. `docs/05-plan-de-travail.md` — tâches ordonnées, cocher au fur et à mesure
6. `docs/06-suivi.md` — état actuel du projet et journal de chaque étape
7. `docs/07-a-fournir.md` — maquettes, informations et décisions encore manquantes (et ce qu'on utilise en attendant)
8. `maquettes/README.md` — système de design et inventaire des écrans ; captures dans `maquettes/captures/`, structure et libellés dans `maquettes/gestion/*.html` et `maquettes/portail/*.html`

École pilote : `docs/ecole-pilote/fiche-itig.md` (ce qu'on sait), `depot/` (l'utilisateur y dépose ses fichiers, hors Git), `documents/` (rangés, sans données personnelles), `prive/` (données personnelles, hors Git).

Espace de travail de Claude : `docs/claude/` — `plans/` (plan de chaque tâche avant de coder), `recherches/` (notes avec sources), `revues/` (résultat de `/verifier`).

GitHub (dépôt privé `GUELORD-MWENDERWA/mwangaza`) : un jalon par version (V1.0, V1.1, V1.2, V2), une issue par tâche titrée « <numéro> — … » ; la PR de la tâche contient `Closes #<n>`.

Si une demande sort du périmètre de `02-perimetre-v1.md`, le signaler avant de coder.

Pour tout écran : regarder la capture PNG **et** le HTML de la maquette, reproduire en React + Tailwind + shadcn/ui avec les jetons de `maquettes/README.md`. Les encadrés `.note` des maquettes sont des règles métier à appliquer, pas du contenu à afficher. Les documents `docs/` priment sur les maquettes en cas de contradiction.

## Stack (décidée — ne pas changer sans accord)

- Backend : Python 3.12+, Django 5.2 LTS, Django REST Framework, drf-spectacular (OpenAPI), PostgreSQL 16+, Celery + Redis, WeasyPrint (PDF)
- Frontend : TypeScript, React, Vite, vite-plugin-pwa (Workbox), Dexie.js (IndexedDB), TanStack Query, React Router, Tailwind CSS + shadcn/ui, react-hook-form + zod, i18next
- Deux applications front : `frontend/apps/gestion` (personnel de l'école, **hors-ligne d'abord**) et `frontend/apps/portail` (parents et élèves, en ligne, léger)
- Infra : Docker Compose, Caddy, un VPS, Cloudflare (DNS + wildcard), sauvegardes PostgreSQL vers stockage objet
- Tests : pytest + pytest-django + factory_boy ; Vitest ; Playwright (dont scénarios hors-ligne)
- Qualité : ruff (lint + format), ESLint + Prettier, pre-commit, GitHub Actions

## Règles non négociables

1. **Isolation des écoles** : tout modèle métier hérite de `TenantModel` (champ `school`), y compris `Student`, `Family` et `Guardian` (chaque école a sa propre copie). Toute requête passe par le manager scopé. Chaque nouveau modèle, écran ou point d'API a un test qui prouve qu'une école ne peut **ni lire ni modifier** les données d'une autre : application, API, exports, rapports, recherche et portail parent compris.
2. **Argent** : montants en **entiers** (plus petite unité : centimes USD, francs FC) + code devise. Jamais de `float`. Taux de change enregistré sur chaque paiement.
3. **Paiements immuables** : on ne modifie ni ne supprime jamais un paiement. Une annulation est un nouvel enregistrement lié, avec motif, permission dédiée et trace d'audit.
4. **Identifiants** : UUID v7 générés côté client pour toute donnée créable hors-ligne. Toute écriture de synchronisation est idempotente.
5. **Audit** : toute création / modification / annulation sur finances, notes, paie et rôles écrit dans `AuditLog`.
6. **Permissions** : vérifier la permission côté serveur sur chaque endpoint ; le front ne fait que masquer.
7. **i18n** : aucun texte d'interface en dur ; français par défaut, anglais disponible.
8. **Pas de nouvelle dépendance** sans l'expliquer et demander.
9. **Rien en dur pour une école** : nom, logo, couleur, options, frais, formats et exemplaires des reçus, rôles personnalisés… viennent des paramètres de l'école, jamais du code.

## Conventions de code

- Code, noms de modèles, variables et API en **anglais** ; interface en français / anglais via i18n.
- Glossaire métier (terme RDC → nom dans le code) :

| Terme école | Code |
|---|---|
| École / établissement | `School` |
| Promoteur | `Promoter` / rôle `promoter` |
| Préfet des études / directeur | rôle `head` |
| Directeur des études | rôle `study_director` |
| Directeur de discipline / surveillant | rôle `discipline_master` |
| Comptable, caissier, secrétaire, enseignant, parent | rôles `accountant`, `cashier`, `secretary`, `teacher`, `parent` |
| Titulaire | `homeroom_teacher` |
| Minerval / frais scolaires | `FeeType` (catégorie `tuition`) |
| Barème (montant et devise d'un frais) | `FeeRule` |
| Tranche | `InstallmentTemplate` (modèle) ; ce que doit l'élève : `StudentCharge` |
| Échéancier | `FeeRule.schedule_kind` + `InstallmentTemplate` ; échéancier particulier d'un élève : `StudentCharge` avec `source=custom` (pas de modèle `PaymentSchedule`) |
| Taux de change (fixe pour l'année, corrigeable) | `ExchangeRate` |
| Caisse | `CashRegister` |
| Clôture de caisse | `CashClosing` |
| Reçu | pas de modèle : vue imprimable d'un `Payment` (`receipt_number`) |
| Option (humanités) | `Track` |
| Section de classe (6e A) | `ClassGroup` |
| Année scolaire | `AcademicYear` |
| Période (P1, P2…) | `Term` |
| Inscription annuelle | `Enrollment` |
| Famille / tuteur | `Family` / `Guardian` |
| Prime / motivation enseignants | `TeacherBonus` |

- Backend : une app Django par domaine (`core`, `accounts`, `schools`, `students`, `finance`, `payroll`, `portal`, `notifications`, `sync`, `audit`). Logique métier dans `services.py`, pas dans les vues.
- Front : dossiers par fonctionnalité (`features/finance/...`). Client API typé généré depuis l'OpenAPI (`packages/api`).
- Messages de commit en français, style conventionnel : `feat(finance): encaissement partiel`.

## Commandes

Outils : `uv` (Python, dans `~/.local/bin`), `pnpm` (via corepack), `make`, Docker. `make` seul affiche la liste. Version commentée pour l'utilisateur, avec les commandes à venir et le dépannage : `A-FAIRE.md` § 11–12 (à tenir à jour avec ce tableau).

| Commande | Effet |
|---|---|
| `make install` | `uv sync` (backend) + `pnpm install` (frontend) |
| `make dev` | `pnpm install` sur la machine, puis tout dans Docker : PostgreSQL (hôte : 5433), Redis, Django (:8000), Celery, Gestion (:5173), Portail (:5174) ; le conteneur du front réutilise le `node_modules` de la machine |
| `make services` puis `make dev-local` | seulement PostgreSQL et Redis dans Docker ; Django et Vite sur la machine (valeurs dans `.env`, copié de `.env.example`) |
| `make stop` | arrêter les conteneurs |
| `make migrate` · `make makemigrations app=<app> name=<nom>` | migrations |
| `make test` · `make test-back` · `make test-front` | pytest ; vérification des types (Vitest arrive en 0.2) |
| `make lint` | ruff, ESLint, Prettier (0.2) |
| `make api` | schéma OpenAPI → `frontend/packages/api/openapi.yaml` (à relancer après tout changement d'API) |
| `make build` | build des deux PWA |
| `make superuser` · `make shell` | compte super-admin ; console Django |
| `python3 maquettes/outils/maquettes.py menu` · `… index` · `node maquettes/outils/captures.mjs` | maquettes : menu latéral commun, galerie `index.html`, captures PNG (sans dépendance, Chrome de la machine) |

Adresses en dev : Gestion `http://itig.localhost:5173/app/` (le sous-domaine = code de l'école), Portail `http://localhost:5174/`, API `/api/…` via le proxy Vite, doc de l'API `/api/docs/` (seulement en `DEBUG`). Réglages Django : `config.settings.dev` (défaut de `manage.py`), `test` (pytest), `prod` (wsgi/asgi, refuse de démarrer sans `DJANGO_SECRET_KEY`).

## Façon de travailler

- Une tâche du plan = une branche = une PR, tests inclus.
- Avant de coder une fonction, relire la section correspondante du cahier des charges et du modèle de données.
- Après chaque tâche : cocher la case dans `docs/05-plan-de-travail.md` et noter toute décision nouvelle dans la section « Journal des décisions » de `docs/03-architecture-technique.md`.
- En cas de doute sur une règle scolaire RDC (bulletins, délibération, frais), demander plutôt que supposer.

## Données de démonstration

On travaille avec des données **fictives et réalistes** : `make demo` recrée l'école `itig` (démo : ~800 élèves avec familles, fratries et paiements sur plusieurs mois), une seconde école fictive `volcans`, plus petite, pour prouver l'isolation, et un compte par rôle (détail : `docs/07-a-fournir.md` § 4). Les vraies données, c'est l'école qui les saisit. Chaque tâche qui ajoute un modèle enrichit cette commande. Jamais de vraie donnée personnelle dans les données de démonstration ni dans les tests.

## Suivi du projet (obligatoire)

Chaque étape doit être notée pour savoir à tout moment où en est le projet.

- **Début d'une tâche** : dans `docs/06-suivi.md`, mettre à jour « État actuel » (tâche en cours, branche).
- **Fin d'une tâche** : cocher dans `docs/05-plan-de-travail.md`, mettre à jour « État actuel » et « Avancement », ajouter une entrée datée au « Journal » (fait, tests, décisions, reste à faire).
- **Tout autre événement** (document reçu de l'ITIG, décision, blocage levé, question tranchée) : entrée datée au « Journal ».
- **Décision technique** : aussi dans le « Journal des décisions » de `docs/03-architecture-technique.md`.
- **Action qui attend l'utilisateur** (installer, fusionner une PR, demander à l'ITIG, acheter, créer un compte) ou **nouvelle commande** : mettre à jour `A-FAIRE.md` (ce qu'il doit faire, comment, avec quelles commandes ; cocher ce qui est fait). Le signaler dans la réponse.
- Terminer chaque réponse de travail par une ligne d'état : `📍 Tâche X.Y — étape — prochaine action`.

## Skills du projet (`.claude/skills/`)

| Commande | Quand |
|---|---|
| `/etat` | Faire le point : où on en est, prochaine tâche, bloquants |
| `/tache 1.1` | Réaliser une tâche du plan de bout en bout (branche, tests, suivi) |
| `/noter …` | Noter une étape, une décision, un document reçu, un blocage |
| `/ecran caisse-encaissement` | Construire un écran à partir de sa maquette |
| `/design` | Appliquer le système de design (jetons, composants, formats) |
| `/backend` | Créer un modèle, un service ou un endpoint Django conforme |
| `/argent` | Tout calcul, stockage ou affichage de montant |
| `/hors-ligne` | Synchronisation, Dexie, file d'opérations, reçus hors-ligne |
| `/verifier` | Contrôle des règles non négociables avant commit / PR |
| `/document-ecole` | Intégrer un document réel de l'ITIG |

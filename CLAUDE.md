# CLAUDE.md — Mwangaza (nom de travail)

Plateforme de gestion scolaire multi-écoles pour la RDC, lancement à Goma.
École pilote : **ITIG Don Bosco Goma** (institut technique, ~1 200 élèves, ateliers mécanique / auto / électricité / électronique).

## Au début de chaque session

Lire `docs/06-suivi.md` (état actuel, tâche en cours, bloquants) avant toute autre action.

## À lire avant toute tâche

1. `docs/01-cahier-des-charges.md` — vision complète du produit (toutes les fonctions, présentes et futures)
2. `docs/02-perimetre-v1.md` — **ce qu'on construit maintenant** et ce qu'on ne construit PAS encore
3. `docs/03-architecture-technique.md` — stack, multi-écoles, hors-ligne, sécurité, hébergement
4. `docs/04-modele-de-donnees.md` — entités et règles métier
5. `docs/05-plan-de-travail.md` — tâches ordonnées, cocher au fur et à mesure
6. `docs/06-suivi.md` — état actuel du projet et journal de chaque étape
7. `maquettes/README.md` — système de design et inventaire des écrans ; captures dans `maquettes/captures/`, structure et libellés dans `maquettes/gestion/*.html` et `maquettes/portail/*.html`

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

1. **Isolation des écoles** : tout modèle métier hérite de `TenantModel` (champ `school`). Toute requête passe par le manager scopé. Chaque nouvelle vue a un test qui prouve qu'une école ne voit pas les données d'une autre.
2. **Argent** : montants en **entiers** (plus petite unité : centimes USD, francs FC) + code devise. Jamais de `float`. Taux de change enregistré sur chaque paiement.
3. **Paiements immuables** : on ne modifie ni ne supprime jamais un paiement. Une annulation est un nouvel enregistrement lié, avec motif, permission dédiée et trace d'audit.
4. **Identifiants** : UUID v7 générés côté client pour toute donnée créable hors-ligne. Toute écriture de synchronisation est idempotente.
5. **Audit** : toute création / modification / annulation sur finances, notes, paie et rôles écrit dans `AuditLog`.
6. **Permissions** : vérifier la permission côté serveur sur chaque endpoint ; le front ne fait que masquer.
7. **i18n** : aucun texte d'interface en dur ; français par défaut, anglais disponible.
8. **Pas de nouvelle dépendance** sans l'expliquer et demander.

## Conventions de code

- Code, noms de modèles, variables et API en **anglais** ; interface en français / anglais via i18n.
- Glossaire métier (terme RDC → nom dans le code) :

| Terme école | Code |
|---|---|
| École / établissement | `School` |
| Promoteur | `Promoter` / rôle `promoter` |
| Préfet des études / directeur | rôle `head` |
| Directeur des études | rôle `academic_director` |
| Titulaire | `homeroom_teacher` |
| Minerval / frais scolaires | `FeeType` (catégorie `tuition`) |
| Tranche | `Installment` |
| Échéancier | `PaymentSchedule` |
| Caisse | `CashRegister` |
| Clôture de caisse | `CashClosing` |
| Reçu | `Receipt` |
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

À compléter lors de la mise en place (tâche 0 du plan de travail) : démarrage, tests, migrations, génération du client API, build PWA.

## Façon de travailler

- Une tâche du plan = une branche = une PR, tests inclus.
- Avant de coder une fonction, relire la section correspondante du cahier des charges et du modèle de données.
- Après chaque tâche : cocher la case dans `docs/05-plan-de-travail.md` et noter toute décision nouvelle dans la section « Journal des décisions » de `docs/03-architecture-technique.md`.
- En cas de doute sur une règle scolaire RDC (bulletins, délibération, frais), demander plutôt que supposer.

## Suivi du projet (obligatoire)

Chaque étape doit être notée pour savoir à tout moment où en est le projet.

- **Début d'une tâche** : dans `docs/06-suivi.md`, mettre à jour « État actuel » (tâche en cours, branche).
- **Fin d'une tâche** : cocher dans `docs/05-plan-de-travail.md`, mettre à jour « État actuel » et « Avancement », ajouter une entrée datée au « Journal » (fait, tests, décisions, reste à faire).
- **Tout autre événement** (document reçu de l'ITIG, décision, blocage levé, question tranchée) : entrée datée au « Journal ».
- **Décision technique** : aussi dans le « Journal des décisions » de `docs/03-architecture-technique.md`.
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

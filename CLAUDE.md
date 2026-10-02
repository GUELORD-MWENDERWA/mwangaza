# CLAUDE.md — Mwangaza (nom de travail)

Plateforme de gestion scolaire multi-écoles pour la RDC, lancement à Goma.
École pilote : **ITIG Don Bosco Goma** (institut technique, ~1 200 élèves, ateliers mécanique / auto / électricité / électronique).

**L'ITIG est l'école d'exemple, pas la seule école.** Elle donne un cas concret (niveaux, options, frais, reçus, bulletins, rôles), mais chaque école, l'ITIG comprise, saisit elle-même ses vraies données dans l'application. **On n'attend rien de l'ITIG** (ni documents, ni données, ni essai sur place) : aucune tâche n'en dépend ; ce qui manque, Claude l'invente de façon réaliste pour les données de démonstration.

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

Espace de travail de Claude : `docs/claude/` — `plans/` (plan de chaque tâche avant de coder), `recherches/` (notes avec sources), `revues/` (anciennes revues, jusqu'à la 1.7 ; le résultat de `/verifier` va maintenant dans la PR).

GitHub (dépôt privé `GUELORD-MWENDERWA/mwangaza`) : un jalon par version (V1.0, V1.1, V1.2, V1.3, V1.4, V2 ; découpage du 2026-10-02 dans `05`), une issue par tâche titrée « <numéro> — … » ; la PR de la tâche contient `Closes #<n>`. Règles des PR : section « Travail avec GitHub ».

Si une demande sort du périmètre de `02-perimetre-v1.md`, le signaler avant de coder.

Pour tout écran : regarder la capture PNG **et** le HTML de la maquette, reproduire en React + Tailwind + shadcn/ui avec les jetons de `maquettes/README.md`. Les encadrés `.note` des maquettes sont des règles métier à appliquer, pas du contenu à afficher. Les documents `docs/` priment sur les maquettes en cas de contradiction.

## Stack (décidée — ne pas changer sans accord)

- Backend : Python 3.12+, Django 5.2 LTS, Django REST Framework, drf-spectacular (OpenAPI), PostgreSQL 16+, Celery + Redis, WeasyPrint (PDF)
- Frontend : TypeScript, React, Vite, vite-plugin-pwa (Workbox), Dexie.js (IndexedDB), TanStack Query, React Router, Tailwind CSS + shadcn/ui, react-hook-form + zod, i18next
- Applications front : `frontend/apps/gestion` (personnel de l'école, **hors-ligne d'abord**), `frontend/apps/portail` (parents et élèves, en ligne, léger) et, à partir de la V1.1 (5.2), `frontend/apps/console` (console de la plateforme pour le super-admin, à `admin.<domaine>` ; l'administration Django ne sert plus qu'au dépannage)
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
9. **Rien en dur pour une école ni pour la plateforme** : nom, logo, couleur, options, frais, formats et exemplaires des reçus, rôles personnalisés… viennent des paramètres de l'école ; le nom, le logo, les couleurs et le contact de la plateforme (aujourd'hui « Mwangaza ») viendront de ses paramètres (tâche 5.1), jamais du code.

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
| `make install` | `uv sync` (backend) + `pnpm install` (frontend) + `make hooks` |
| `make hooks` | installe les contrôles pre-commit (ruff, ESLint, Prettier, refus d'un `.env` ou d'une clé privée) sur les fichiers de chaque commit |
| `make dev` | `pnpm install` sur la machine, puis tout dans Docker : PostgreSQL (hôte : 5433), Redis, Django (:8000), Celery, Gestion (:5173), Portail (:5174) ; le conteneur du front réutilise le `node_modules` de la machine |
| `make dev-local` | Django et Vite sur la machine (valeurs dans `.env`, copié de `.env.example`) ; recette en bash pour que Ctrl+C arrête proprement les trois serveurs ; Vite lancé app par app (`pnpm dev` afficherait un faux échec à l'arrêt) |
| `make services` | seulement PostgreSQL et Redis dans Docker, prêts (`--wait`) ; rarement utile : la cible cachée `db-up` les démarre avant `dev-local`, `migrate`, `makemigrations`, `demo`, `superuser`, `shell` et `test-back` (pas en CI, où `CI` est défini) |
| `make stop` | arrêter les conteneurs |
| `make reset-db` | efface la base de développement de Docker (et celle des tests : `down --volumes`), puis `make migrate demo` ; pour une base qu'une migration ne peut plus suivre (`InconsistentMigrationHistory`, ex. nouveau modèle de compte en 1.2) |
| `make migrate` · `make makemigrations app=<app> name=<nom>` | migrations |
| `make demo` | crée ou remet à jour les données fictives (`apps/core/management/commands/demo.py`) : identité de la plateforme de départ (nom, couleurs, sans logo ni icône) avec un support et des mentions légales fictifs ; écoles `itig` et `volcans`, un compte par rôle (`apps/accounts/demo.py` : téléphones `0000001001`…, super-admin `0000000000`, mot de passe `mwangaza-demo` ; double authentification activée avec une clé commune pour les comptes qui l'exigent, super-admin compris, sauf le promoteur de l'ITIG) ; remet les écoles de démonstration comme au départ (couleur, abonnement, pas suspendues, logo public de l'ITIG) et leur organisation scolaire (année 2026-2027 en cours, découpage, niveaux, options, classes, format du matricule) ; frais de l'année (grille fictive : types, barèmes, tranches) et taux s'il manque ; élèves (800 à l'ITIG, 150 aux Volcans, avec familles et inscriptions ; créés une seule fois par école) ; réductions, caisses (toutes fermées) et paiements depuis la rentrée, deux crédits d'élèves et des demandes d'annulation (validée, refusée, en attente) par école ; un appareil par caissier et secrétaire ; trois annonces par école (une archivée, lues par une famille sur deux) ; compte du portail (`0002000001`) relié à la famille des deux écoles côté ITIG, code des Volcans affiché pour « Ajouter un enfant d'une autre école » ; trois demandes de coordonnées des parents à l'ITIG ; environ une famille sur trois a activé son compte du portail (une seule fois par école) ; débloque les essais ratés ; refusé hors `DEBUG` |
| `make totp` · `make totp key=<clé>` | code de double authentification du moment : comptes de `make demo`, ou clé donnée par `/api/auth/totp/setup/` ; refusé hors `DEBUG` |
| `make demo-excel` | liste d'élèves fictive `eleves-fictifs.xlsx` (~800 élèves, classes de l'ITIG de démonstration, erreurs glissées exprès) pour essayer l'import ; refusé hors `DEBUG` |
| `make messages` | traductions du serveur : `makemessages -l fr` puis `compilemessages` (`backend/locale/fr/LC_MESSAGES/django.po` et `.mo`, les deux dans Git) ; demande gettext ; texte source en anglais, **tout** texte traduit en français dans la même PR (`apps/core/tests/test_translations.py` refuse un texte vide ou « fuzzy » et un `.mo` pas recompilé) ; le serveur répond dans la langue de l'interface (cookie `django_language` posé par `packages/i18n`) |
| `make test` · `make test-back` · `make test-front` | pytest ; vérification des types puis Vitest (`*.test.ts` : logique, dans Node ; `*.test.tsx` : écrans, navigateur simulé jsdom avec Testing Library ; appareil en UTC), dans `frontend/apps` et `frontend/packages` |
| `make test-e2e` | parcours dans Chromium (Playwright, `frontend/e2e/`) : Django + Gestion aux adresses des écoles, données remises à zéro par `make demo` avant et après ; réutilise des serveurs déjà lancés (`make dev-local`) ; une fois avant : `cd frontend && pnpm exec playwright install chromium` |
| `make guide` | guide de la version en PDF (`docs/guide/guide-v<version>.pdf`, dans Git) : `frontend/guide/` — config Playwright à part (Django, Gestion, Portail ; `make demo` avant et après), `captures.spec.ts` (connexion avec chaque compte de démo, captures JPEG dans `guide/captures/`, hors Git ; version et nom de la plateforme), `guide.html` (texte, jetons du design) imprimé par Chromium ; pas dans la CI ; à la fin de chaque version : texte mis à jour, puis `make guide` |
| `make lint` · `make lint-back` · `make lint-front` | vérifie sans rien modifier : ruff (check + format) ; ESLint + Prettier |
| `make format` | corrige ce qui peut l'être : ruff, ESLint `--fix`, Prettier |
| GitHub Actions (`.github/workflows/ci.yml`) | à chaque PR et sur `main` : `make lint-back test-back` + schéma OpenAPI à jour (PostgreSQL 16) ; types du client de l'API à jour + `make lint-front test-front build` ; `make test-e2e` (job à part, PostgreSQL + Chromium) |
| `make api` · `make api-schema` | schéma OpenAPI → `frontend/packages/api/openapi.yaml`, puis types TypeScript du client → `frontend/packages/api/src/schema.d.ts` (à relancer après tout changement d'API) ; `api-schema` : seulement le schéma (CI du backend) |
| `make build` | build des deux PWA |
| `make prod-local` · `make prod-local-stop` | essai de la production sur la machine (`infra/docker-compose.yml`, valeurs de `infra/local.env`, projet `mwangaza-essai`) : images construites depuis `infra/Dockerfile` (front construit, Django + gunicorn, Caddy `tls internal`), ports 80 et 443 ; base vide (`make demo` refusé hors `DEBUG`) ; arrêt sans effacer les données |
| `make superuser` · `make shell` | compte super-admin ; console Django |
| `python3 maquettes/outils/maquettes.py menu` · `… index` · `node maquettes/outils/captures.mjs` | maquettes : menu latéral commun, galerie `index.html`, captures PNG (sans dépendance, Chrome de la machine) |

Adresses en dev : Gestion `http://itig.localhost:5173/app/` (le sous-domaine = code de l'école ; `…/api/school/` renvoie l'école ; écrans : `/app/login` et ses étapes `…/code`, `…/new-password`, `…/two-factor`, `/app/account`, `/app/schools`, `/app/support`, `/app/students/invitations` (invitations au portail), une adresse par entrée du menu, guide du caissier et du comptable par-dessus les écrans (« Aide et guide » en bas du menu) ; service worker seulement après `make build`, essai avec `cd frontend/apps/gestion && pnpm preview` sur le port 4173), Portail `http://localhost:5174/` (écrans `/login`, `/activate` (code famille prérempli depuis `#<code>`, QR de la lettre d'invitation), `/forgot-password`, `/` (mes enfants), `/children/<id>` (paiements), `/announcements`, `/profile`, `/add-school`, `/install`, `/guide` (guide du parent, après l'activation) ; service worker seulement après `make build` ; API sans école `/api/portal/auth/login/` · `activate/` · `reset/`, `/api/portal/me/`, `/api/portal/profile/`, `/api/portal/families/` · `families/link/`, `/api/portal/children/<id>/` · `…/photo/`, `/api/portal/payments/<id>/receipt/`, `/api/portal/announcements/` · `read/`, refusée à l'adresse d'une école), API `/api/…` via le proxy Vite (`/api/platform/` · `logo/` · `icon/` · `manifest/gestion/` · `manifest/portail/` : identité de la plateforme, publique à toute adresse, `/api/me/`, `/api/roles/`, `/api/staff/`, `/api/audit/`, `/api/school/settings/`, `/api/support/`, `/api/academic-years/`, `/api/levels/`, `/api/tracks/`, `/api/class-groups/`, `/api/matricule-format/`, `/api/students/`, `/api/families/` · `families/activation/` · `families/letters/` · `families/<id>/letter/` · `families/<id>/invitation-message/`, `/api/enrollments/`, `/api/student-imports/`, `/api/contact-changes/`, `/api/fee-types/`, `/api/fee-rules/`, `/api/exchange-rates/`, `/api/discounts/`, `/api/student-charges/`, `/api/cash-registers/`, `/api/cash-sessions/`, `/api/cash-closings/`, `/api/payments/`, `/api/cancellations/`, `/api/student-credits/`, `/api/unpaid/`, `/api/dashboard/`, `/api/announcements/`, `/api/devices/` · `/api/me/devices/`, `/api/sync/snapshot/` · `pull/` · `push/` depuis un appareil enregistré), vérification publique d'un reçu `/v/<id>` et d'une situation financière `/v/s/<jeton>` ; doc de l'API `/api/docs/` (seulement en `DEBUG`) ; administration Django `http://localhost:8000/admin/` (super-admin : mot de passe puis code de `make totp` ; identité de la plateforme : `/admin/core/platformsettings/`, jusqu'à la console de la 5.2) ; connexion en étapes `/api/auth/login/` (utilisable dans l'API navigable), puis `…/login/totp/`, `…/password/`, `…/totp/setup/` et `…/totp/activate/` selon l'étape renvoyée. Réglages Django : `config.settings.dev` (défaut de `manage.py`), `test` (pytest), `prod` (wsgi/asgi, refuse de démarrer sans `DJANGO_SECRET_KEY` ; adresse du visiteur lue dans `X-Real-IP` posé par Caddy). Essai de la production (`make prod-local`) : `https://itig.localhost/app/`, `https://parents.localhost/`, `https://admin.localhost/admin/` (certificat local de Caddy).

## Façon de travailler

- Une tâche du plan = une branche = une PR, tests inclus (voir « Travail avec GitHub »).
- Avant de coder une fonction, relire la section correspondante du cahier des charges et du modèle de données.
- Après chaque tâche : cocher la case dans `docs/05-plan-de-travail.md` et noter toute décision nouvelle dans la section « Journal des décisions » de `docs/03-architecture-technique.md`.
- En cas de doute sur une règle scolaire RDC (bulletins, délibération, frais), demander plutôt que supposer.

## Économie de tokens (obligatoire)

Le quota de tokens est limité et 30 tâches restent (2 pour clore la V1.0, 28 de la V1.1 à la V1.4) : une tâche doit tenir dans une conversation. La qualité ne baisse pas : les 9 règles non négociables, pas de requêtes N+1, listes paginées, pas de code bâclé ; une tâche = une branche = une PR (base `main`), Actions vert, l'utilisateur fusionne.

- **Tests peu nombreux, utiles, réalistes.** Écrire : isolation entre écoles, permissions, argent, audit, vraies règles métier ; Playwright seulement pour un chemin critique (connexion, caisse, hors-ligne). Ne pas écrire : ce que Django, DRF ou React garantissent déjà, les variantes presque identiques, les libellés ou la mise en page, les cas irréalistes. Dans un fichier de tests ouvert pour la tâche, supprimer ou fusionner les tests redondants (pas de grand nettoyage à part) ; **ne jamais supprimer** un test d'isolation, de permission, d'argent ou d'audit. Erreurs glissées exprès seulement pour l'argent, l'isolation et le hors-ligne.
- **Lancer peu.** Pendant le travail : les tests du module touché, depuis la racine — `set -a && . ./.env && set +a && cd backend && uv run pytest apps/<app> -q | tail -3` (variables de `.env`, que `make` charge d'habitude) ; `cd frontend && pnpm exec vitest run apps/gestion/src/features/<dossier> | tail -5` (depuis `frontend/` : sa configuration). **Pas de suite complète en local** (≈ 9 min sur la machine) : la CI la lance (≈ 5 min, trois jobs en parallèle).
- **Vérifier peu.** Nouvel écran : une seule capture, à 390 px. Pas de rejeu des étapes « À tester toi-même ».
- **Documents courts.** Plan (`docs/claude/plans/`) : 20 lignes maximum. Suivi : voir « Suivi du projet ». Courts ne veut pas dire oubliés : **à chaque tâche, tous les `.md` que le changement rend faux ou incomplets sont mis à jour dans la même PR** (liste : « Suivi du projet », fin d'une tâche). Pas de fichier dans `docs/claude/revues/` : le résultat de `/verifier` tient en quelques lignes dans la PR. Description de PR et message de fin courts : ce qui change, « À valider », « À tester toi-même » (3 à 5 étapes), « Après la fusion ».
- **Lire peu.** Seulement les passages utiles (`grep -n`, `sed -n a,bp`), pas un fichier entier déjà connu ; ne pas relire un fichier qu'on vient de modifier ; filtrer les sorties longues (`tail`, `grep`). Pas de sous-agents sauf demande de l'utilisateur.
- **Taille.** Une tâche qui dépasse à peu près un module serveur ou deux écrans : proposer de la découper dans `05` avant de coder.
- **Une conversation par tâche.** Claude ne peut pas taper `/clear` ni `/compact` : à la fin d'une tâche, dire « Fusionne la PR, puis tape /clear et /tache X.Y » ; si la conversation devient longue en cours de tâche, dire « Tape /compact » juste après un commit. Tâche simple (écrans de saisie, documents) : rappeler que `/model` permet de passer à Sonnet.

## Travail avec GitHub

Rôles : **Claude est le développeur** (code, teste, ouvre les PR). **L'utilisateur est le chef de projet et le relecteur** : il valide les décisions, teste ce qui est visible et fusionne. En relisant une PR, il regarde : contrôles verts, description conforme à la tâche, section « À valider », puis ses tests ; le code (*Files changed*) seulement pour apprendre ou vérifier un point précis. **La description doit donc suffire pour comprendre ce qui a changé sans lire le code.**

1. **Une seule PR par tâche du plan** (1.1 → une PR). Les corrections, petites réparations et mises à jour de documents faites pendant la tâche vont dans cette PR, jamais dans des PR séparées.
2. **PR séparée seulement dans deux cas** : une décision importante que l'utilisateur doit valider avant que Claude continue, ou une correction urgente qui bloque le travail. Dire clairement, dans la PR et dans la réponse, pourquoi elle est séparée.
3. **Toujours `base: main`**, branche partie de `main` à jour. Jamais de PR empilée sur une autre branche : si la tâche a besoin d'une PR pas encore fusionnée, le dire et attendre la fusion.
4. **Ne jamais fusionner.** C'est toujours l'utilisateur qui fusionne.
5. **Pas d'attente à vide** : un seul push à la fin, puis la PR est donnée tout de suite, contrôles en cours ; l'utilisateur commence ses tests pendant que Claude surveille la CI en arrière-plan et confirme « ✅ contrôles verts » (ou corrige dans la même PR et le dit). L'utilisateur ne fusionne qu'après le ✅ ou les coches vertes.
6. **Description de la PR**, en français simple : ce qui change et pourquoi (sans jargon inutile), les tests, puis trois sections courtes :
   - **« À valider »** : les décisions ou propositions que l'utilisateur accepte en fusionnant, avec où les lire ; ou « Rien ».
   - **« À tester toi-même »** : 3 à 5 étapes, commandes exactes et pages à ouvrir (adresses complètes), avec le résultat attendu pour chacune. Si rien n'est visible, le dire.
   - **« Après la fusion »** : ce qu'il faut taper (ex. `git switch main && git pull && make install`) et la prochaine tâche.

   Puis `Closes #<n>`. Modèle : skill `tache`, étape 5.
7. **Message de fin dans le terminal** : il reprend ces trois sections, sans détails techniques inutiles, puis « Fusionne la PR, puis tape /clear et /tache X.Y » et la ligne `📍`.

Côté utilisateur, la marche à suivre est dans `A-FAIRE.md` § 10 « Comment relire et fusionner une PR ».

## Données de démonstration

On travaille avec des données **fictives et réalistes** : `make demo` recrée l'école `itig` (démo : ~800 élèves avec familles, fratries et paiements sur plusieurs mois), une seconde école fictive `volcans`, plus petite, pour prouver l'isolation, et un compte par rôle (détail : `docs/07-a-fournir.md` § 4). Les vraies données, c'est l'école qui les saisit. Chaque tâche qui ajoute un modèle enrichit cette commande. Jamais de vraie donnée personnelle dans les données de démonstration ni dans les tests.

## Suivi du projet (obligatoire)

Chaque étape doit être notée pour savoir à tout moment où en est le projet.

- **Début d'une tâche** : dans `docs/06-suivi.md`, mettre à jour « État actuel » (tâche en cours, branche).
- **Fin d'une tâche** : cocher dans `docs/05-plan-de-travail.md` ; dans `06`, « État actuel », le compteur du bloc dans « Avancement » et une entrée datée de 3 à 5 lignes au « Journal » (fait, tests, décisions, suite). **Puis passer en revue tous les autres `.md`** et mettre à jour, dans la même PR, chacun que la tâche rend faux ou incomplet :
  - `CLAUDE.md` (tableau « Commandes », ligne `make demo`, « Adresses en dev » : nouvel écran, nouvelle API) et `A-FAIRE.md` § 11 (mêmes commandes et adresses, en langage simple) — les deux ensemble ;
  - `A-FAIRE.md` « Maintenant » et § 8–9 (action de l'utilisateur nouvelle, faite ou devenue urgente) ;
  - `docs/02` à `04` (règle précisée, entité ou champ, décision technique au « Journal des décisions » de `03`), `docs/07-a-fournir.md` (§ 1 maquette dessinée ou validée, § 2 information reçue, § 4 ce que crée `make demo`) ;
  - `maquettes/README.md` (écran codé avec un écart à sa maquette, nouvelle maquette) ;
  - `README.md`, `docs/claude/README.md`, `infra/README.md`, `frontend/packages/*/README.md` (organisation qui change) ;
  - `.claude/skills/*/SKILL.md` (façon de faire, commande, helper de test ou adresse qu'une skill cite).
- **Tout autre événement** (document reçu de l'ITIG, décision, blocage levé, question tranchée) : entrée datée au « Journal ».
- **Décision technique** : aussi dans le « Journal des décisions » de `docs/03-architecture-technique.md`.
- **Action qui attend l'utilisateur** (installer, fusionner une PR, demander à l'ITIG, acheter, créer un compte) ou **commande nouvelle ou changée** : mettre à jour `A-FAIRE.md` (ce qu'il doit faire, comment, avec quelles commandes ; cocher ce qui est fait). Le signaler dans la réponse.
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

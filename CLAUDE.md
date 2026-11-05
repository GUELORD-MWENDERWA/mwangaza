# CLAUDE.md — Mwangaza (nom de travail)

Plateforme de gestion scolaire multi-écoles pour la RDC, lancement à Goma. École d'exemple : **ITIG Don Bosco Goma** (institut technique, ~1 200 élèves). Elle donne un cas concret (niveaux, options, frais, reçus, bulletins, rôles), mais **chaque école saisit elle-même ses vraies données** ; on n'attend rien de l'ITIG : ce qui manque, Claude l'invente de façon réaliste pour la démonstration.

## Au début de chaque session

Lire « État actuel » de `docs/06-suivi.md`. Pour un lot : skill `tache` (elle dit quoi lire ensuite).

## Documents (lire seulement les passages utiles, par `grep -n`)

`docs/01-cahier-des-charges.md` (vision) · `02-perimetre-v1.md` (**ce qu'on construit maintenant** ; demande hors périmètre : le signaler avant de coder) · `03-architecture-technique.md` (stack, multi-écoles, hors-ligne, sécurité, « Journal des décisions ») · `04-modele-de-donnees.md` (entités, règles) · `05-plan-de-travail.md` (**la file** : § 2, 17 lots ; § 8.2 définition de « fini ») · `06-suivi.md` (état, journal) · `07-a-fournir.md` (ce qui manque et ce qu'on utilise en attendant) · `docs/specs/` (spécification d'un module) · `maquettes/README.md` (design, inventaire des écrans) · `docs/claude/reference.md` (**chaque commande, chaque écran, chaque API, contenu de `make demo`**) · `docs/claude/plans/` (fiche de chaque lot). École pilote : `docs/ecole-pilote/fiche-itig.md` ; `depot/` et `prive/` hors Git.

GitHub `GUELORD-MWENDERWA/mwangaza` (public jusqu'à la fin de la V2) : jalon « V1 complète », une issue « Lot N — … » par lot.

## Stack (décidée — ne pas changer sans accord)

- Backend : Python 3.12+, Django 5.2 LTS, DRF, drf-spectacular, PostgreSQL 16+, Celery + Redis, WeasyPrint, Pillow
- Frontend : TypeScript, React, Vite, vite-plugin-pwa, Dexie.js, TanStack Query, React Router, Tailwind + shadcn/ui, react-hook-form + zod, i18next
- Applications : `frontend/apps/gestion` (personnel, **hors-ligne d'abord**), `frontend/apps/portail` (parents et élèves, en ligne), `frontend/apps/console` (plateforme, `admin.<domaine>`)
- Infra : Docker Compose, Caddy, un serveur, Cloudflare, sauvegardes vers stockage objet
- Tests : pytest + pytest-django + factory_boy ; Vitest ; Playwright. Qualité : ruff, ESLint + Prettier, pre-commit, GitHub Actions

## Règles non négociables

1. **Isolation des écoles** : tout modèle métier hérite de `TenantModel` (champ `school`), y compris `Student`, `Family` et `Guardian`. Toute requête passe par le manager scopé. Chaque nouveau modèle, écran ou point d'API a un test qui prouve qu'une école ne peut **ni lire ni modifier** les données d'une autre (API, exports, rapports, recherche, portail compris).
2. **Argent** : montants en **entiers** (centimes USD, francs FC) + code devise. Jamais de `float`. Taux de change enregistré sur chaque paiement.
3. **Paiements immuables** : jamais modifiés ni supprimés ; une annulation est un nouvel enregistrement lié (motif, permission dédiée, audit). Seule exception : suppression d'un espace d'essai ou de démonstration (`03` § 4 bis).
4. **Identifiants** : UUID v7 générés côté client pour toute donnée créable hors-ligne ; toute écriture de synchronisation est idempotente.
5. **Audit** : toute création / modification / annulation sur finances, notes, paie et rôles écrit dans `AuditLog`.
6. **Permissions** vérifiées côté serveur sur chaque endpoint ; le front ne fait que masquer.
7. **i18n** : aucun texte d'interface en dur ; français par défaut, anglais disponible.
8. **Pas de nouvelle dépendance** sans l'expliquer et demander.
9. **Rien en dur pour une école ni pour la plateforme** : nom, logo, couleur, options, frais, reçus, rôles… viennent des paramètres de l'école ; nom, logo, couleurs et contact de la plateforme, de ses paramètres.

## Conventions de code

- Code, modèles, variables et API en **anglais** ; interface fr / en par i18n. Commits en français, style conventionnel (`feat(finance): encaissement partiel`).
- Backend : une app Django par domaine (`core`, `accounts`, `schools`, `students`, `finance`, `academics`, `timetable`, `payroll`, `portal`, `notifications`, `sync`, `audit`, `ai`, `billing`, `equipment`) ; logique dans `services.py`, pas dans les vues ; pas de N+1 ; listes paginées.
- Front : dossiers par fonctionnalité (`features/finance/...`) ; client API typé généré depuis l'OpenAPI (`packages/api`, `make api`).
- Glossaire (terme RDC → code) :

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
| Échéancier | `FeeRule.schedule_kind` + `InstallmentTemplate` ; échéancier particulier : `StudentCharge` avec `source=custom` |
| Taux de change (fixe pour l'année, corrigeable) | `ExchangeRate` |
| Caisse · clôture de caisse | `CashRegister` · `CashClosing` |
| Reçu | pas de modèle : vue imprimable d'un `Payment` (`receipt_number`) |
| Reprise en cours d'année (payé avant Mwangaza) | `Payment` avec `origin=prior`, sans `cash_session` ni reçu |
| Option (humanités) · section de classe (6e A) | `Track` · `ClassGroup` |
| Année scolaire · période (P1, P2…) · inscription annuelle | `AcademicYear` · `Term` · `Enrollment` |
| Famille / tuteur | `Family` / `Guardian` |
| Événement du calendrier · convocation des parents | `SchoolEvent` · `Summons` |
| Circulaire | pas de modèle : vue imprimable d'une `Announcement` |
| Prime / motivation enseignants | `TeacherBonus` |
| Passage de classe, confirmation de place | `PlaceConfirmation` (`academics/promotion.py`) |
| Règlement des études (délibération) | `School.settings["pass_rules"]`, `Level.pass_rules` (`schools/pass_rules.py`) ; décision proposée : `academics/resits.py` |
| Cours commun à plusieurs classes · remplaçant d'un cours | `CourseGroup` · `CourseSubstitute` |
| Appareil (console, lecteur, relais), sonnerie, présence par lecteur | `Equipment` (`Device` = navigateur de la Gestion hors ligne), `BellProfile` / `BellSlot`, `AttendanceSession` / `AttendanceRecord` (`docs/specs/equipements.md`) |
| Cours principal, branche d'option, pratique (atelier) | `Course.category` (`main`, `option`, `practical`, `general`) |

## Commandes essentielles

Outils : `uv` (`~/.local/bin`), `pnpm` (corepack), `make`, Docker. `make` seul affiche la liste ; **détail de chaque commande : `docs/claude/reference.md`** (seule liste complète ; `A-FAIRE.md` § 11 la résume en langage simple pour l'utilisateur).

| Commande | Effet |
|---|---|
| `make dev` · `make dev-local` · `make stop` | tout dans Docker ; ou sur la machine (migrations d'abord) ; arrêter |
| `make migrate` · `make demo` | migrations ; données fictives `itig-demo` (800 élèves) et `volcans` (150), un compte par rôle (`0000001001`…, mot de passe `mwangaza-demo`), parent `0002000001` |
| `make api` · `make messages` | schéma OpenAPI + types (après tout changement d'API, docstring comprise) ; traductions du serveur (tout traduit en français) |
| `make lint` · `make test-e2e` | lint ; parcours Playwright |
| `make apercu ecran=<app/écran>` | captures à 390, 820, 1440 px + `rapport.json` (ses propres serveurs à neuf, ≈ 2 min) |
| `make deploy` | mise en ligne (skill `deployer`) |

Tests du module touché, depuis la racine : `set -a && . ./.env && set +a && cd backend && uv run pytest apps/<app> -q | tail -3` ; `cd frontend && pnpm exec vitest run apps/gestion/src/features/<dossier> | tail -5` ; types : `pnpm typecheck 2>&1 | grep 'error TS'`. Adresses en dev : Gestion `http://itig-demo.localhost:5173/app/`, Portail `http://localhost:5174/`, Console `http://admin.localhost:5175/`, API et site `http://localhost:8000/` ; un `curl` vers l'API d'une école passe l'hôte (`-H "Host: itig-demo.localhost"`).

## Façon de travailler

- **Un lot du plan (`05` § 2) = une branche = une PR**, en **3 parties au plus** (serveur, écrans, fin du lot), une conversation chacune ; commit et push de sauvegarde à la fin de chaque partie. Skill `tache`.
- **Regard de développeur senior** avant d'accepter une tâche, un plan ou une demande (y compris de l'utilisateur) : utile ? faisable ? coût pour le serveur (écritures par requête, tâches de fond, taille des tables, écran chargé souvent) ? Retirer ou simplifier, le dire avec la raison dans la fiche et dans « À valider », puis travailler. Règle scolaire RDC floue : demander.
- **Écrans** : jamais une page sans maquette (capture PNG **et** HTML de `maquettes/`, jetons de `maquettes/README.md`) ; même un petit ajout a sa maquette avant le code ; sinon la dessiner d'après les grands logiciels (skill `design`). Toute application s'adapte au téléphone, à la tablette et à l'ordinateur. Les encadrés `.note` des maquettes sont des règles métier, pas du contenu ; les documents `docs/` priment. En-tête des documents imprimés : exemplaire fourni (logo, drapeau, lignes centrées, filet épais, titre avec N° de référence).
- **Vérification visuelle en fin de lot**, en une passe : chaque écran du lot à 390 et 1440 px (`make apercu`), comparé à sa maquette (alignement, débordement, textes bruts). Pendant une partie : typecheck, lint et tests seulement.
- **Un outil qui bloque deux fois** : chercher la cause dans l'environnement (base migrée ? serveur à jour ? hôte de l'école ?), sinon passer et le dire. Jamais d'attente sans délai.
- Fin d'un lot : cocher ses tâches dans `05`, décision nouvelle au « Journal des décisions » de `03`.

## Économie de tokens (obligatoire)

Une partie de lot tient dans une conversation ; la qualité ne baisse pas (9 règles, pas de N+1, listes paginées, pas de code bâclé).

- **Tests peu nombreux, utiles, réalistes** : isolation entre écoles, permissions, argent, audit, vraies règles métier ; Playwright seulement pour un chemin critique (connexion, caisse, hors-ligne). Pas de test de ce que Django, DRF ou React garantissent, de variante presque identique, de libellé ou de mise en page. **Ne jamais supprimer** un test d'isolation, de permission, d'argent ou d'audit. Erreurs glissées exprès seulement pour l'argent, l'isolation et le hors-ligne.
- **Lancer peu** : les tests du module touché ; la suite complète, c'est la CI (≈ 5 min). Un test ne refait jamais `make demo` : sa vérification s'ajoute au scénario de `core/tests/test_demo.py`.
- **Lire peu** : `grep -n`, `sed -n a,bp`, sorties filtrées (`tail`, `cut -c1-200`) ; ne pas relire un fichier qu'on vient de modifier ; explorer en 5 à 10 appels groupés ; pas de sous-agents sauf demande.
- **Documents courts** : fiche du lot 30 lignes ; journal 3 à 5 lignes ; résultat de `/verifier` dans la PR ; description de PR courte.
- **Modèle** : effort `high` (jamais `xhigh`) ; Opus pour le serveur difficile, Sonnet pour les écrans et la fin de lot — le dire en fin de partie.
- Fin de partie : commit + push, puis « Tape /clear puis /tache lot N » ; fin de lot : « Fusionne la PR, puis tape /clear et /tache lot N+1 » ; conversation longue : « Tape /compact » juste après un commit.

## Travail avec GitHub

**Claude est le développeur** (code, teste, ouvre les PR) ; **l'utilisateur est le chef de projet et le relecteur** (valide, teste ce qui est visible, fusionne). La description de PR doit suffire sans lire le code.

1. **Une seule PR par lot**, `base: main`, branche partie de `main` à jour, **ouverte en brouillon dès la partie 1** (la CI vérifie chaque push ; passée en relecture à la fin du lot) ; les petites réparations du lot vont dedans. PR séparée seulement pour une décision à valider avant de continuer ou une correction urgente (le dire et pourquoi). Jamais de PR empilée.
2. **Ne jamais fusionner.**
3. Pas d'attente à vide : PR donnée tout de suite, CI surveillée en arrière-plan, puis « ✅ contrôles verts » (ou correction dans la même PR).
4. Description en français simple : ce qui change et pourquoi, tests, puis **« À valider »** (ou « Rien »), **« À tester toi-même »** (5 à 8 étapes, adresses complètes, résultat attendu), **« Après la fusion »** ; puis `Closes #<n>`. Modèle : skill `tache`.
5. Message de fin dans le terminal : ces trois sections, puis la ligne `📍`.

Côté utilisateur : `A-FAIRE.md` § 10.

## Données de démonstration

Fictives et réalistes (développement, tests, serveur de démonstration) ; `make demo` recrée les espaces de démonstration (`03` § 4 bis) : `itig-demo`, `volcans` (preuve d'isolation), un compte par rôle (`07` § 4). Chaque nouveau modèle enrichit `make demo`. Jamais de vraie donnée personnelle.

## Suivi du projet (obligatoire)

- Début d'un lot : « État actuel » de `docs/06-suivi.md`. Fin d'une partie : partie cochée dans la fiche, compteur « Avancement ».
- Fin d'un lot : tâches cochées dans `05`, « État actuel » et entrée datée (3 à 5 lignes) au « Journal » de `06` ; **puis tout `.md` que le lot rend faux ou incomplet, dans la même PR** : `docs/claude/reference.md` (commande, `make demo`, écran, API — seule liste), `A-FAIRE.md` (action de l'utilisateur ; tableau des commandes du § 11), `docs/02` à `04`, `07` (§ 1 maquettes, § 4 `make demo`), `maquettes/README.md`, READMEs, `.claude/skills/*/SKILL.md`, `CLAUDE.md` (commande essentielle seulement).
- Autre événement (décision, blocage levé, document reçu) : entrée datée au « Journal » de `06` ; décision technique : aussi dans `03`. Action qui attend l'utilisateur : `A-FAIRE.md`, et le dire.
- Chaque réponse de travail finit par : `📍 Lot N (partie k/n) — étape — prochaine action`.

## Skills du projet (`.claude/skills/`)

| Commande | Quand |
|---|---|
| `/etat` | Faire le point : où on en est, prochaine tâche, bloquants |
| `/tache lot N` | Réaliser un lot : une partie par conversation, une PR à la fin |
| `/noter …` | Noter une étape, une décision, un document reçu, un blocage |
| `/ecran …` · `/design` | Construire un écran d'après sa maquette · système de design |
| `/backend` · `/argent` · `/hors-ligne` | Modèle, service, endpoint · montants · synchronisation |
| `/verifier` | Contrôle des règles non négociables avant commit / PR |
| `/document-ecole` · `/deployer` | Document réel de l'ITIG · serveur en ligne |

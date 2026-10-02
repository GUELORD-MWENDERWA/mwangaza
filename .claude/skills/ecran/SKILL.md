---
name: ecran
description: Construire un écran de l'application Gestion ou du Portail Mwangaza à partir de sa maquette (capture PNG + HTML) en React + Tailwind + shadcn/ui, avec i18n, permissions, états hors-ligne / vide / erreur et tests. À utiliser dès qu'une tâche ou une demande porte sur un écran, une page, un formulaire ou une impression (ex. « /ecran caisse-encaissement », « fais l'écran des impayés »).
argument-hint: "<nom du fichier de maquette, ex. caisse-encaissement>"
---

# Construire l'écran : $ARGUMENTS

Suivre aussi la skill `design` (jetons, composants, formats).

## 1. Trouver la maquette

| Maquette | Lot | Réf. | Tâche |
|---|---|---|---|
| `gestion/connexion`, `gestion/connexion-double-authentification`, `gestion/double-authentification-activation`, `gestion/mon-compte` | V1.0 | B4–B5 | 1.3 (écrans en 1.6) |
| `gestion/choix-ecole`, `gestion/personnel-comptes` | V1.0 | B1–B3 | 1.2 (écrans en 1.6) |
| `gestion/journal-audit` | V1.0 | I1 | 1.4 |
| `gestion/deverrouillage-pin` | V1.0 | B5 | 3.7 |
| `gestion/tableau-de-bord` (sert aussi de référence pour la coquille), `gestion/menu-mobile`, `gestion/pages-etat` | V1.0 | G3, § 9.4 | 1.6 (coquille, menu, états), 4.2 |
| `gestion/roles-permissions` | V1.0 | B1–B2 | 1.2 |
| `gestion/parametres-ecole` | V1.0 | A1, M5 | 1.5 (API), 1.7 (écran), 3.2 (reçus), 4.2 (alertes) |
| `gestion/superadmin-ecoles` | V1.0 dans l'administration Django (1.5) ; écran dans la console : V1.1 | A1–A3 | 5.3 |
| `gestion/organisation-scolaire` | V1.0 | C1–C3 | 1.7 |
| `gestion/eleves-liste`, `gestion/eleve-fiche-identite`, `gestion/eleve-fiche-famille`, `gestion/eleve-fiche-historique`, `gestion/eleve-fiche`, `gestion/eleve-nouveau`, `gestion/famille-fiche` | V1.0 | D2–D4 | 2.2 (onglet Finances : 2.7) |
| `gestion/eleves-import` | V1.0 | D1 | 2.3 |
| `gestion/fiche-inscription`, `gestion/liste-classe` | V1.0 | D5 | 2.4 |
| `gestion/frais-baremes`, `gestion/eleve-reduction` | V1.0 | E1–E5 | 2.5 |
| `gestion/eleve-echeancier` | V1.0 | E4 | 2.6 |
| `gestion/caisse-ouverture`, `gestion/caisse-accueil`, `gestion/caisse-encaissement` | V1.0 | F1–F5 | 3.1 (en ligne), 3.5 (hors-ligne) |
| `gestion/recu`, `portail/verification-recu` | V1.0 | F3–F6, F4 | 3.2 |
| `gestion/appareils-synchro` | V1.0 | F5, B5 | 3.3, 3.7 |
| `gestion/credits-eleves` | V1.0 | — | 3.6 |
| `gestion/annulations`, `gestion/recu-annulation`, `gestion/caisse-cloture`, `gestion/clotures-caisse` | V1.0 | F7, F8 | 3.8 |
| `gestion/impayes`, `gestion/situation-financiere`, `gestion/impayes-export` | V1.0 | G1–G2 | 4.1 |
| `gestion/annonces` | V1.0 | H4 | 4.3 |
| `portail/activation`, `connexion`, `mot-de-passe-oublie`, `installer`, `accueil`, `enfant-paiements`, `annonces`, `profil` ; `gestion/changements-coordonnees` | V1.0 | H1–H6 | 4.4 |
| `gestion/guide-premiere-connexion`, `portail/guide` | V1.0 | I3 | 4.5 |
| `gestion/paie` | **V1.3** | 7.3 | 7.3 |
| `gestion/presences-pointage-qr` | **V1.2** | 6.3 | 6.3 |
| `gestion/cours-maxima`, `gestion/notes-saisie`, `gestion/bulletin`, `gestion/bulletin-education-de-base`, `portail/enfant-scolarite` | **V1.4** | 8.x | 8.1, 8.2, 8.3, 8.8 |

Maquettes marquées « à valider » dans `maquettes/README.md` : dessinées par Claude ; si l'utilisateur a laissé une remarque (PR ou `docs/06-suivi.md`), l'appliquer à la maquette avant de coder.

Écran absent de ce tableau : chercher dans `docs/07-a-fournir.md` § 1 (M1–M20…). S'il n'a pas de maquette, **la dessiner d'abord** dans le même système (`maquettes/<app>/<nom>.html` avec `assets/styles.css` et la coquille de `maquettes/outils/maquettes.py`, encadrés `.note` pour les règles), l'ajouter à `maquettes/README.md` et au catalogue de `maquettes.py` (puis `python3 maquettes/outils/maquettes.py index` et `node maquettes/outils/captures.mjs <fichier>`), puis **coder avec elle sans attendre l'accord** (décision du 2026-09-29) : la signaler dans « À valider » de la PR, la noter dans `07` § 1.

Écran d'une version suivante que celle de la tâche en cours (version de chaque tâche : `05`) : **s'arrêter et le signaler**. Les éléments d'une version suivante à l'intérieur d'un écran ne sont pas codés et leurs entrées de menu sont masquées. Les bandeaux de version des maquettes datent de l'ancien découpage (avant le 2026-10-02) : la version qui compte est celle de `05`.

## 2. Lire la maquette

1. Regarder la capture : `maquettes/captures/desktop/<app>-<nom>.png` (ouvrir l'image avec l'outil Read) ; la mobile seulement si la desktop ne suffit pas.
2. Lire `maquettes/<app>/<nom>.html` : structure, libellés exacts, colonnes, boutons, raccourcis clavier.
3. Extraire **chaque encadré `.note`** : ce sont des règles métier et des critères d'acceptation. Les lister ; chacun devient un test ou une vérification explicite. Ne jamais les afficher.
4. Recouper avec la user story (`docs/02-perimetre-v1.md`) et les champs (`docs/04-modele-de-donnees.md`). **Les documents font foi** : noter tout écart et le signaler à l'utilisateur.
5. Les données des maquettes (noms, montants, taux, dates — jour simulé 19/10/2026) sont fictives : ne pas les coder en dur. Elles peuvent servir de données de démonstration.

## 3. Construire

- Emplacement : `frontend/apps/<gestion|portail>/src/features/<domaine>/…` ; composants génériques dans `frontend/packages/ui`.
- **Gestion** : un écran du menu se branche dans `SCREENS` de `src/routes.tsx` (le droit de l'entrée est vérifié avant, sinon page 403) ; compte connecté : `useCurrentMe()`, école de l'adresse (nom, fuseau) : `useCurrentSchool()`, droits : `can(me, [...])` ; erreurs : `errorMessage()`, `fieldMessage()` et `applyServerErrors()` de `src/lib/errors.ts` (jamais le `detail` du serveur) ; données pas lues : `LoadError` (`features/status/StatusPages.tsx` : pas de réseau, droit retiré, erreur) ; liste paginée par le serveur : `Pagination` (`features/shell/Pagination.tsx`) ; noms et téléphones : `fullName()`, `formatPhone()`, `roleName()` de `src/lib/people.ts` ; jour du calendrier (`2026-09-07`) : `formatDay` ; dates : `formatDate` / `formatTime` de `@mwangaza/i18n` avec `school.timezone`.
- Composants shadcn/ui + jetons de la skill `design`. Ne pas copier le HTML ni les classes des maquettes.
- **Textes** : aucun en dur. Clés i18next par fonctionnalité (ex. `finance.cashier.collectAndPrint`) ; `fr` reprend les libellés de la maquette mot pour mot, puis traduction `en`.
- **Données** : client typé `frontend/packages/api` (généré depuis l'OpenAPI) + TanStack Query. Écran utilisable hors-ligne (caisse, élèves, reçus) : lire et écrire via Dexie selon la skill `hors-ligne`.
- **Formulaires** : react-hook-form + zod ; mêmes schémas que la synchronisation quand ils existent.
- **Montants** : skill `argent` ; formatage uniquement via `packages/money`.
- **Permissions** : masquer les actions selon les codes de `docs/04-modele-de-donnees.md` § 8 ; le serveur vérifie de son côté.
- **États** que la maquette ne montre pas : chargement, liste vide, erreur, hors-ligne, opérations en attente — les traiter avec `Banner`, `StatusPill`, squelettes, dans le style du système.
- **Clavier** : reprendre les raccourcis indiqués (caisse : `Ctrl K` rechercher, `F9` valider, `Échap` changer d'élève) ; double-clic / double envoi protégé sur les actions d'argent.
- Mobile : vérifier l'écran à 390 px ; le Portail est conçu mobile d'abord.

## 4. Vérifier

1. Tests (« Économie de tokens » de `CLAUDE.md`) : Vitest pour les règles `.note` qui protègent quelque chose (permissions masquées, argent, règle métier) — pas de test de libellé ou de mise en page ; Playwright seulement pour un chemin critique (connexion, caisse, hors-ligne). Lancer seulement le dossier touché, depuis `frontend/` : `pnpm exec vitest run apps/gestion/src/features/<dossier>`. Écrans de la Gestion (`*.test.tsx`) : `renderApp("/adresse")` (`src/test/render.tsx` ; guide de première connexion déjà vu, sauf `renderApp("/", { guide: true })`), faux serveur `mockApi({"GET /api/…": réponse})` (il renvoie les requêtes reçues avec `query` et `body`), `apiError(code, statut)` (`src/test/api.ts`), comptes `me("cashier")`, `platformAdmin()` (`src/test/fixtures.ts`). Parcours réels : `frontend/e2e/*.spec.ts` (`make test-e2e` ; un compte à code une seule fois par parcours : un code ne sert qu'une fois ; caissier ou comptable : `skipGuide(page)` après la connexion). Élément qu'une étape du guide doit montrer : attribut `data-guide` (`features/guide/guides.ts`).
2. Une seule capture de l'écran construit, à 390 px, comparée à la maquette ; lister les différences restantes. Pas de capture à 1440 px ni de rejeu du parcours à la main.
3. Aucun texte en dur : `apps/gestion/textes.test.ts` le vérifie (texte entre balises, `label`, `placeholder`, `title`, `aria-label`, `alt`) ; `fr` et `en` aux mêmes clés : TypeScript et `packages/i18n/src/locales.test.ts`.

## 5. Rendre compte

Liste courte : règles `.note` appliquées (et testées), écarts avec la maquette ou les documents, états ajoutés, puis `📍` l'état de la tâche. Écart à la maquette → noté sur la ligne de l'écran dans `maquettes/README.md` ; nouvelle adresse → « Adresses en dev » de `CLAUDE.md` et § 11 de `A-FAIRE.md` (même PR).

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
| `gestion/connexion`, `gestion/connexion-double-authentification` | V1.0 | B4 | 1.3 (écran en 1.6) |
| `gestion/deverrouillage-pin` | V1.0 | B5 | 3.7 |
| `gestion/tableau-de-bord` (sert aussi de référence pour la coquille) | V1.0 | G3 | 1.6 (coquille), 4.2 |
| `gestion/roles-permissions` | V1.0 | B1–B2 | 1.2 |
| `gestion/superadmin-ecoles` | V1.0 | A1–A3 | 1.5 |
| `gestion/organisation-scolaire` | V1.0 | C1–C3 | 1.7 |
| `gestion/eleves-liste`, `gestion/eleve-fiche`, `gestion/eleve-nouveau` | V1.0 | D2–D4 | 2.2 (onglet Finances : 2.7) |
| `gestion/eleves-import` | V1.0 | D1 | 2.3 |
| `gestion/frais-baremes` | V1.0 | E1–E5 | 2.5 |
| `gestion/caisse-encaissement` | V1.0 | F1–F5 | 3.1 (en ligne), 3.5 (hors-ligne) |
| `gestion/recu`, `portail/verification-recu` | V1.0 | F3–F6, F4 | 3.2 |
| `gestion/appareils-synchro` | V1.0 | F5, B5 | 3.3, 3.7 |
| `gestion/annulations`, `gestion/caisse-cloture` | V1.0 | F7, F8 | 3.8 |
| `gestion/impayes` | V1.0 | G1–G2 | 4.1 |
| `gestion/annonces` | V1.0 | H4 | 4.3 |
| `portail/activation`, `accueil`, `enfant-paiements`, `annonces`, `profil` | V1.0 | H1–H5 | 4.4 |
| `gestion/paie` | **V1.1** | 5.3 | 5.3 |
| `gestion/presences-pointage-qr` | **V1.1** | 5.5 | 5.5 |
| `gestion/notes-saisie`, `gestion/bulletin`, `portail/enfant-scolarite` | **V1.2** | 6.x | 6.2, 6.3, 6.8 |

Écran absent de ce tableau : chercher dans `docs/07-a-fournir.md` § 1 (M1–M20…). S'il n'a pas de maquette, **la dessiner d'abord** dans le même système (`maquettes/<app>/<nom>.html` avec `assets/styles.css`, encadrés `.note` pour les règles), l'ajouter à `maquettes/README.md` et `maquettes/index.html`, la montrer à l'utilisateur et attendre son accord avant de coder ; puis cocher la ligne dans `07`.

Écran V1.1 / V1.2 alors que la tâche en cours est V1.0 : **s'arrêter et le signaler**. Les éléments marqués « V1.1 » / « V1.2 » à l'intérieur d'un écran V1.0 ne sont pas codés et leurs entrées de menu sont masquées.

## 2. Lire la maquette

1. Regarder la capture : `maquettes/captures/desktop/<app>-<nom>.png` et, si elle existe, `maquettes/captures/mobile/<app>-<nom>.png` (ouvrir l'image avec l'outil Read).
2. Lire `maquettes/<app>/<nom>.html` : structure, libellés exacts, colonnes, boutons, raccourcis clavier.
3. Extraire **chaque encadré `.note`** : ce sont des règles métier et des critères d'acceptation. Les lister ; chacun devient un test ou une vérification explicite. Ne jamais les afficher.
4. Recouper avec la user story (`docs/02-perimetre-v1.md`) et les champs (`docs/04-modele-de-donnees.md`). **Les documents font foi** : noter tout écart et le signaler à l'utilisateur.
5. Les données des maquettes (noms, montants, taux, dates — jour simulé 19/10/2026) sont fictives : ne pas les coder en dur. Elles peuvent servir de données de démonstration.

## 3. Construire

- Emplacement : `frontend/apps/<gestion|portail>/src/features/<domaine>/…` ; composants génériques dans `frontend/packages/ui`.
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

1. Tests : Vitest pour la logique d'écran, Playwright pour le parcours ; un test par règle `.note` quand c'est testable.
2. Lancer l'application et comparer à la capture à 1440 px (et 390 px si capture mobile). Lister les différences restantes.
3. Aucun texte en dur : rechercher les chaînes françaises dans les `.tsx` modifiés.

## 5. Rendre compte

Liste courte : règles `.note` appliquées (et testées), écarts avec la maquette ou les documents, états ajoutés, puis `📍` l'état de la tâche.

# Plan — Tâche 1.7 : organisation scolaire et écrans des paramètres

Issue #13 · branche `tache/1.7-organisation-parametres` · date : 2026-09-27.

Références : C1–C3, B1–B3, I1 (`02`) ; cahier § 7 ; `04` § 1 (`School.matricule_format`), § 2
(organisation), § 8 (permissions) ; `03` § 4. Maquettes : `gestion/organisation-scolaire`
(fournie), `personnel-comptes` (M3), `roles-permissions` (fournie), `journal-audit` (M6),
`parametres-ecole` (M5). Informations ITIG « en attendant » (`07` § 2) : I1 classes (structure
publique + sections inventées), I2 matricule `ITIG-{AAAA}-{0000}`, I3 calendrier (modèle
secondaire, dates de la maquette). Skills : `backend`, `ecran`, `design`.

Aucune nouvelle dépendance : `radix-ui` (déjà là) donne les onglets et l'interrupteur.

## 1. Serveur — organisation scolaire (app `schools`)

Modèles [T] de `04` § 2 :

- `AcademicYear` : `name` (unique dans l'école), `starts_on` < `ends_on`, `is_current` (une
  seule par école, contrainte partielle), `status` (`open` ; la clôture d'année vient avec la
  délibération, V1.2).
- `Term` : `academic_year`, `kind` (`semester`, `trimester`, `period`, `exam`), `parent`
  (semestre ou trimestre), `order`, `name`, `starts_on`, `ends_on` (vides tant que l'école ne
  les a pas saisis). **`name` vide = nom traduit par l'interface** (« 1re période », « Examens
  du 1er semestre », « Semestre 2 ») d'après le genre et la place, comme les rôles système ;
  l'école peut renommer.
- `Level` : `name` (unique), `cycle`, `order`. `Track` : `name`, `code` (uniques ; code en
  majuscules, sert au matricule `{OPT}`).
- `ClassGroup` : `academic_year`, `level`, `track` (facultatif), `section`, `capacity`,
  `homeroom_teacher` ; nom calculé « 3e Électricité A » ; unique (année, niveau, option,
  section) même sans option.
- `School.matricule_format` (champ de `04` § 1) : à la création d'une école,
  `{CODE}-{AAAA}-{0000}` avec son code en majuscules (migration de données pour les écoles
  existantes).

Services (`apps/schools/organisation.py`), chaque changement noté dans le journal (nouveau
domaine `organisation`) :

- **Année depuis un modèle** (C1) : `secondary` = secondaire RDC (2 semestres, chacun 2 périodes
  + examens), `trimesters` (3 trimestres, chacun 2 périodes + examens), `empty` (découpage
  saisi à la main). En option, **copie des classes d'une autre année** (niveau, option,
  section, capacité ; pas les titulaires, qui changent ; barèmes : 2.5). Première année = année
  en cours ; « définir comme année en cours » ensuite.
- **Découpage** : remplacé d'un seul envoi (`PUT …/terms/`) : noms, dates, périodes et examens
  ajoutés ou retirés ; dates dans l'année, début ≤ fin, période dans son semestre.
- Niveaux, options, classes : créer, modifier, supprimer **seulement s'ils ne servent plus**
  (classe sans élève : vérifié par la base dès que les inscriptions existent, 2.1) ; titulaire =
  une personne active de l'école (sinon refusé : un compte d'une autre école n'est pas visible).
- **Matricule** (C3) : variables `{AAAA}`, `{AA}`, `{0000}` (3 à 6 zéros), `{OPT}` ; obligatoires
  : une année et un numéro (la suite repart à 1 chaque année : sans l'année, deux élèves
  auraient le même). Sans option, `{OPT}` disparaît avec un séparateur voisin. Aperçu « Prochain
  matricule » ; la génération elle-même arrive avec les inscriptions (2.1).

API (`classes.manage`) : `/api/academic-years/` (+ `…/{id}/terms/`, `…/{id}/make-current/`),
`/api/levels/` (+ `reorder/`), `/api/tracks/`, `/api/class-groups/?academic_year=`,
`/api/matricule-format/` (+ `preview/`).

## 2. Serveur — compléments pour les écrans

- `/api/staff/` : filtres `search` (nom, téléphone), `role`, `is_active` (M3, « Utilisateurs avec
  ce rôle »).
- `/api/audit/actors/` (`audit.view`) : les personnes qui apparaissent dans le journal, pour le
  filtre « Personne » (le promoteur lit le journal sans voir `/api/staff/`).
- `/api/staff/` titulaires possibles : liste du personnel actif, pour choisir un titulaire, avec
  `classes.manage` (`/api/class-groups/teachers/`).

## 3. Écrans de la Gestion

Composants ajoutés à `packages/ui` : `Tabs`, `Switch`, `Select` (liste native stylée), `Table`.

- **Paramètres de l'école** (M5, `/app/settings`) : identité (nom court, adresse de
  l'application en lecture seule, nom officiel, fuseau), logo (changer, retirer, aussitôt
  enregistré), couleur (aperçu du texte lisible et teinte voisine proposée, même calcul que le
  serveur), devises (USD, FC, devise principale), « Enregistrer ». Cartes « Reçus » (3.2) et
  « Alertes » (4.2), régime et code EPST (V1.2), adresse / téléphone / e-mail (en-tête des reçus,
  3.2), logo noir et blanc (3.2) : avec leur tâche ; « langue par défaut » : pas dans le modèle.
- **Organisation scolaire** (`/app/organisation`) : choix de l'année, onglets « Année et
  périodes » (année, modèle, découpage et « Modifier les dates »), « Niveaux et options »,
  « Classes » (liste groupée par option et niveau, sections cliquables, titulaire), « Matricule ».
- **Comptes du personnel** (M3, `/app/staff`) : recherche, filtres rôle et état, fiche à droite
  (rôles à cocher, nouveau mot de passe, réinitialiser la double auth., désactiver /
  réactiver, noms et téléphone), « Nouveau compte » (mot de passe provisoire affiché une fois).
- **Rôles et permissions** (`/app/roles`) : liste des rôles, permissions par groupe, renommer,
  nouveau rôle, supprimer un rôle de l'école, utilisateurs du rôle ; double authentification
  **affichée** (déduite des droits, décision de la 1.3) au lieu de l'interrupteur de la maquette.
- **Journal d'audit** (M6, `/app/audit`) : filtres personne, action, domaine, dates, recherche ;
  liste paginée ; détail (avant / après traduits). « Exporter » : 2.4 ; appareil : 3.3.

## 4. Données de démonstration

ITIG : année 2026-2027 en cours (modèle secondaire, dates de la maquette), niveaux 7e EB, 8e EB,
1re–4e, 4 options, ~23 classes, matricule `ITIG-{AAAA}-{0000}`, l'enseignant de démonstration
titulaire d'une classe. Volcans : année, niveaux, 2 options, 4 classes, format différent.

## 5. Tests prévus

- pytest : modèles (contraintes), modèles d'année, copie, découpage (règles de dates), matricule
  (formats refusés, rendu, `{OPT}` absent), services (suppression refusée, titulaire d'une autre
  école), API (chaque point : 403 sans `classes.manage`, isolation beta → 404 / invisible, audit),
  filtres du personnel, `audit/actors`, `make demo`.
- Vitest : chaque écran (affichage, droits, erreurs traduites, formulaires) ; couleur (mêmes
  vecteurs que le serveur) ; noms des périodes.
- Playwright : directeur crée une classe et change le matricule ; ajoute un compte (mot de
  passe provisoire) ; crée un rôle ; lit ces actions au journal ; change la couleur.

## 6. Décisions (à valider par la fusion)

Noms des périodes traduits ; modèles d'année ; règles du matricule et format par défaut ; copie
sans titulaires ; suppression seulement si inutilisé ; titulaire = personnel actif ; domaine
d'audit `organisation` ; écarts aux maquettes (§ 3). Question ouverte Q12 : découpage officiel du
primaire (pas de modèle « primaire » tant qu'il n'est pas confirmé).

## Risques

Taille de la tâche (5 écrans) ; nombre de clés de traduction ; pagination (50 par page) : les
écrans lisent la page demandée, jamais « tout ».

# Tâche 8.3.6 — Fiches de cotes (issue #268)

**But** : trois documents imprimables par classe, avec les options d'impression de 8.3.4 : fiche d'un cours (élèves × périodes/examens/totaux + moyenne, plus haute, plus basse, nombre sous la moitié, signature de l'enseignant), fiche vierge à remplir à la main, tableau de la classe (élèves × cours pour une colonne choisie, total, %, place ; sert à la délibération 8.4).

**Décisions (regard senior)**
- Un seul point d'API `GET /api/class-groups/<id>/grade-sheet/?kind=course|blank|class` ; on réutilise `class_report` (une lecture des notes de la classe, rien de stocké, aucune table).
- Fiche d'un cours et vierge : `grades.enter` (ses cours / sa classe de titulaire), `enter_any` ou `validate` ; tableau de la classe : `enter_any`, `validate` ou titulaire de la classe.
- Notes non validées : le document est autorisé (outil de travail) mais porte la mention « provisoire » (`missing_sheets`).
- Colonnes au choix (`matricule`, `totals`) ; papier, sens (tableau de classe : paysage par défaut). Audit : une ligne par PDF.

**Hors périmètre** : Excel, délibération (8.4), conduite (8.5.1).

**Critères** : stats exactes (moyenne au dixième, hauteur/basse, < moitié) ; case incomplète vide ; 403 pour un cours qu'on ne note pas ; autre école 404 ; écran « Fiches de cotes » (maquette `notes-fiches`) à 390 et 1440 px.

**Tests** : stats et incomplets ; permissions (enseignant d'un autre cours, caissier) ; isolation ; audit du PDF ; options (`@page`, colonnes).

**Documents** : 05, 06, reference.md, A-FAIRE § 11, 07 § 1, maquettes/README, skill design (impression).

**Risques** : en-têtes de cours dans le tableau de classe (60 cours) → à tester sur PDF.

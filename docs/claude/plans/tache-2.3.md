# Tâche 2.3 — Import Excel des élèves (D1)

Décisions de l'utilisateur (2026-09-27) : dépendance **openpyxl** (lit et écrit les .xlsx, resservira en 2.4) ; fratries **regroupées dans le fichier** (même nom de tuteur ET même téléphone), jamais rattachées à une famille déjà dans l'école.

- Serveur, `apps/students/imports.py` : lecture .xlsx (openpyxl, lecture seule) ou .csv (stdlib) ; correspondance des colonnes devinée par leurs titres (NOM, POSTNOM, PRENOM, SEXE, DATE NAISS., CLASSE, NOM DU PARENT, TEL…) ; rapprochement des classes (« 3E ELEC A » → « 3e Électricité A », niveau + code ou nom de l'option + section) ; vérification ligne par ligne → prête / avertissement (importée) / erreur (pas importée).
- Modèle `StudentImport` [T] : année, nom du fichier, lignes lues (JSON, vidées après l'import : le fichier n'est pas gardé), `mapping`, `class_mapping`, `status` (analysed → importing → done / failed), `report`, `created_count`.
- Import en tâche Celery (`tasks.py`) : une transaction, créations groupées (`bulk_create`), matricules de la séquence de l'année (numéros pris sautés, ou matricule du fichier gardé), une ligne de journal par élève importé (historique de la fiche).
- Règles : erreurs = nom, sexe ou classe manquants / inconnus, date invalide, matricule déjà pris, élève déjà dans l'école (même nom, prénom, naissance : protège d'un fichier importé deux fois) ; avertissements = doublon dans le fichier, téléphone illisible (tuteur gardé sans téléphone).
- API `/api/student-imports/` : `POST` (fichier + année → analyse), `GET`, `PATCH` (colonnes, classes → nouvelle analyse), `POST …/confirm/` (202), `GET …/report/` (rapport .xlsx), `GET …/template/` (modèle .xlsx) ; droit `students.import`.
- Écran `/app/students/import` (maquette `eleves-import`) : étapes Fichier, Colonnes, Vérification, Import ; bouton « Importer » dans la liste des élèves ; progression par interrogation de l'API.
- Fichier fictif réaliste : commande `make demo-excel` → `eleves-fictifs.xlsx` (~800 élèves, quelques erreurs glissées).
- Tests : isolation (import d'une autre école : 404, classe d'une autre école refusée), 403 sans `students.import`, analyse (classes, dates, doublons, fratries), import complet sans doublon ni matricule en double, journal ; front : parcours de l'écran.
- Risques : noms de classes très variés (→ association à la main) ; fichiers .xls (→ message « enregistrez en .xlsx »).

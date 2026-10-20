# Tâche EDT.1a — Grille horaire et salles

**But** : l'école règle ses heures de cours (durée, début, heures par jour, récréations, deux vacations), ses salles et ateliers, la grille et la salle habituelle de chaque classe ; elle voit tout de suite « heures de cours / places de la grille » par classe. Spec : `docs/specs/emploi-du-temps.md` §§ 3, 13.

**Hors périmètre** : champs de placement des cours, profils des enseignants, règles et diagnostic (EDT.1b) ; horaire, éditeur (EDT.2) ; droits `timetable.view`, `.publish`, `.record_exceptions` (ajoutés avec leur écran, EDT.4 et EDT.6 : un droit qui ne sert à rien embrouille l'écran des rôles).

**Critères d'acceptation**
- Nouvelle app `timetable` : `TimeGrid`, `TimeSlot`, `Room` [T] ; `ClassGroup.time_grid`, `ClassGroup.home_room` (facultatifs, vide = grille par défaut) ; module `timetable` (dépend de `academics`, `resolve` rendu transitif), droit `timetable.manage` (préfet et DE ; rôles qui ont `courses.configure` aussi) ; écoles qui ont `academics` reçoivent le module.
- Grille enregistrée d'un bloc ; une heure garde son identifiant (jour + numéro) d'un envoi à l'autre, pour l'horaire d'EDT.2 ; cases contiguës, récréation entre deux heures, une seule grille par défaut. Grille proposée créée par le serveur (Q16 : 50 min, 7 h 30, 7 h × 5 + 4 le samedi, récréations 15 et 10 min = 39 places).
- Salles : ajout, modification, retrait (jamais supprimées : l'horaire s'y référera). Règles générales dans `School.settings["timetable"]` (4 réglages, défauts de la spec).
- Écrans « Grille horaire » (réglages, semaine, classes et capacité, règles) et « Salles », maquettes d'abord, 390 et 1440 px.

**Tests obligatoires** : isolation (grille, salle, classe d'une autre école : 404, jamais listées ; salle ou grille d'une autre école refusée sur une classe), 403 sans `timetable.manage` et sans le module, journal des changements, règles de la grille (chevauchement, récréation en bout de journée, défaut unique), identifiants gardés, capacité exacte (cours barrés et heures vides), `resolve` transitif ; Vitest du calcul des heures ; `make demo` dans `test_demo.py`.

**Documents** : `04`, `03` (journal), `05`, `06`, `07` §§ 1 et 4, `reference.md`, `A-FAIRE.md` § 11, `maquettes/README.md`, `CLAUDE.md` (liste des apps).

**Risques** : pas de pagination (au plus quelques grilles, ~100 salles, ~60 classes : une requête chacune, plafond côté serveur) ; capacité en une requête annotée.

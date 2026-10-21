# Tâche EDT.1b — Cours, enseignants et contrôles avant le calcul

**But** : le DE dit comment placer chaque cours (séances, au plus N h par jour, salle ou type de salle exigé, récréation traversable, moment), règle la disponibilité de chaque enseignant (charge maximale, au plus par jour, absences) et voit tout de suite ce qui empêchera l'horaire (contrôles 1 à 5 de la spec § 6). Spec : `docs/specs/emploi-du-temps.md` §§ 4, 6.

**Découpage (2026-10-21)** : trop gros pour une PR (trois écrans, deux modèles, sept contrôles). `TimetableRule`, éditeur des règles, contrôles 6 et 7, groupes parallèles et cours communs → **EDT.1c** (#371).

**Hors périmètre** : règles (EDT.1c) ; bouton « Calculer » (EDT.3) ; horaire (EDT.2).

**Critères d'acceptation**
- `Course` : `lesson_pattern`, `max_per_day`, `room`, `room_kind`, `can_span_break` (vide = oui pour un atelier), `preferred_part`, dans l'objet `placement` de chaque cours de la grille (même envoi d'un bloc) ; absent = gardé ; présent sans `timetable.manage` ou sans le module : 403 ; séances = heures ; salle de l'école en service ; copiés avec la grille.
- `TeacherTimetableProfile` [T] (compte du personnel actif) : `max_week_hours`, `max_day_hours`, `unavailable` (jours entiers ou plages horaires : valables pour toutes les grilles, deux vacations comprises) ; `GET /api/timetable/teachers/`, `PUT …/teachers/<id>/` ; journal.
- `checks.py`, calcul pur en ~7 requêtes quelle que soit la taille : classe surchargée ; enseignant au-delà de son maximum, de ses heures libres, de ce que ses jours permettent ; cours impossible à étaler, séance trop longue ; salle ou type de salle demandé au-delà de ses heures ; cours sans enseignant ou sans heures, enseignant parti. Chaque ligne : code, rouge / orange, objet, chiffres. `GET /api/timetable/checks/`.
- Écrans : vue « Emploi du temps » de la grille des cours ; « Charges des enseignants » : maximum et disponibilités (fenêtre avec la semaine de la grille) ; nouvel écran « Contrôles avant le calcul ». Maquettes d'abord, 390 et 1440 px.

**Tests** : isolation (profil, salle et enseignant d'une autre école, contrôles), 403 (placement et profils sans droit, sans module), journal, un cas par contrôle, séances ≠ heures refusées ; Vitest (séances proposées, absences) ; `make demo` dans `test_demo.py`.

**Documents** : `04`, `03`, `05` (découpage), `06`, `07` §§ 1 et 4, spec, `reference.md`, `A-FAIRE.md` § 11, `maquettes/README.md`.

**Risques** : un atelier de 6 h d'un seul bloc et la règle « 2 h du même cours par jour » de l'école → la règle de l'école ne descend jamais sous la plus longue séance (sinon chaque atelier serait rouge) ; contrôles en mémoire, sans N+1.

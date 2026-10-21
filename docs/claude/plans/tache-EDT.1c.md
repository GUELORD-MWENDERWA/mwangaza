# Tâche EDT.1c — Règles de l'emploi du temps et leurs contrôles

**But** : le DE écrit les consignes de l'horaire (liste fermée de règles), les voit en phrases sur l'écran renommé « Règles et contrôles », et le diagnostic dit tout de suite ce qui se contredit (contrôles 6 et 7).

**Hors périmètre** : calcul (EDT.3), horaire et vrais verrous `TimetableEntry` (EDT.2), consignes en phrases par l'IA (IA.2a).

**Critères d'acceptation**
- `TimetableRule` [T] : 9 kinds en lignes (`fixed_lesson`, `course_not_slot`, `course_part_of_day`, `parallel_courses`, `joint_courses`, `room_unavailable`, `spread_over_week`, `teacher_compact`, `teacher_free_day`), `params` vérifiés par un schéma propre au kind (cours, enseignant, salle de l'école et de l'année), force permise par kind, poids 1–10, au plus 500 règles.
- Regard senior : `max_course_per_day`, `teacher_max_per_day`, `teacher_max_week`, `class_no_gap` restent où l'école les règle déjà (règles générales, cours, disponibilités) — pas de seconde copie ; `stability` viendra avec le calcul (EDT.3).
- Un cours n'est que dans une règle de regroupement (parallèles ou communs) : groupes disjoints, comptés une fois dans les contrôles 1 (classe) et 2 (enseignant).
- Contrôle 6 : deux verrous qui se chevauchent (même classe hors parallèles, même enseignant hors cours communs, même salle). Contrôle 7 : verrou hors de la grille, sur une récréation interdite, qui n'est pas une séance du cours, sur une absence, sur une salle fermée, sur un moment interdit ; parallèles au même enseignant ; heures différentes dans un groupe ; cours communs à enseignants différents ; règle sans objet (orange).
- API `timetable/constraints/` (liste, ajout, modification, suppression, journal) + `constraints/choices/` ; écran : carte « Règles », fenêtre d'ajout, bouton « Modifier la règle » sur les lignes 6 et 7.
- `make demo` : ITIG, atelier de la 2HT Électricité A le lundi de la 2e à la 7e heure, et quelques souhaits.

**Tests** : isolation (lire, modifier, supprimer, viser le cours d'une autre école), 403, schéma refusé, groupes disjoints, contrôles 6 et 7, comptage une fois ; scénario `test_demo`.

**Documents** : spec §§ 5–6, `04`, `03` journal, `reference.md`, `A-FAIRE.md` § 11, `07` § 1 et 4, `maquettes/README.md`, `05`, `06`.

**Risques** : références en JSON (cours supprimé → règle sans objet), matin = avant 12 h (deux vacations), maquette à dessiner avant le code.

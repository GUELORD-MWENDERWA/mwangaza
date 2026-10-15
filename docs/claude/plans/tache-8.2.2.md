# Tâche 8.2.2 — Contrôle des notes

**But** : une feuille (cours × période) a un état — brouillon, envoyée, validée —, une date limite de saisie par période, et le directeur des études la valide (`grades.validate`, double authentification).

**Hors périmètre** : hors ligne (8.2.3), bulletin (8.3). Notification du directeur à l'envoi : écartée (une écriture de plus par envoi ; l'écran « À valider » suffit).

**Critères d'acceptation**
- `GradeSheet` (cours, période, état, envoyée/validée par et le, `reopened`) créée au premier enregistrement ; `GradeDeadline` (période, date) posée par `grades.validate`.
- Brouillon : saisie libre jusqu'à la date limite (passée : 409 `deadline_passed`, sauf feuille rouverte ou `grades.validate`). Envoi : feuille complète (400 `incomplete_sheet`).
- Envoyée : modifier demande un motif (400 `reason_required`), gardé au journal avec les cases. Validée : fermée (409 `sheet_validated`).
- Valider ; rouvrir / renvoyer avec motif (`grades.validate`) : retour en brouillon, date limite levée pour cette feuille.
- Maximum d'un cours déjà noté : changé seulement par qui a `grades.validate` (409 `max_graded`).
- Historique de la feuille (journal) dans la feuille ; `GET /api/grading/validation/` : envoyées à valider + dates limites. Écran « À valider » (nouvelle maquette) et bandeau d'état dans la saisie.
- `grades.validate` : directeur des études, double authentification (`TOTP_PERMISSIONS`), migration pour les rôles ayant `courses.configure` sauf… les mêmes que `enter_any`.

**Tests obligatoires** : isolation, 403 sans droit, machine d'états, date limite, motif, maximum noté, journal.

**Documents** : 03, 04, 05, 06, reference.md, A-FAIRE § 11, 07, maquettes/README.

**Risques** : verrou du cours déjà pris dans `save_sheet` ; ne pas créer de ligne `GradeSheet` pour un envoi sans changement.

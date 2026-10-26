# Plan IA.2b — Analyse et propositions (branche tache/IA.2b-analyse-propositions, issue #395)

**But** : bouton « Demander conseil » : l'IA (usage `timetable_review`) reçoit les chiffres calculés par le code, explique en mots simples et propose des actions d'une liste fermée ; chacune s'applique d'un clic par les services normaux, le solveur vérifie ensuite.
**Hors périmètre** : déplacer une heure, retirer un verrou d'un horaire calculé (l'éditeur le fait ; aucune action ne touche aux heures verrouillées), nouveau modèle.

**Critères** : `timetable/review.py` (dossier : contrôles ou conflits du brouillon, règles, cours des classes en cause, codes courts ; schéma de sortie ; chaque action revérifiée) ; API `POST review/` (`timetable` facultatif), `GET review/<id>/`, `POST …/apply/` (clé `kind:id`), `POST …/finish/` ; fenêtre dans Contrôles et dans l'éditeur d'un brouillon ; maquette `conseil-emploi-du-temps`.
**Actions** : `soften_rule`, `pause_rule` (verrou compris), `set_pattern` (somme = heures du cours), `need_teacher` (conseil seul).

**Tests** : action invalide / autre école écartée, application = règle ou cours changé + journal, une action une seule fois, droits 403, isolation 404.
**Documents** : 03, 05, 06, 07, maquettes/README, reference.md, A-FAIRE.md.
**Regard senior** : un appel par clic ; dossier plafonné (60 lignes de contrôle, 80 cours) ; pas de réservation de crédit en plus ; `proposals` relit l'état à chaque lecture (quelques requêtes indexées).

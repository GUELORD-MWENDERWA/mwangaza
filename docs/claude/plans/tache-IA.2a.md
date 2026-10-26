# Plan IA.2a — Consignes en phrases → règles (branche tache/IA.2a-consignes-en-regles, issue #390)

**But** : le directeur des études écrit ses consignes ; l'IA (usage `timetable_constraints`, IA.1.1) les traduit en règles de la liste fermée (`constraints.SPECS`) ; il coche, corrige, enregistre. Rien n'est enregistré sans lui.
**Hors périmètre** : analyse et propositions (IA.2b), nouveau kind de règle, indisponibilité d'enseignant par plage (reste dans les disponibilités EDT.1b).

**Critères** : `timetable/assistant.py` (consignes fixes + noms/identifiants de l'école seulement, schéma de sortie, vérification de chaque règle par `constraints.clean` : une proposition invalide devient « pas compris » avec la raison) ; API `POST constraints/assist/` (clic, `request_id` du client), `GET constraints/assist/<id>/` (état + propositions), `POST …/keep/` (crée les règles cochées, `source=ai`, `text`, journal, puis `settle(kept)`) et `…/abandon/` ; bouton « Dire mes consignes » sur la carte Règles → panneau (phrase, propositions cochables avec la phrase lisible de `describe`, enregistrer). « Ne vient pas le vendredi » = `teacher_free_day` obligatoire (pas de nouveau kind).

**Tests** : isolation (appel d'une autre école introuvable, ids d'une autre école refusés), droits (403 sans `timetable.manage` / sans `ai.use`), refus des verrous IA sans appel, proposition invalide → « pas compris », enregistrement = règles `source=ai` + journal + appel « gardé », deux enregistrements = une fois.

**Documents** : 03 (journal), 04, 05, 06, 07 § 1 et § 4, maquettes/README, reference.md, A-FAIRE.md.

**Regard senior** : un appel par clic, résultat gardé 24 h au plus ; contexte limité aux cours enseignés de l'année (noms, ids) ; pas de réservation de crédit supplémentaire ; interrogation de l'état par le client toutes les 2 s (une lecture indexée).

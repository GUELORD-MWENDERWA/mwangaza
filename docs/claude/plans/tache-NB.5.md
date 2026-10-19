# Tâche NB.5 — Conseil de délibération par période et en fin d'année, avec PV

**But** : le conseil (direction des études, titulaire, enseignants de la classe) délibère à chaque période, chaque semestre et en fin d'année ; lui seul voit le tableau ; présents, président et observations notés ; proclamation figée ; procès-verbal imprimable.

**Hors périmètre** : remise du bulletin de période au parent (8.4.6 et 8.8) ; seconde session (NB.6) ; décision par élève à la période (le conseil confirme les résultats, il ne décide pas de passage).

**Critères d'acceptation**
- `Deliberation` gagne `term` (vide = fin d'année ; une par classe et session), `council` (présents, président) et `remarks` ; le figé garde le conseil. Les lecteurs de la fin d'année (bulletin, situations, passage, reprise) ne lisent que `term` vide.
- Période ou semestre : tableau (pourcentage, place, conduite, application), proclamation refusée tant que le titulaire n'a pas dit « bulletins prêts » (chaque période et examen du semestre) ; conduite figée avec, élèves sans conduite signalés.
- Secret : lecture pour `grades.validate`, le titulaire et les enseignants de la classe ; tout autre compte 403 ; écriture : `grades.validate` seulement.
- PV en PDF et aperçu (en-tête des documents) après proclamation : session, date, président, présents et absents, chiffres, décisions et écarts motivés (fin d'année), conduite, observations, signatures.
- Maquettes d'abord : `gestion/deliberation.html` (session, conseil, PV) et `gestion/deliberation-pv.html`.

**Tests obligatoires** : isolation (tableau et PV d'une autre école : 404) ; 403 non-membre, secrétaire, et écriture par un enseignant membre ; proclamation de période refusée sans « bulletins prêts », puis figée sans toucher la fin d'année ; conseil (présents hors membres refusés, journal) ; PV.

**Documents** : `04` (Deliberation), `03` journal, `reference.md` + `A-FAIRE.md` § 11 (API, PV), `07` § 1 et § 4, `maquettes/README.md`, `05`, `06`.

**Risques** : OneToOne → ForeignKey (migration sans perte, `nulls_distinct=False`) ; requêtes `deliberation__class_group` de `situations.py`, `promotion.py`, `prior_results.py`, `demo.py` à filtrer sur `term` vide.

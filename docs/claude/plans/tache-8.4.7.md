# Tâche 8.4.7 — Reprise des résultats de l'année précédente (issue #300)

**But** : une école dont les élèves n'ont aucune note dans Mwangaza pour une année (année passée créée à l'arrivée, ou tenue sur papier) donne seulement la **décision finale et le pourcentage** : saisis dans la délibération, ou importés d'un fichier Excel pour toute l'école. Comme `origin=prior` pour les paiements, ce n'est pas un circuit à part : la délibération garde ces résultats, la classe se proclame comme les autres, et situations (8.4.4), bulletin (8.4.3) et passage de classe (8.4.5) les lisent sans rien de plus.

**Regard senior** : pas de modèle `PriorResult` à part (il faudrait que 8.4.4, 8.4.5 et le Portail lisent deux sources) ; un champ `DeliberationDecision.prior_percent`. Le pourcentage repris n'est accepté que pour un élève **sans aucune note** cette année : jamais pour remplacer un pourcentage calculé (sinon on falsifie un résultat). Import sans table ni tâche de fond (aperçu, puis même fichier renvoyé, comme 4.19) ; « a des notes » = une requête sur `Grade`, pas le bulletin de chaque classe.

**Hors périmètre** : reprise des notes d'une période (déjà possible : saisie des totaux, 8.4.0) ; proclamation automatique à l'import (le préfet proclame chaque classe) ; passage de classe (8.4.5).

**Critères d'acceptation** : délibération → élève sans note : champ « % repris » à côté de la décision, enregistré, figé à la proclamation ; écran « Reprise des résultats » : année, date de délibération, modèle Excel garni (élèves sans note des classes non proclamées), aperçu (prêtes, erreurs : matricule inconnu, décision illisible, pourcentage hors 0–100, élève qui a des notes, classe proclamée, élève en double), enregistrement ; date posée aux classes qui n'en ont pas ; fichier envoyé deux fois = rien de changé (journal seulement pour ce qui change).

**Tests obligatoires** : isolation (matricule d'une autre école = inconnu) ; permission `grades.validate` (403) ; refus du pourcentage d'un élève noté ; classe proclamée refusée ; journal `deliberation.decided` ; fichier renvoyé sans effet ; situation lit le pourcentage repris.

**Documents** : `04` (champ, règle), `03` journal des décisions, `05`, `06`, `07` § 1 et § 4, `maquettes/README.md` (+ `gestion/reprise-resultats.html`, ajout à `gestion/deliberation.html`), `reference.md` et `A-FAIRE.md` § 11 (écran, API, `make demo` : 8EB C sans notes, résultats repris pour la moitié).

**Risques** : `make demo` (classe sans notes : vérifier bulletins, situations) ; lignes figées (`_frozen`) ; écran de délibération déjà chargé.

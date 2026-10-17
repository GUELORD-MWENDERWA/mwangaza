# Tâche 8.4.3 — Bulletin complété (#296)

**But** : le bas du bulletin se remplit d'après la dernière proclamation : mention gardée (autres biffées), date, cours à repêcher ; colonne du repêchage avec % et enseignant.

**Hors périmètre** : situations (8.4.4), passage de classe (8.4.5), frais (8.4.6). Nom, signature et cachet du chef : déjà faits (`core/_signer.html`).

**Critères** : classe proclamée → bas rempli ; pas proclamée ou élève ajouté après → vierge ; brouillon rouvert ne change pas le bulletin tant qu'il n'est pas reproclamé.

**Tests** : lecture de la version figée (avant/après réouverture), isolation entre écoles.

**Docs** : 05, 06, 04, 07, reference.md, maquettes/README.md.

**Risques** : passage `resit_courses` absent des anciennes versions (`row.get`) ; pas de requête par élève (cache sur le rapport).

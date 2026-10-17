# Tâche 8.4.2 — Délibération d'une classe (#295)

**But** : tableau de la classe avec la décision proposée (règles de 8.4.1) et la décision prise (admis, doublant, repêchage, réorienté, exclu, abandon) ; écart signalé avec motif obligatoire ; date de délibération ; proclamation qui fige les résultats ; correction ensuite = nouvelle version avec motif.

**Choix (regard senior)** : `Deliberation` (une par classe : date, statut, version) + `DeliberationDecision` (une ligne par élève décidé : proposition vue, décision, motif) + `DeliberationSnapshot` (JSON figé à chaque proclamation : seul lu par bulletin 8.4.3 et situations 8.4.4). Droit : `grades.validate` (pas de nouveau droit ni de migration de rôles). Conduite et application : déjà corrigeables avec motif (écrans Conduite et Application) ; le tableau y renvoie, rien n'est dupliqué. Proposition recalculée à la lecture (aucune écriture).

**Hors périmètre** : bulletin complété (8.4.3), statistiques imprimables (8.4.4), passage de classe (8.4.5), notification des parents.

**Critères d'acceptation** : décisions enregistrées, « appliquer les propositions » aux élèves sans décision ; proclamer exige date, une décision par élève et un motif pour chaque écart ; classe proclamée = lecture seule ; rouvrir exige un motif, la proclamation suivante crée la version n+1, l'ancienne reste.

**Tests obligatoires** : écart sans motif refusé, proclamation figée (notes changées ensuite : le figé ne bouge pas), rouvrir/version, droit (403), journal, isolation entre écoles.

**Documents** : `04`, `03`, `05`, `06`, `07` § 1, `reference.md`, `maquettes/README.md`, `A-FAIRE.md` § 11.

**Risques** : élève hors classe (autre classe) ; élève ajouté après proclamation (sans décision, signalé).

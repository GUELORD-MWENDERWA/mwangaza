# Tâche 2.6.2 — Échéancier particulier (E4, M12)

**Serveur** (`finance`)
- `StudentCharge.Status.REPLACED` (« remplacé ») ; migration 0003 (choix seulement).
- `services.reschedule_charges(enrollment, fee_type, installments, reason, parent_signed, actor)` : inscription active ; motif obligatoire ; remplace les frais dus encore actifs de ce type (3.1 : sauf ceux déjà payés, même en partie) par des `StudentCharge` `source=custom`, même devise ; somme des versements = reste à réorganiser (`installments_total_mismatch`) ; les anciens passent « remplacés », jamais effacés. Audit `finance.charges_rescheduled` sur l'inscription (visible dans l'historique de l'élève), avec motif, engagement signé, avant / après.
- `sync_charges` : un type de frais sous échéancier particulier n'est plus touché pour cet élève (ni barème modifié, ni changement de classe).
- API `POST /api/student-charges/reschedule/`, droit `finance.grant_discount` (note de la maquette) ; renvoie les frais dus de l'inscription.

**Écran** (Gestion)
- Onglet « Finances » de la fiche : carte « Ce qui est dû » (frais, échéance, montant, état ; soldes et paiements en 2.7 / 3.1) avec le lien « Échéancier particulier ».
- `students/:id/finances/schedule` : maquette `eleve-echeancier` (aujourd'hui, frais à réorganiser, motif, engagement, dates libres / mensuel, total = reste).

**Tests** : isolation (inscription d'une autre école), 403 sans le droit, somme ≠ reste, motif vide, anciens « remplacés » + nouveaux `custom`, audit, barème modifié sans effet ; Vitest : découpage mensuel et envoi.

**Risque** : un changement de classe ne recalcule plus un frais sous échéancier — à valider.

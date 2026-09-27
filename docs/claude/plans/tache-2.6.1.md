# Tâche 2.6.1 — Frais dus des élèves (`StudentCharge`)

Découpage validé le 2026-09-27 : 2.6.1 (frais dus + actions de la fiche), 2.6.2 (échéancier particulier E4), puis 2.5.2.

- **Modèle** `StudentCharge` [T] (finance) : `enrollment`, `fee_type`, `label`, `amount_minor`, `currency`, `due_on`, `source` (`rule` / `custom`), `installment_template` (`SET_NULL`), `status` (`active` / `removed`) ; une seule ligne par inscription et par tranche. Jamais supprimé (`04` : aucune suppression physique) : un frais qui ne s'applique plus passe `removed`, et revient `active` si le barème s'applique de nouveau.
- **Service** `sync_charges(enrollments, fee_type=None)` : par type de frais, barème le plus précis (classe > niveau > option > école), une ligne par tranche ; crée, met à jour, retire, réactive ; seulement les inscriptions `active` ; en masse (`bulk_create` / `bulk_update`, pas de N+1). Frais déjà payés intouchables : branché avec les paiements (3.1), noté dans `05`.
- **Appelé par** : `enroll`, import Excel, `update_enrollment` (classe changée ou retour en `active`), barème créé / modifié / supprimé (inscriptions actives de l'année, ce type de frais), `make demo`.
- **Audit** : pas d'entrée par frais (des milliers) ; l'action qui les cause est déjà notée ; le barème ajoute `students_updated`.
- **API** : `GET /api/student-charges/?enrollment=` (lecture ; droits `finance.*` utiles), paginée.
- **Fiche élève**, carte « Inscription » (`students.edit`) : « Changer de classe », « Enregistrer un départ » (motif, date), « Annuler le départ », « Inscrire pour <année> » (élève connu, pas inscrit cette année).
- **Tests** : barème le plus précis et devises ; changement de classe ; barème modifié puis supprimé (retiré, puis réactivé) ; départ intact ; import ; isolation et 403 de l'API ; un test d'écran (départ).
- **Risque** : barème « toute l'école » modifié = ~1 200 inscriptions recalculées dans la requête (en masse : moins d'une seconde).

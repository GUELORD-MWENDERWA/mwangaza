# Tâche 4.1.2 — Situation financière imprimable (G2) et colonnes de paiement de la liste des élèves

**Serveur (finance)**
- `finance/statements.py` : pour une ou plusieurs inscriptions, frais dus (`charges_by_enrollment`, même calcul que l'onglet Finances : réductions déduites, paiements annulés exclus), solde par devise (`balance`), paiements reçus et annulés, tuteur principal ; 4 requêtes quel que soit le nombre d'élèves.
- `GET /api/student-charges/statement/?enrollment=…&enrollment=…&output=html|pdf&upcoming&payments&hide_paid` (droit `CHARGES_READ`, 100 élèves au plus, une page par élève) ; gabarit `finance/statement.html` ; PDF noté au journal (`finance.statement_printed`), aperçu HTML non.
- QR : `/v/s/<jeton>` signé par le serveur (`django.core.signing`, sel propre à l'école) : école, date, élève en initiales, classe, retard et reste par devise tels qu'imprimés ; jeton modifié ou d'une autre école : « inconnu » (404).

**Serveur (élèves)** : liste `/api/students/` → champ `finance` (retard par devise, situation à jour / partiel / en retard) avec un droit `CHARGES_READ`, sinon `null` ; calcul pour la page seulement (2 requêtes) ; filtre `payment=up_to_date|partial|overdue` (403 sans le droit).

**Front** : `features/students/StatementPage.tsx` (routes `students/:id/statement` et `unpaid/statements?enrollment=…`), bouton « Situation financière » dans l'onglet Finances ; cases à cocher et « Imprimer les situations sélectionnées » dans les Impayés ; colonnes « Échu non payé », « Paiements » et filtre « Paiement » dans la liste des élèves.

**Tests** : isolation (inscription d'une autre école → 400, jeton d'une autre école → 404), 403 sans droit (document, filtre, colonnes absentes), montants par devise jamais additionnés avec réduction et paiement annulé, audit du PDF ; liste : filtre et colonnes ; Vitest : sélection des impayés → lien.

**Décisions** : échéances à venir listées une par une (pas de regroupement « novembre → juin ») ; pied « Signature et cachet » (pas « Le comptable » : tout rôle peut imprimer).
**Risque** : URL longue pour 100 élèves (≈ 4 ko, sous les limites).

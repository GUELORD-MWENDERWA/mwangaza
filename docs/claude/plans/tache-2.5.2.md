# Tâche 2.5.2 — Réductions (E3, maquette `eleve-reduction`)

**Serveur** (`finance`) : modèle `Discount` [T] (`enrollment`, `fee_type` vide = tous les frais, `kind`, `percent` 1–100 ou `amount_minor` + `currency`, `reason_code`, `reason` obligatoire, `approved_by`, retrait : `revoked_at`, `revoked_by`, `revoke_reason` ; contraintes en base). Jamais effacé.
- `grant_discount` / `revoke_discount` (droit `finance.grant_discount`, audit `finance.discount_granted` / `finance.discount_revoked` sur l'inscription → historique de l'élève).
- Effet **calculé, pas stocké** : `discount_shares(charges, discounts)` par frais (et devise) — % arrondi demi supérieur, montants cumulés plafonnés au frais, réparti au prorata des échéances actives (reste le plus fort, l'écart sur les dernières). Suit donc tout seul changement de classe, barème modifié, échéancier.
- API : `GET/POST /api/discounts/`, `POST /api/discounts/{id}/revoke/` ; `discount_minor` ajouté à `GET /api/student-charges/`.
- Refus : élève pas inscrit / parti, rien dû pour ce frais, montant sans frais précis ou > frais, motif vide.

**Front** : dialogue « Accorder une réduction » depuis l'onglet Finances (modèles = motif, frais concernés, % / montant, valeur, motif, tableau « Effet sur ce que doit l'élève ») ; liste des réductions actives avec « Retirer » (motif) ; colonnes Réduction / Après dans « Ce qui est dû ». Calcul du tableau par `prorate` / `percentOf` de `@mwangaza/money` (mêmes règles, servira aussi hors-ligne).

**Tests** : répartition (%, montant, arrondi, cumul plafonné, tous les frais en deux devises), suit l'échéancier, refus, retrait, audit, isolation, 403 ; `prorate` TS ; dialogue : tableau d'effet, envoi en entiers, rien sans motif, bouton masqué sans droit.

**Écarts** : modèles sans valeur par défaut (valeurs propres à l'école, I6) ; colonnes « Déjà payé » / crédit → 3.1 (pas de paiements avant).

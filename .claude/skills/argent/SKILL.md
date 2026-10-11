---
name: argent
description: Règles de l'argent dans Mwangaza — montants en entiers (centimes USD, francs CDF), devises, taux de change, conversion et arrondi, répartition d'un paiement sur les échéances, réductions, soldes, surpaiement et crédit, annulation, montant en lettres, formats d'affichage. À utiliser pour tout code ou test qui stocke, calcule, convertit, répartit ou affiche un montant (finance, caisse, reçus, impayés, tableau de bord, portail, paie).
---

# Argent

Références : `docs/03-architecture-technique.md` § 6, `docs/04-modele-de-donnees.md` § 4, `docs/02-perimetre-v1.md` E et F, note de `maquettes/gestion/caisse-encaissement.html`.

## Stockage

- Montant = **entier** dans la plus petite unité + code devise ISO : `amount_minor` + `currency`.
  - `USD` : 2 décimales → `150,00 $` = `15000`.
  - `CDF` : 0 décimale utile → `30 000 FC` = `30000`. Code `CDF`, affiché « FC ».
- **Jamais de `float`** : ni `FloatField`, ni `float()`, ni `parseFloat` / `Number()` sur une saisie de montant. `Decimal` uniquement pour les taux.
- Python : `apps.core.money.Money(amount_minor, currency)` immuable, `Currency` (`USD`, `CDF`) ; refuse `float`, `bool` et `Decimal` comme montant ; opérations seulement entre montants de même devise (`CurrencyMismatchError`) ; `Money.from_major("150.25", "USD")` refuse les décimales en trop ; `money.convert("CDF", rate)` applique Q4 (taux `Decimal` USD → CDF).
- Front : `frontend/packages/money` — parse la saisie (`"150,00"` → `15000`), formate, additionne. Les écrans ne font aucun calcul de montant à la main.

## Taux et conversion

- `ExchangeRate(school, academic_year, USD → CDF, rate)` : taux de l'année, fixe, saisi par le comptable ; une correction ajoute une ligne (historique), le taux en vigueur est la dernière. La devise d'un frais est celle de son barème (`FeeRule.currency`).
- Chaque paiement enregistre `rate_used` (taux en vigueur à l'encaissement ; une correction ultérieure ne le change pas) ; l'allocation est exprimée dans la devise de la charge.
- Arrondi : **demi supérieur** à l'unité de la devise cible (centime USD, franc CDF), calculé en `Decimal`, puis converti en entier.
- Sens du taux (décision Q4) : toujours USD → CDF, tel que saisi. USD → CDF : multiplier ; CDF → USD : **diviser** en `Decimal` par le taux (jamais multiplier par `1/rate`).

## Répartition d'un paiement (F2)

1. Charges non soldées de l'inscription, triées par `due_on` puis `fee_type` ; par défaut, celles **dans la devise reçue** (note de la maquette caisse) ; conversion vers l'autre devise seulement si le caissier le coche.
2. Le caissier peut modifier la répartition avant de valider.
3. Somme des allocations ≤ montant reçu (converti) ; le reste → `StudentCredit`.
4. Validation protégée contre le double envoi (un seul paiement par clic, idempotence par `op_id`).

## Soldes

- Reste dû d'une charge = `amount_minor` − réductions applicables − allocations des paiements **non annulés**.
- Solde élève **par devise**, jamais additionné entre devises (affichage `20,00 $ + 30 000 FC`).
- En retard : `due_on` < aujourd'hui (fuseau de l'école) et reste dû > 0.
- Réduction en % : arrondi demi supérieur à l'unité de la devise ; auteur et motif obligatoires.
- Calcul à la demande, mis en cache, recalculable à tout moment depuis les écritures.

## Annulation, surpaiement

- Un paiement n'est jamais modifié ni supprimé. Annulation = `PaymentCancellation` (motif, demandeur, validateur, reçu d'annulation) ; ses allocations sortent du calcul du solde.
- Reprise en cours d'année (E6, `finance/prior_payments.py`) : `Payment.origin=prior`, sans session de caisse ni reçu. Elle compte dans les soldes comme tout paiement, mais **jamais dans l'argent entré en caisse** : toute somme d'« encaissé » filtre `origin=cash` (`dashboard._payments`) ou passe par une session (clôtures). Montant d'un fichier : texte → `Money.from_major`, jamais `float` ; trois chiffres après le séparateur refusés (« 25,000 » est ambigu).
- Deux caisses hors-ligne qui encaissent pour le même élève : les deux paiements sont valides ; le surplus devient un `StudentCredit` signalé au comptable. Jamais de rejet d'un paiement encaissé physiquement.

## Affichage

Formats de la skill `design` : `1 234,56 $`, `1 260 000 FC`, chiffres tabulaires alignés à droite.
**Montant en lettres** (reçu, F3) : en français, calculé côté navigateur (le reçu s'imprime hors-ligne). Formulation exacte (sous-unités, nom de la devise, soixante-dix / quatre-vingts) à confirmer sur le modèle de reçu de l'ITIG.

## Tests obligatoires

Répartition (ancienne échéance d'abord, partiel, ajustement manuel), conversion et arrondi dans les deux sens, réduction montant et %, annulation qui rouvre le reste dû, surpaiement → crédit, deux devises sur le même élève, montant en lettres (0, 1, 21, 71, 80, 100, 1 000 000, avec centimes).

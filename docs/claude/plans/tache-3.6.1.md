# Tâche 3.6.1 — Crédits d'élèves : serveur, écran M14, dialogue de réduction

Découpage de la 3.6 validé le 2026-09-29 ; utiliser un crédit ne crée pas de paiement (validé).

- **Modèles** (`finance`) : `StudentCredit` (inscription, origine `offline_surplus` / `discount`, montant, devise, paiement ou réduction d'origine, `voided_at` / `voided_by`) ; `CreditAllocation` [I] (crédit, frais dû, montant, même devise que le crédit).
- **Services** : `record_payment` hors ligne → crédit du surplus non affecté ; `grant_discount` → crédit de la hausse du trop-payé, par devise ; `revoke_discount` → annule les crédits de la réduction (leurs affectations ne comptent plus) ; `use_credit` → échéances les plus anciennes dans sa devise, sans paiement ni reçu ; reste « à traiter » si l'élève doit moins. Audit à chaque action.
- **Solde** : payé d'un frais = paiements + crédits affectés, plafonné à ce qui est dû (le trop-payé est le crédit) ; payé + crédits = argent reçu.
- **API** `/api/student-credits/` : liste paginée (état, année), résumé, détail avec la proposition, `use`. Lire : `view_reports` ou `approve_cancellation` ; utiliser : `approve_cancellation`.
- **Front** : écran `credits` (maquette `credits-eleves`, justificatif imprimable) ; colonnes « Déjà payé » / « Effet » du dialogue de réduction (crédit sur la fiche élève : 3.6.2).
- **Démo** : un paiement en double hors ligne et une réduction sur une tranche payée.
- **Tests** : isolation, 403, surplus → crédit, réduction → seulement l'écart, retrait → annulé, utilisation (ordre, reste, audit), payé total = argent reçu.
- **Hors tâche** : crédit à la caisse, en ligne et hors ligne (3.6.2) ; paiement d'origine annulé → crédit annulé (3.8).

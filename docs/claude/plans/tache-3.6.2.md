# Tâche 3.6.2 — Crédit à la caisse

**But** : le crédit d'un élève (M14) est proposé à la caisse au prochain paiement ; le caissier l'utilise en un clic, en ligne et hors ligne ; le crédit à traiter se voit sur la fiche élève (Finances).

**Serveur** (`finance`, `sync`)
- `GET /api/student-charges/credits/?enrollment=` : crédits à traiter de l'inscription (droits `CHARGES_READ`, comme les frais dus).
- `POST /api/student-credits/{id}/use/` : aussi avec `finance.collect_payment` (caissier) ; même service `use_credit` (plus anciennes échéances, même devise, sans paiement, audit).
- Synchro : entité `enrollment` + `credits` (à traiter : id, origine, devise, montant, utilisé, reste, reçu) ; opération `credit.use` (`{credit}`), idempotente par `op_id`.

**Front** (`features/cash`, `features/students`)
- `CollectPanel` : bandeau « Crédit disponible » avec ce qu'il paiera (`allocate`) et « Utiliser le crédit » ; en ligne : POST puis rafraîchir ; appareil : opération `credit.use` dans la file avec ses parts, comptées dans `financeOf` tant que l'état du serveur ne les montre pas (`used_minor` inchangé).
- `StudentFinancesTab` : carte « Crédit à traiter » (origine, reste, lien vers Crédits d'élèves si droit).

**Tests** : caissier utilise (200), secrétaire 403, autre école 404 (API + synchro) ; `credit.use` rejoué = un seul usage ; crédits dans la synchro sans N+1 ; `financeOf` avec usage en file / déjà reflété / refusé ; écran caisse : bouton → POST.

**Risques** : double comptage entre l'envoi et la descente (réglé par `used_minor`) ; duplicata hors ligne sans les crédits utilisés → noté en 3.8.

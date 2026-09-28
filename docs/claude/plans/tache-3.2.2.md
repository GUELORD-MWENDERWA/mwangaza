# Tâche 3.2.2 — Reçu dans le navigateur

**Serveur (finance)** : `services.balance_after(payment)` (solde juste après ce paiement : paiements jusqu'à lui, pas encore annulés à ce moment-là ; retard au jour du paiement) ; `reprint_payment` → audit `finance.payment_reprinted`, refusé (409) pour un paiement annulé ; `PaymentReceiptSerializer` (échéance des lignes, nom de la caisse, année, solde) rendu par création, lecture et `POST /api/payments/{id}/reprint/`. `/api/school/` (public) donne aussi les réglages du reçu et le logo noir et blanc (imprimés sur chaque reçu).

**Front** : `amountInWords` dans `@mwangaza/money` (français) ; `features/cash/Receipt.tsx` + `receipt.css` : reçu thermique 58 / 80 mm, A6 / A5 / petit format sur A4 avec traits de découpe, 1 ou 2 exemplaires (élève / souche), DUPLICATA avec heure de réimpression, QR code vers `/v/{id}` (composant `QrCode` existant) ; impression par une zone cachée à l'écran + `window.print()`. « Encaisser et imprimer » (F9), « Réimprimer » (bandeau et paiements du jour), « Test » sur l'ouverture de caisse.

**Tests** : serveur — solde du reçu après chaque paiement (paiement suivant et annulation après coup ignorés), réimpression auditée et refusée si annulé, isolation et droits de `reprint` (ajoutés aux tests existants). Front — montant en lettres (0, 1, 21, 71, 80, 100, 1 000 000, centimes, FC), encaisser et imprimer puis réimprimer (DUPLICATA). E2E caisse : `window.print` neutralisé, reçu présent.

**Décisions** : pas de `uqr` (qrcode-generator déjà installé fait le même SVG) ; montant en lettres toujours en français ; pas d'aperçu à l'écran ni de bouton « Imprimer en A4 » (format choisi dans les paramètres) ; thermique : `@page { margin: 0 }`, largeur de papier réglée dans le pilote.

**Risques** : impression réelle non testable en CI (vérifiée par capture de l'aperçu PDF de Chrome).

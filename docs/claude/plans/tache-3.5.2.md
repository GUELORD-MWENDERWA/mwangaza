# Tâche 3.5.2 — Ouverture et réimpression hors ligne, QR signé (F4)

**Serveur** (`sync/operations.py`, `finance/services.py`, `finance/verification.py`)
- Opérations `cash_session.open` (id de l'appareil, caisse, heure de l'appareil → `open_cash_session`, audit à l'heure de l'appareil ; caisse prise entre-temps → refusée, à régler en 3.8) et `payment.reprint` (paiement de sa session, heure de réimpression → audit ; noté même si annulé depuis : le papier existe).
- `/v/{id}?n=&t=&a=&c=&r=&s=` : QR signé par l'appareil (ECDSA P-256, message `id|n|t|a|c|r`). Paiement connu : contenu différent → « falsifié ». Inconnu : appareil trouvé par le préfixe du numéro, signature juste → « authentique, émis hors ligne par la caisse C1, en attente de synchronisation » ; fausse → « falsifié » ; appareil révoqué ou opération refusée → « inconnu ».
- Pas de champ `Payment.receipt_signature` (le QR suffit ; une fois synchronisé, la base fait foi) → `04` corrigé.

**Front** (`features/cash`, `lib/device.ts`, `lib/sync/db.ts`)
- Appareil mémorisé : ouverture toujours par la file (caisses de la config, occupées si lues en ligne) ; session de l'op en attente affichée, écrite dans la session gardée quand le serveur l'applique ; refus → bandeau sur l'écran d'ouverture.
- Réimpression sur l'appareil : duplicata fait sur place (solde juste après le paiement, même calcul que `balance_after`) + op `payment.reprint`.
- Chaque reçu imprimé sur un appareil mémorisé est signé à l'impression ; QR agrandi (57 modules).

**Tests** : pytest (ops ouverture / réimpression idempotentes, isolation, droits ; page : en attente, falsifié, contenu modifié, révoqué, autre école) ; Vitest (solde du duplicata, session locale) ; Playwright caisse : ouverture hors ligne, deux encaissements, duplicata, page `/v/` « en attente », retour réseau sans doublon.

**Risques** : QR plus dense sur thermique 58 mm ; ouverture hors ligne refusée → paiements refusés (3.8).

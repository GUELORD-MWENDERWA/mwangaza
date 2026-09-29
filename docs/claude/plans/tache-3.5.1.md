# Tâche 3.5.1 — Encaisser hors ligne

Décidé avec l'utilisateur (2026-09-29) : 3.5 découpée (3.5.1 encaisser hors ligne ; 3.5.2 ouverture et réimpression hors ligne, QR signé) ; sur un appareil mémorisé, on encaisse **toujours par la file** (numéro de l'appareil `ITIG-P1-26-…`), avec ou sans réseau ; appareil non mémorisé : encaissement en ligne actuel.

- Serveur : `Payment.cash_session` exposé (paiements de la session retrouvés sur l'appareil) ; `make api`.
- `lib/sync/db.ts` : table `cash` (session ouverte du caissier, gardée à chaque lecture en ligne) ; opération appliquée → `sent`, retirée à la descente suivante (le solde ne « perd » jamais le paiement entre l'envoi et la descente) ; séquence des reçus jamais reculée par un instantané.
- `lib/sync/session.ts` : base de l'appareil donnée aux écrans.
- `features/cash/offline.ts` (pur, Vitest) : paiements en attente ajoutés aux frais dus (une fois, par `id`), solde (même calcul que `finance.services.balance`), recherche, numéro de reçu, reçu imprimé sans serveur.
- `features/cash/localData.ts` : lectures Dexie en direct ; encaissement = une transaction (séquence + opération), puis `syncNow()`.
- Écrans : `CashPage` (source appareil ou serveur ; page « stockage refusé » avec « Continuer en ligne seulement ») ; `CashDesk` (recherche, totaux, liste avec « en attente » / « refusé ») ; `CollectPanel` (encaisser par la file).
- Tests : Vitest (paiement déjà reçu par le serveur compté une fois, refusé non compté, solde, numéros consécutifs) ; Playwright `caisse.spec.ts` : réseau coupé, deux encaissements, reçus consécutifs, retour du réseau, aucun doublon, solde juste côté serveur.
- Hors 3.5.1 : ouverture de caisse et réimpression hors ligne, QR signé (3.5.2) ; démarrage sans réseau (3.7).
- Risques : Chromium sans écran refuse peut-être `persist()` → le test le simule ; requêtes en échec hors ligne (`network`) → repli sur l'appareil.

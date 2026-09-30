# Tâche 3.8.2 — Clôture de caisse par le caissier (F8)

**Serveur** : `CashClosing` [T][I] une ligne par devise (attendu, compté, écart, explication, `closed_at` de l'appareil, `closed_by`, `device`) ; `CashSession.device` (ouverte hors ligne). `services.closing_summary` (attendu par devise, détail par type de frais + trop-perçu, reçus, annulations) et `close_cash_session` (caissier de la session seulement, audit `finance.cash_session_closed`). `GET/POST /api/cash-sessions/{id}/closing/`. Opération `cash_session.close`. Démo : clôtures des sessions passées (une avec écart).
**Appareil / écran** : `features/cash/ClosingPage.tsx` (maquette `caisse-cloture`), résumé calculé sur l'appareil (`closing.ts`) ou lu au serveur ; bordereau imprimé à la clôture ; bouton « Clôturer » dans la caisse ; clôture dans la file = plus de session sur l'appareil (et `settle` vide la session gardée).

**Décisions** (à valider dans la PR, journal de `03`) :
- Hors ligne, l'argent est déjà reçu : une ouverture hors ligne n'est plus refusée (caisse prise, caissier déjà ouvert ailleurs, caisse désactivée) et un paiement hors ligne d'une session close est accepté ; il n'entre pas dans l'attendu déjà figé (3.8.3 le montre « arrivé après la clôture »).
- Contraintes « une session ouverte par caisse / par caissier » : seulement pour les ouvertures en ligne ; `open_session_of` rend la plus ancienne (à clôturer d'abord).
- Attendu calculé par le serveur à l'arrivée : paiements de la session non annulés à l'heure de clôture. Devises : celles de l'école + celles des paiements. En ligne : compté pour chaque devise et explication exigée s'il y a un écart ; hors ligne : rien refusé (devise non comptée = 0).

**Tests** : isolation (session d'une autre école → 404), permission (sans `finance.collect_payment` → 403 ; session d'un autre caissier → 404), argent (attendu, écart, annulé exclu, explication obligatoire), immuable + audit, hors ligne (rejeu = une clôture ; paiement tardif accepté hors attendu ; ouverture sur caisse prise acceptée avec ses paiements) ; front : calcul du résumé, écart → explication exigée, clôture hors ligne mise en file.

**Risques** : relâcher les contraintes de session (tests existants d'ouverture) ; taille (serveur + écran) — l'écran du comptable est en 3.8.3.

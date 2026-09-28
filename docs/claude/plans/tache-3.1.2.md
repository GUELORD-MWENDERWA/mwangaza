# Tâche 3.1.2 — Écrans de caisse en ligne

- **Serveur** : `CashRegisterSerializer.open_session` (qui l'a ouverte, depuis quand, ou `null`) pour « Libre / Occupée » ; une requête de plus (Prefetch), pas de N+1.
- **`packages/money`** : `convert()` (entiers, BigInt, demi supérieur, CDF → USD en divisant), mêmes résultats que `Money.convert`.
- **`features/cash/`** : `allocation.ts` (portage de `allocate` et `_part_for` : devise reçue d'abord, puis l'autre si « Convertir », échéances les plus anciennes ; cases cochées = ajustement) ; `CashPage` : pas de session → `caisse-ouverture`, sinon accueil (`caisse-accueil`) qui devient encaissement (`caisse-encaissement`) quand un élève est choisi.
- Encaissement : la répartition affichée est envoyée telle quelle (`allocations`), le serveur la vérifie ; `id` UUID v7 gardé jusqu'au succès (double clic, nouvel essai) ; surplus bloqué (crédit en 3.6) ; F9 valide, Échap change d'élève, Ctrl K met le curseur dans la recherche de la caisse (la palette globale laisse faire).
- Accueil : totaux par devise de la session, paiements de la session (recherche, pagination), élèves récents.
- **Paramètres** : carte « Caisses » (ajouter nom + code, renommer, désactiver / réactiver), avec `finance.configure_fees`.
- Hors tâche (masqué) : réimpression et imprimante (3.2), prochain reçu (3.3), en attente d'envoi (3.4), annulations et clôture (3.8), montants rapides fixes (20 $, 50 $ : en dur pour une école).

Tests : serveur 1 (caisse occupée, sans fuite entre écoles) ; `convert` (deux sens, arrondi) ; `allocation` (ordre, partiel, conversion, cases cochées, surplus) ; écran 2 (répartition envoyée + même `id` au nouvel essai ; surplus bloqué) ; Playwright : caissière ouvre la caisse, encaisse, voit le paiement du jour.

Risque : écart d'arrondi entre `convert` TS et `Decimal` → mêmes cas de test des deux côtés ; le serveur refuse de toute façon une part fausse.

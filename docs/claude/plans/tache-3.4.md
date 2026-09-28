# Tâche 3.4 — Synchronisation dans le navigateur

**Base locale** (`lib/sync/db.ts`, Dexie, déjà dans la stack) : une base par appareil `mwangaza-sync-<id>` ; tables `enrollments` (état du serveur, `gen`), `config`, `meta` (curseur, instantané en cours, dernière synchro, séquence des reçus), `outbox` (`++seq`, `&op_id`, `status` : `pending` / `rejected`). L'état du serveur n'est jamais modifié sur place : les opérations en attente s'y superposent (3.5).

**Moteur** (`lib/sync/engine.ts`, sur des interfaces `LocalStore` / `SyncServer` comme `device.ts`) : 1) envoi des opérations en attente, dans l'ordre, par 100, avec `receipt_seq` ; `applied` / `duplicate` → retirées, `rejected` → gardées visibles avec l'erreur, plus renvoyées ; 2) instantané par pages, reprenable, nouvelle génération (l'ancienne reste lisible jusqu'à la fin), séquence des reçus = max(locale, serveur) ; 3) `pull` jusqu'à `has_more = false` ; `snapshot_required` → nouvel instantané ; `device_revoked` → base effacée et appareil oublié.

**Déclencheurs** (`lib/sync/runner.ts` + `useSync`) : ouverture de la coquille (appareil mémorisé et droit `students.view` ou `finance.collect_payment`), retour du réseau, toutes les 60 s en ligne, « Synchroniser maintenant » ; une seule à la fois. En attente / refusées lues en direct (`liveQuery` de Dexie).

**Indicateur** : « En ligne · à jour », « … · N en attente », « Synchronisation… », refusées en rouge ; clic → menu : dernière synchro, en attente, refusées, stockage, « Synchroniser maintenant ».

**Stockage persistant** : `navigator.storage.persist()` au démarrage ; refusé → bandeau (textes M8) « Réessayer » / « Continuer en ligne seulement » (caché pour la session). La page bloquante sur la caisse hors-ligne : 3.5.

**Mise à jour** (M8) : avec des opérations en attente, « Elle s'installera après la synchronisation des N opérations » ; installée quand la file est vide.

**Tests** : moteur (Vitest, ~6 : pages et reprise de l'instantané, pull et suppression, `snapshot_required`, envoi et refus gardés, appareil révoqué) ; mise à jour pas forcée avec file non vide ; Playwright : connexion mémorisée → données chargées → hors ligne / en ligne.

**Hors tâche** : écran admin « Appareils et synchro » (maquette `appareils-synchro`) → 3.7 ; démarrage sans réseau (`/api/me/` indisponible) → 3.7 (PIN).

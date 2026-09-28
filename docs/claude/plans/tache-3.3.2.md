# Tâche 3.3.2 — Synchronisation serveur

**Modèles** (`sync`) : `SyncOperation` (`op_id` unique par école, appareil, type, contenu, `applied` / `rejected`, résultat) ; `ChangeLog` (une ligne par entité, sa dernière modification ; `seq` vide à l'écriture, donné à la lecture). `Payment` : `device`, `synced_at` (migration `finance`).

**Entités descendues** : `enrollment` (élève, classe, frais dus avec réductions / payé / reste, paiements) et `config` (école, reçus, année en cours, classes, types de frais, caisses, taux). Changements notés par signaux Django (`post_save` / `post_delete`) et, après les écritures en masse (frais dus, échéancier, import, classes), par un appel explicite.

**Numéro croissant sans trou de lecture** : `seq` donné sous verrou de l'école aux lignes validées (`skip_locked`) : une transaction longue (import) ne bloque pas `pull`, et aucun changement validé plus tard ne reçoit un numéro plus petit que ce que l'appareil a déjà lu.

**Endpoints** `/api/sync/` : `snapshot` (pages d'inscriptions ; curseur, appareil et configuration sur la première), `pull?since=&limit=` (inscriptions hors année en cours → `delete`), `push` (lots de 100 dans l'ordre ; `applied` / `duplicate` / `rejected` + erreur ; même `op_id` → même résultat ; `receipt_seq` gardé sur l'appareil).

**Opération** `payment.create` : `record_payment` avec numéro de l'appareil (`ITIG-P1-26-000184`, préfixe et année vérifiés), heure de l'appareil, taux en vigueur ; surplus laissé non réparti (crédit en 3.6) au lieu d'un refus.

**Accès** : appareil enregistré de la session (sinon 403 `device_required`), pas révoqué (409 `device_revoked`) ; `students.view` ou `finance.collect_payment` ; frais et paiements seulement avec une permission finance (paiements des autres caissiers seulement avec `finance.view_reports`).

**Tests** (`sync/tests/test_sync.py`) : isolation (snapshot / pull / push d'une autre école), permissions, idempotence (même lot deux fois → un paiement), appareil révoqué, surplus accepté, numéro de reçu d'un autre appareil refusé, pull voit un changement validé après une transaction plus ancienne, écritures en masse notées.

**Risques** : signaux oubliés sur une écriture en masse future (docstring de `changes.py`) ; taille de l'instantané (pages de 200).

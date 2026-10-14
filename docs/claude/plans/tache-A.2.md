# Tâche A.2 — Purge des opérations de synchronisation

**But** : `SyncOperation` (une ligne par opération envoyée par un appareil, avec son contenu JSON) ne grossit plus sans fin : chaque nuit, le planificateur efface les opérations **appliquées** de plus de 90 jours, dans toutes les écoles.

**Hors périmètre / retiré (regard senior)** :
- `ChangeLog` n'est **pas** purgé : il a une ligne par inscription (plus une pour la configuration), renumérotée à chaque changement, pas une ligne par paiement. Il grossit donc comme `Enrollment`, que l'on garde. Effacer une ligne ferait rater une suppression à un appareil en retard, sauf à ajouter un plancher par école et un instantané forcé : beaucoup de complexité pour peu de place gagnée.
- Les opérations **refusées** restent : `finance/verification.py` s'en sert (reçu hors ligne refusé → « inconnu ») ; elles sont rares.
- Pas d'index sur `created_at` : un parcours de la table par nuit, sur 90 jours de lignes, coûte moins qu'un index mis à jour à chaque envoi.

**Critères d'acceptation** : tâche Celery `apps.sync.tasks.purge` dans `CELERY_BEAT_SCHEDULE` (chaque nuit) ; une seule requête DELETE ; une opération renvoyée après la purge ne crée pas de doublon (l'encaissement garde son identifiant : `record_payment` rend le paiement existant).

**Tests obligatoires** : purge sur deux écoles (ancienne appliquée effacée, récente et refusée gardées) ; paiement renvoyé après la purge → pas de second paiement.

**Documents** : `05` (A.2 corrigé et coché, file barrée), `06`, `03` (journal des décisions), `docs/claude/reference.md` (tâches de fond), `04` si `SyncOperation` y est décrit.

**Risques** : une opération reçue, réponse perdue, appareil hors ligne plus de 90 jours puis renvoi : encaissement protégé par son identifiant ; réimpression notée deux fois au plus (sans effet sur l'argent).

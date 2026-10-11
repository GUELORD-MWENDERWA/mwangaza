# Tâche 4.7.1 — Sauvegardes prêtes, essayées sur la machine

Issue #164 · branche `tache/4.7.1-sauvegardes` · 2026-10-11

**But** (I4 précisé, `02` § 2 bis) : une sauvegarde chiffrée qu'on sait remettre en service, avant d'acheter le stockage (4.7.2).

**Fichiers**
- `infra/backup/sauvegarde.sh` : `backup` (purge des sessions expirées, dump `pg_dump -Fc` fait dans le conteneur `db`, archive des fichiers, chiffrement `gpg` AES-256, rotation) et `restore` (base à part `mwangaza_restauration`, comparaison table par table avec la base en service ; `--remplacer` : bascule par renommage, l'ancienne base est gardée).
- `Makefile` : `make backup`, `make restore` (`file=`, `remplacer=oui`, `pile=reseau|essai` pour les images du serveur) ; `.gitignore` : `sauvegardes/`.
- `infra/serveur/deployer.sh` : `make deploy` installe la tâche du jour dans le crontab du compte ; `preparer.sh` : `gnupg`.
- Documents : `03` (§ 9 et journal), `05`, `06`, `reference.md`, `CLAUDE.md`, `A-FAIRE.md` (§ 9, § 11), `infra/README.md`, `.env.example`, skill `deployer`.

**Décisions (regard senior)**
- Une seule commande = la tâche du jour (purge + sauvegarde + rotation) : même chemin essayé à la main et lancé par cron ; pas de planificateur Celery ni de nouveau conteneur.
- Purge des sessions en SQL dans `db` (ce que fait `clearsessions`) : pas de Django à démarrer chaque nuit.
- `pg_dump` / `pg_restore` du conteneur `db` : même version que le serveur PostgreSQL, rien à installer dans l'image.
- Rotation : base 30 jours, fichiers 7 jours (archive complète, plus lourde) ; jamais avant une sauvegarde réussie.
- Sans clé `BACKUP_PASSPHRASE` (serveur de démonstration) : purge seulement, dit dans le journal.
- Remplacer la base = renommer, rien n'est effacé (règle 3).

**Tests** : pas de test en CI (script d'exploitation, Docker requis) ; essai réel sur la machine noté dans la PR : sauvegarde, restauration à part, 0 différence, mauvaise clé refusée, bascule.

**Hors tâche (4.7.2)** : envoi vers le stockage objet, sauvegarde continue (WAL), suivi d'erreurs, sonde.

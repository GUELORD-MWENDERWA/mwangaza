# Plan 4.7.2 — sauvegardes hors du serveur, erreurs, sonde

Branche `tache/4.7.2-sauvegardes-hors-serveur` · 2026-10-13. Décisions de l'utilisateur : Backblaze B2, rclone, Sentry.

**Fichiers**
- `infra/backup/sauvegarde.sh` : après la sauvegarde, copie vers B2 (`rclone copy`, config par variables `RCLONE_CONFIG_*` tirées de `serveur.env`) ; rotation distante ; `fetch` rapatrie la dernière paire pour `restore` ; ping de supervision (succès / échec) ; échec = code ≠ 0.
- `infra/serveur/preparer.sh` : installe `rclone` ; `init.py` / `.env.example` : variables `BACKUP_B2_*`, `BACKUP_PING_URL`, `SENTRY_DSN`.
- `backend` : `sentry-sdk` (seule dépendance), initialisé dans `prod.py` si `SENTRY_DSN`, sans données personnelles ; passé par `docker-compose.yml`.
- Docs : `03` (journal), `A-FAIRE.md` (clés B2, Sentry, UptimeRobot, Healthchecks), `reference.md`, `infra/README.md`, skill `deployer`, `06`, `05`.

**Tests** : Sentry — `before_send` retire les données personnelles, rien sans DSN. Script : essai réel avec un « stockage » rclone local (`:local:`) à la main, non automatisé (shell).

**Retiré (regard senior)** : sauvegarde continue WAL-G / pgBackRest — un conteneur de plus et de la complexité pour restaurer « à la minute » ; un dump chiffré chaque nuit (perte max. 24 h) suffit pour une école ; à revoir au-delà de ~10 écoles.

**Risques** : clés B2 pas encore créées (action de l'utilisateur) — le script ne copie rien tant que `BACKUP_B2_BUCKET` est vide, sans erreur.

# Infrastructure

| Fichier | Rôle | Tâche |
|---|---|---|
| `docker-compose.dev.yml` | développement : PostgreSQL 16, Redis 7, Django, Celery (worker et planificateur, 5.6.2), Vite (Gestion + Portail) | 0.1 |
| `Dockerfile` | images de production : front construit (pnpm), Django + gunicorn (aussi pour Celery), Caddy avec la Gestion, le Portail, la console et les fichiers statiques de Django | 4.6.1 |
| `docker-compose.yml` | production : Caddy (seul ouvert, 80 et 443), Django (gunicorn), `worker` (file rapide), `worker-heavy` (file lourde : PDF, imports), `scheduler` (planificateur, seul), Redis, PostgreSQL ; limites de mémoire de chaque service (PERF.5a, somme ≈ 1,78 Go) ; `migrate` tourne avant Django et les travailleurs puis s'arrête : migrations, puis droits du compte PostgreSQL de l'application (`manage.py setup_app_role`, S.5). Lui seul a le compte propriétaire (`POSTGRES_PASSWORD`) ; Django et Celery ont `mwangaza_app` (`POSTGRES_APP_PASSWORD`), lignes seulement ; journaux limités | 4.6.1 |
| `Caddyfile` | HTTPS, `{ecole}.mwangazaschool.com`, `parents.mwangazaschool.com`, `admin.mwangazaschool.com`, compression, adresse IP réelle du visiteur (Cloudflare) | 4.6.1 |
| `routes.caddy` | routes de chaque adresse, communes aux adresses du serveur : école (`/app`, `/api`, `/v`), portail, console (`/api`, `/admin` vers Django), site public sur le domaine nu (Django, seul indexé ; espaces privés en `noindex`), cache des PWA ; requêtes vers Django limitées à 10 Mo (S.4) | 4.6.1 |
| `serveur/preparer.sh` | vrai serveur, une fois, en root par SSH (`make deploy-setup`) : mises à jour automatiques, Docker, ports 80 et 443, SSH par clé seulement | 4.6.3 |
| `serveur/deployer.sh` · `serveur/init.py` | vrai serveur piloté depuis la machine (`make deploy…`) : `init` (crée `serveur.env`, hors Git, secrets neufs ; ajoute à un fichier existant un secret apparu depuis), `git archive` envoyé par SSH dans `~/mwangaza/code` (mise à jour sur place), images construites sur le serveur, `up --wait`, `check`, super-admin, journaux | 4.6.3 |
| `.env.example` | modèle de `infra/.env` sur le serveur (domaine, certificat, secrets, clés des notifications Web Push : `manage.py webpush_keys`) | 4.6.1, 5.5.1 |
| `local.env` | valeurs publiques de l'essai sur la machine (`make prod-local`) | 4.6.1 |
| `certs/` | certificat d'origine Cloudflare (`origin.pem`, `origin.key`), hors Git | 4.6.3 |
| `backup/sauvegarde.sh` | tâche de chaque nuit (crontab du compte, posé par `make deploy`) et `make backup` : sessions expirées effacées, dump de la base et archive des fichiers chiffrés par `gpg` (clé `BACKUP_PASSPHRASE` ; sans clé : purge seule), rotation 30 / 7 jours ; `make restore` : essai dans une base à part comparée table par table, `remplacer=oui` pour remettre en service (l'ancienne base est gardée) ; journal sur le serveur : `journalctl -t mwangaza` ; copie vers Backblaze B2 par `rclone` et ping d'alerte (4.7.2) ; `fetch` rapatrie la dernière copie | 4.7.1 |

Essayer la production sur la machine : `make prod-local`, puis https://itig.localhost/app/ (certificat local de Caddy : accepter l'avertissement du navigateur) ; `make prod-local-stop` pour l'arrêter. La base de cet essai est vide (`make demo` est refusé hors développement).



Vrai serveur (AWS Lightsail, 4.6.3) : `serveur/serveur.env` (créé par `make deploy-init`) ; `docker-compose.production.yml` + `production/Caddyfile` (certificat joker par DNS Cloudflare, IP réelle du visiteur lue par Caddy) ; `make deploy-setup`, `make deploy`, `make deploy-check` (`A-FAIRE.md` § 9 ter, skill `/deployer`). Les démonstrations se créent dans la console, pas par `make demo`.

Voir `docs/03-architecture-technique.md` § 2 et § 9.

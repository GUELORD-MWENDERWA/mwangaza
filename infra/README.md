# Infrastructure

| Fichier | Rôle | Tâche |
|---|---|---|
| `docker-compose.dev.yml` | développement : PostgreSQL 16, Redis 7, Django, Celery (worker et planificateur, 5.6.2), Vite (Gestion + Portail) | 0.1 |
| `Dockerfile` | images de production : front construit (pnpm), Django + gunicorn (aussi pour Celery), Caddy avec la Gestion, le Portail, la console et les fichiers statiques de Django | 4.6.1 |
| `docker-compose.yml` | production : Caddy (seul ouvert, 80 et 443), Django, Celery (worker et planificateur des notifications à heure fixe, `-B`), Redis, PostgreSQL ; journaux limités | 4.6.1 |
| `Caddyfile` | HTTPS, `{ecole}.mwangazaschool.com`, `parents.mwangazaschool.com`, `admin.mwangazaschool.com`, compression, adresse IP réelle du visiteur (Cloudflare) | 4.6.1 |
| `routes.caddy` | routes de chaque adresse, communes au serveur et à l'essai sur plusieurs appareils : école (`/app`, `/api`, `/v`), portail, console (`/api`, `/admin` vers Django), cache des PWA | 4.6.1, 4.11 |
| `Caddyfile.reseau` | adresse DuckDNS (essai sur plusieurs appareils, serveur de démonstration en ligne) : un seul certificat Let's Encrypt joker obtenu par DNS chez DuckDNS (module `caddy-dns/duckdns`, image `caddy-reseau` du `Dockerfile`), page d'accueil à `www.` | 4.11 |
| `docker-compose.reseau.yml` | ajouté à `docker-compose.yml` pour l'essai sur plusieurs appareils et le serveur de démonstration en ligne : Caddy DuckDNS, page d'accueil (`ACCUEIL`), logos de démonstration, données fictives permises (`DJANGO_DEMO_DATA`), mot de passe des comptes fictifs propre au serveur (`DJANGO_DEMO_PASSWORD`) | 4.11, 4.6.2 |
| `reseau/essai.py` | essai sur plusieurs appareils : `init` (crée `reseau/reseau.env`, hors Git, avec des secrets neufs), `ip` (adresse de la machine dans DuckDNS), `accueil` (page des QR codes, `reseau/accueil/`, hors Git), `adresses` ; avec `--serveur` : les mêmes pour le serveur de démonstration (`serveur/serveur.env`, IP publique lue dans `SERVEUR`, `serveur/accueil/`) | 4.11, 4.6.2 |
| `serveur/preparer.sh` | serveur de démonstration, une fois, en root par SSH (`make deploy-setup`) : mises à jour automatiques, Docker, ports 80 et 443 (règles iptables des images d'Oracle), SSH par clé seulement | 4.6.2 |
| `serveur/deployer.sh` | serveur de démonstration piloté depuis la machine (`make deploy…`) : `git archive` envoyé par SSH dans `~/mwangaza/code` (mise à jour sur place), images construites sur le serveur, `up --wait` ; données fictives, super-admin, journaux | 4.6.2 |
| `.env.example` | modèle de `infra/.env` sur le serveur (domaine, certificat, secrets, clés des notifications Web Push : `manage.py webpush_keys`) | 4.6.1, 5.5.1 |
| `local.env` | valeurs publiques de l'essai sur la machine (`make prod-local`) | 4.6.1 |
| `certs/` | certificat d'origine Cloudflare (`origin.pem`, `origin.key`), hors Git | 4.6.3 |
| `backup/sauvegarde.sh` | tâche de chaque nuit (crontab du compte, posé par `make deploy`) et `make backup` : sessions expirées effacées, dump de la base et archive des fichiers chiffrés par `gpg` (clé `BACKUP_PASSPHRASE` ; sans clé : purge seule), rotation 30 / 7 jours ; `make restore` : essai dans une base à part comparée table par table, `remplacer=oui` pour remettre en service (l'ancienne base est gardée) ; journal sur le serveur : `journalctl -t mwangaza` ; copie hors du serveur et sauvegarde continue : 4.7.2 | 4.7.1 |

Essayer la production sur la machine : `make prod-local`, puis https://itig.localhost/app/ (certificat local de Caddy : accepter l'avertissement du navigateur) ; `make prod-local-stop` pour l'arrêter. La base de cet essai est vide (`make demo` est refusé hors développement).

Essayer sur plusieurs appareils du même réseau (téléphones, iPhone, autre PC), avec un vrai certificat : `make reseau` (pas à pas dans `A-FAIRE.md` § 9 bis), `make reseau-demo` pour les données fictives, `make reseau-stop` pour l'arrêter.

Serveur de démonstration en ligne, gratuit (Oracle Cloud « Always Free » + DuckDNS), données fictives seulement : `make deploy-setup` une fois, puis `make deploy` (pas à pas dans `A-FAIRE.md` § 9 ter ; skill `/deployer`). Les vraies écoles attendent le vrai domaine (`Caddyfile`, Cloudflare, 4.6.3) et les sauvegardes (4.7).

Vrai serveur (AWS Lightsail, 4.6.3) : `MODE=production` dans `serveur/serveur.env` (créé par `make deploy-init`) ; `docker-compose.production.yml` + `production/Caddyfile` (certificat joker par DNS Cloudflare, IP réelle du visiteur lue par Caddy) ; mêmes commandes `make deploy…`, `make deploy-check` ; `make reseau` n'est pas touché (`A-FAIRE.md` § 9 quinquies).

Voir `docs/03-architecture-technique.md` § 2 et § 9.

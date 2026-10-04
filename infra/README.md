# Infrastructure

| Fichier | Rôle | Tâche |
|---|---|---|
| `docker-compose.dev.yml` | développement : PostgreSQL 16, Redis 7, Django, Celery, Vite (Gestion + Portail) | 0.1 |
| `Dockerfile` | images de production : front construit (pnpm), Django + gunicorn (aussi pour Celery), Caddy avec la Gestion, le Portail, la console et les fichiers statiques de Django | 4.6.1 |
| `docker-compose.yml` | production : Caddy (seul ouvert, 80 et 443), Django, Celery, Redis, PostgreSQL ; journaux limités | 4.6.1 |
| `Caddyfile` | HTTPS, `{ecole}.mwangaza.school`, `parents.mwangaza.school`, `admin.mwangaza.school`, compression, adresse IP réelle du visiteur (Cloudflare) | 4.6.1 |
| `routes.caddy` | routes de chaque adresse, communes au serveur et à l'essai sur plusieurs appareils : école (`/app`, `/api`, `/v`), portail, console (`/api`, `/admin` vers Django), cache des PWA | 4.6.1, 4.11 |
| `Caddyfile.reseau` | essai sur plusieurs appareils : un seul certificat Let's Encrypt joker obtenu par DNS chez DuckDNS (module `caddy-dns/duckdns`, image `caddy-reseau` du `Dockerfile`), page d'accueil à `www.` | 4.11 |
| `docker-compose.reseau.yml` | ajouté à `docker-compose.yml` pour l'essai sur plusieurs appareils : Caddy de l'essai, page d'accueil, logos de démonstration, données fictives permises (`DJANGO_DEMO_DATA`) | 4.11 |
| `reseau/essai.py` | essai sur plusieurs appareils : `init` (crée `reseau/reseau.env`, hors Git, avec des secrets neufs), `ip` (adresse de la machine dans DuckDNS), `accueil` (page des QR codes, `reseau/accueil/`, hors Git), `adresses` | 4.11 |
| `.env.example` | modèle de `infra/.env` sur le serveur (domaine, certificat, secrets, clés des notifications Web Push : `manage.py webpush_keys`) | 4.6.1, 5.5.1 |
| `local.env` | valeurs publiques de l'essai sur la machine (`make prod-local`) | 4.6.1 |
| `certs/` | certificat d'origine Cloudflare (`origin.pem`, `origin.key`), hors Git | 4.6.2 |
| `backup/` | sauvegardes continues + dump quotidien vers le stockage objet, test de restauration | 4.7 |

Essayer la production sur la machine : `make prod-local`, puis https://itig.localhost/app/ (certificat local de Caddy : accepter l'avertissement du navigateur) ; `make prod-local-stop` pour l'arrêter. La base de cet essai est vide (`make demo` est refusé hors développement).

Essayer sur plusieurs appareils du même réseau (téléphones, iPhone, autre PC), avec un vrai certificat : `make reseau` (pas à pas dans `A-FAIRE.md` § 9 bis), `make reseau-demo` pour les données fictives, `make reseau-stop` pour l'arrêter. Jamais sur le serveur.

Voir `docs/03-architecture-technique.md` § 2 et § 9.

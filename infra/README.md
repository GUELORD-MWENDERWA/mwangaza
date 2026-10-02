# Infrastructure

| Fichier | Rôle | Tâche |
|---|---|---|
| `docker-compose.dev.yml` | développement : PostgreSQL 16, Redis 7, Django, Celery, Vite (Gestion + Portail) | 0.1 |
| `Dockerfile` | images de production : front construit (pnpm), Django + gunicorn (aussi pour Celery), Caddy avec la Gestion, le Portail, la console et les fichiers statiques de Django | 4.6.1 |
| `docker-compose.yml` | production : Caddy (seul ouvert, 80 et 443), Django, Celery, Redis, PostgreSQL ; journaux limités | 4.6.1 |
| `Caddyfile` | HTTPS, `{ecole}.mwangaza.school` (`/app`, `/api`, `/v`), `parents.mwangaza.school`, `admin.mwangaza.school` (console ; `/api`, `/admin` vers Django), compression, cache des PWA, adresse IP réelle du visiteur (Cloudflare) | 4.6.1 |
| `.env.example` | modèle de `infra/.env` sur le serveur (domaine, certificat, secrets) | 4.6.1 |
| `local.env` | valeurs publiques de l'essai sur la machine (`make prod-local`) | 4.6.1 |
| `certs/` | certificat d'origine Cloudflare (`origin.pem`, `origin.key`), hors Git | 4.6.2 |
| `backup/` | sauvegardes continues + dump quotidien vers le stockage objet, test de restauration | 4.7 |

Essayer la production sur la machine : `make prod-local`, puis https://itig.localhost/app/ (certificat local de Caddy : accepter l'avertissement du navigateur) ; `make prod-local-stop` pour l'arrêter. La base de cet essai est vide (`make demo` est refusé hors développement).

Voir `docs/03-architecture-technique.md` § 2 et § 9.

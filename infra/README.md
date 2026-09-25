# Infrastructure

| Fichier | Rôle | Tâche |
|---|---|---|
| `docker-compose.dev.yml` | développement : PostgreSQL 16, Redis 7, Django, Celery, Vite (Gestion + Portail) | 0.1 |
| `docker-compose.yml` | production sur le VPS : Caddy, Django (gunicorn), Celery, Redis, PostgreSQL | 4.6 |
| `Caddyfile` | HTTPS, `{ecole}.mwangaza.cd`, `parents.mwangaza.cd`, `admin.mwangaza.cd` | 4.6 |
| `backup/` | sauvegardes continues + dump quotidien vers le stockage objet, test de restauration | 4.7 |

Voir `docs/03-architecture-technique.md` § 2 et § 9.

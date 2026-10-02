# Tâche 4.6.1 — Production prête, essayée sur la machine

Découpage de la 4.6 (2026-10-02, accord de l'utilisateur) : domaine, Cloudflare et VPS pas encore achetés. 4.6.1 = tout ce qui se fait et s'essaie sans eux ; 4.6.2 = VPS, DNS, certificat, `make deploy`, première mise en ligne.

**Fichiers**
- `infra/Dockerfile` (une image, trois étapes) : front construit (pnpm), back (uv sans dev, gunicorn, collectstatic, utilisateur non root), Caddy avec les deux PWA et les fichiers statiques de Django.
- `infra/docker-compose.yml` : caddy, django (migrate puis gunicorn), celery, redis, postgres ; journaux limités ; `infra/.env.example` (serveur) et `infra/local.env` (essai sur la machine, `tls internal`, domaine `localhost`).
- `infra/Caddyfile` : `{ecole}.` (/app → Gestion, /api et /v → Django), `parents.` (Portail + /api), `admin.` (Django), racine → portail ; compression ; cache long pour les fichiers à empreinte, `no-cache` pour le reste (mises à jour des PWA) ; IP réelle : `CF-Connecting-IP` seulement si la requête vient de Cloudflare, transmise à Django en `X-Real-IP`.
- `.dockerignore` (liste blanche : jamais `prive/`, `depot/`, `.env`).
- Django : `client_ip` lit l'en-tête du proxy si `CLIENT_IP_HEADER` est réglé (prod), adresse vérifiée ; HSTS réglable (0 pour l'essai local) ; `gunicorn` (accepté le 2026-10-02).
- `Makefile` : `prod-local` / `prod-local-stop`.

**Tests** : `client_ip` (en-tête du proxy pris en prod, ignoré sinon, valeur invalide ignorée). Essai réel : pile de production lancée sur la machine, `curl` sur santé, Gestion, Portail, administration (CSS), `/v/…` servi par Django, compression, en-têtes de cache.

**Décisions** : certificat d'origine Cloudflare (15 ans, wildcard) au lieu d'un plugin Caddy ; images construites sur le VPS (pas de registre) ; photos et pièces jointes sur un volume jusqu'à la 4.7 (stockage objet).

**Risques** : plages d'IP de Cloudflare écrites dans le Caddyfile (à revoir si Cloudflare les change) ; construction du front sur un VPS de 4 Go.

# Tâche 4.11 — Essai sur plusieurs appareils (réseau local, DuckDNS, vrai certificat)

Issue #150. Base : `make prod-local` ; projet Docker à part `mwangaza-reseau` (ses propres données et certificats).

- **Certificat** : un seul joker `*.<nom>.duckdns.org` par DNS (DuckDNS ne garde qu'un TXT à la fois ; Caddy 2.11 réutilise le joker pour `parents.` et `admin.`). Pas de domaine nu (il demanderait un second certificat) : page d'accueil à `www.`.
- `infra/Dockerfile` : étapes `caddy-builder` (xcaddy + `caddy-dns/duckdns` v0.5.0) et `caddy-reseau` ; l'image du serveur ne change pas.
- `infra/Caddyfile` : les routes deviennent des extraits (`infra/routes.caddy`) partagés avec `infra/Caddyfile.reseau` (jeton lu par `{env.DUCKDNS_TOKEN}`, jamais écrit dans la configuration).
- `infra/docker-compose.reseau.yml` (surcharge) : image Caddy de l'essai, page d'accueil, logo de démonstration, `DJANGO_DEMO_DATA=true` (seulement ici, jamais dans `.env.example`).
- `infra/reseau/essai.py` (lancé par `uv run`) : `init` crée `infra/reseau.env` (hors Git) avec secrets et clés Web Push générés ; `ip` met l'adresse de la machine dans DuckDNS ; `accueil` écrit la page avec les QR (segno, déjà là).
- Makefile : `reseau`, `reseau-ip`, `reseau-demo`, `reseau-stop`. `make totp` sert tel quel (même clé de démonstration).
- Backend : réglage `DEMO_DATA` (dev : vrai ; prod : `DJANGO_DEMO_DATA`, faux par défaut) lu par `demo`.

Tests : `demo` refusé sans `DEMO_DATA` ; `caddy adapt` des deux Caddyfile ; `essai.py` essayé à blanc (outil d'essai, pas de test automatique).
Docs : A-FAIRE (pas à pas : compte DuckDNS, jeton, `ufw`, iPhone), `infra/README.md`, CLAUDE.md, `03` journal, `05`, `06`, `07` § 4.
Risques : DNS du partage qui refuse une adresse privée (rare, documenté) ; limites Let's Encrypt (certificat gardé dans le volume `caddy-data`).

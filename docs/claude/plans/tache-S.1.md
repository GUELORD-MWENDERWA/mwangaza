# Tâche S.1 — En-têtes de sécurité et CSP

**But** : les fichiers des trois applications (Gestion, Portail, Console) sont servis avec HSTS, `X-Frame-Options: DENY`, `Permissions-Policy` et une CSP stricte.

**Hors périmètre** : en-têtes des réponses Django (`/api`, `/admin`, déjà réglés côté Django) ; passage de Cloudflare en nuage orange (décidé, action 👤 sur le DNS, `A-FAIRE.md`) ; point de collecte des rapports CSP.

**Critères** : un snippet `securite` importé par `pwa` dans `infra/routes.caddy` (donc vrai serveur et essai local) ; CSP en `Report-Only` par défaut, imposée par `CSP_HEADER=Content-Security-Policy` ; commentaire périmé sur le certificat d'origine retiré.

**Tests** : `backend/tests/test_caddy_headers.py` (en-têtes présents, trois applications, pas d'`unsafe-eval`, pas d'`unsafe-inline` en script) ; `caddy adapt` sur le vrai Caddyfile.

**Documents** : `05`, `06`, `03` (journal), `A-FAIRE.md`, `infra/README.md` si utile.

**Risques** : `frame-src 'self' blob:` pour les aperçus de documents ; styles en ligne autorisés (Radix/Tailwind). Un mois de HSTS (comme Django), pas plus avant d'être sûr.

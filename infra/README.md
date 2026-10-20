# Infrastructure

| Fichier | Rôle | Tâche |
|---|---|---|
| `docker-compose.dev.yml` | développement : PostgreSQL 16, Redis 7, Django, Celery (worker et planificateur, 5.6.2), Vite (Gestion + Portail) | 0.1 |
| `Dockerfile` | images de production : front construit (pnpm), Django + gunicorn (aussi pour Celery), Caddy avec la Gestion, le Portail, la console et les fichiers statiques de Django | 4.6.1 |
| `docker-compose.yml` | production : Caddy (seul ouvert, 80 et 443), Django (gunicorn), `worker` (file rapide, un second travailleur seulement quand des tâches attendent), `worker-heavy` (file lourde : PDF, imports), `scheduler` (planificateur, seul et sans Django : `backend/beat.py`, il ne reçoit que l'adresse de Redis, PERF.8), Redis, PostgreSQL ; `serveur/conteneurs.sh` (cron, 5 min) note mémoire et état de chaque conteneur dans Redis pour la carte « Santé » de la console, guide `docs/exploitation.md` (PERF.5b) ; limites de mémoire de chaque service (PERF.5a et PERF.8, somme ≈ 1,73 Go ; `make deploy-memoire` montre ce qui pèse sur la machine) ; `migrate` tourne avant Django et les travailleurs puis s'arrête : migrations, puis droits du compte PostgreSQL de l'application (`manage.py setup_app_role`, S.5). Lui seul a le compte propriétaire (`POSTGRES_PASSWORD`) ; Django et Celery ont `mwangaza_app` (`POSTGRES_APP_PASSWORD`), lignes seulement ; journaux limités | 4.6.1 |
| `Caddyfile` | HTTPS, `{ecole}.mwangazaschool.com`, `parents.mwangazaschool.com`, `admin.mwangazaschool.com`, compression, adresse IP réelle du visiteur (Cloudflare) | 4.6.1 |
| `routes.caddy` | routes de chaque adresse, communes aux adresses du serveur : école (`/app`, `/api`, `/v`), portail, console (`/api`, `/admin` vers Django), site public sur le domaine nu (Django, seul indexé avec la connexion du portail ; autres espaces privés en `noindex`), cache des PWA ; requêtes vers Django limitées à 10 Mo (S.4) | 4.6.1 |
| `serveur/preparer.sh` | vrai serveur, une fois, en root par SSH (`make deploy-setup`) : mises à jour automatiques, Docker, ports 80 et 443, SSH par clé seulement | 4.6.3 |
| `serveur/deployer.sh` · `serveur/init.py` | vrai serveur piloté depuis la machine (`make deploy…`) : `init` (crée `serveur.env`, hors Git, secrets neufs ; ajoute à un fichier existant un secret apparu depuis), `git archive` envoyé par SSH dans `~/mwangaza/code` (mise à jour sur place), images construites par GitHub Actions (`.github/workflows/images.yml`, étiquette = `serveur/etiquette.sh`, PERF.5c) puis téléchargées (`CONSTRUIRE_SUR_SERVEUR=oui` : ancienne construction, secours), `up --wait --no-build`, `check`, super-admin, journaux | 4.6.3 |
| `.env.example` | modèle de `infra/.env` sur le serveur (domaine, certificat, secrets, clés des notifications Web Push : `manage.py webpush_keys`) | 4.6.1, 5.5.1 |
| `local.env` | valeurs publiques de l'essai sur la machine (`make prod-local`) | 4.6.1 |
| `certs/` | certificat d'origine Cloudflare (`origin.pem`, `origin.key`), hors Git | 4.6.3 |
| `backup/sauvegarde.sh` | tâche de chaque nuit (crontab du compte, posé par `make deploy`) et `make backup` : sessions expirées effacées, dump de la base et archive des fichiers chiffrés par `gpg` (clé `BACKUP_PASSPHRASE` ; sans clé : purge seule), rotation 30 / 7 jours ; `make restore` : essai dans une base à part comparée table par table, `remplacer=oui` pour remettre en service (l'ancienne base est gardée) ; journal sur le serveur : `journalctl -t mwangaza` ; copie vers Backblaze B2 par `rclone` et ping d'alerte (4.7.2) ; `fetch` rapatrie la dernière copie | 4.7.1 |

Essayer la production sur la machine : `make prod-local`, puis https://itig.localhost/app/ (certificat local de Caddy : accepter l'avertissement du navigateur) ; `make prod-local-stop` pour l'arrêter. La base de cet essai est vide (`make demo` est refusé hors développement).



Vrai serveur (AWS Lightsail, 4.6.3) : `serveur/serveur.env` (créé par `make deploy-init`) ; `docker-compose.production.yml` + `production/Caddyfile` (certificat joker par DNS Cloudflare, IP réelle du visiteur lue par Caddy) ; `make deploy-setup`, `make deploy`, `make deploy-check` (`A-FAIRE.md` § 9 ter, skill `/deployer` ; il lit aussi l'état public du domaine avec `serveur/domaine.py` : expiration, verrou de transfert, OPS.3 ; enregistrements e-mail, OPS.4, ci-dessous). Les démonstrations se créent dans la console, pas par `make demo`.

Serveur entier (OPS.2) : instantané automatique Lightsail de tout le disque chaque jour à 2:00 (heure de Goma), 7 gardés, réglé dans la console (rien dans ce dossier) ; en cas de perte : nouvelle instance depuis l'instantané, `make deploy-check ip=<IP provisoire>` (`curl --resolve`, certificat vérifié, DNS ignoré), puis IP statique déplacée (`A-FAIRE.md` § 9 ter, « Serveur perdu ou cassé »). Essai réel : 2026-10-17.

## E-mail du domaine (OPS.4)

Boîtes `contact@` et `support@mwangazaschool.com` chez **LWS** (2 comprises dans l'offre du domaine, 1 Go chacune) ; webmail : bouton « Webmail » du panneau LWS (`webmail.mwangazaschool.com` mène au serveur par le joker `*`). L'application n'envoie aucun e-mail (notifications dans l'app et push). DNS chez **Cloudflare**, nuage **gris** sur chaque ligne ; relevé du 2026-10-17 (`dig`), copié de la zone LWS à l'arrivée chez Cloudflare :

**Envoi par l'application (WEB.1d)** : seulement l'alerte d'une demande de démonstration au super-admin, par la boîte `contact@` (SMTP de LWS, port 465, SSL ; serveur `smtp`/`mail` donné par LWS) : `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_USER`, `DJANGO_EMAIL_PASSWORD` et `DJANGO_ALERT_EMAIL` (destinataire, ta boîte personnelle) dans `serveur.env` (ajoutées vides par `make deploy-init`) ; vides : aucun e-mail. `DJANGO_EMAIL_PORT=587` passe en STARTTLS.

| Type | Nom | Contenu | Rôle |
|---|---|---|---|
| MX | `@` | `mail.mwangazaschool.com`, priorité 10 | reçoit le courrier |
| A | `mail` | `83.229.19.97` (LWS) | serveur de messagerie ; `smtp`, `imap`, `pop` : CNAME vers lui (réglages du téléphone) |
| TXT | `@` | `v=spf1 mx:mwangazaschool.com a:mail.mwangazaschool.com a:mailphp.lws-hosting.com -all` | SPF : seuls les serveurs de LWS écrivent au nom du domaine ; **un seul** TXT `v=spf1` |
| TXT | `dkim._domainkey` | `v=DKIM1; k=rsa; p=MIGf…` (clé publique de LWS, RSA 1024) | signature de chaque message envoyé |
| TXT | `_dmarc` | `v=DMARC1; p=quarantine;` + `rua=…` ajouté par la gestion DMARC de Cloudflare (gratuite) | message qui échoue SPF et DKIM : en indésirables ; `p=reject` après deux semaines de rapports propres ; sans `sp=`, les sous-domaines des écoles suivent la même règle |

- `make deploy-check`, ligne « e-mail » (`serveur/domaine.py`, DNS sur HTTPS) : ATTENTION si MX, SPF ou DKIM manque, si deux SPF, ou si DMARC est absent ou en `none`.
- Un jour, un envoi d'e-mails par l'application (Amazon SES ou autre) : ajouter son `include:` au **même** SPF et sa clé DKIM **avant** le premier envoi, sinon DMARC le bloque.
- Autre fournisseur de boîtes : nouvelles valeurs MX, SPF et DKIM dans Cloudflare, et `DKIM_SELECTEUR` dans `serveur/domaine.py`.
- Ligne `ftp` (nuage orange) : reste de l'import de la zone LWS, inutile, à supprimer.

Voir `docs/03-architecture-technique.md` § 2 et § 9.

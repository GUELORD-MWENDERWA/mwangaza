# Plan PERF.5c — Images construites hors du serveur, dépôt prêt pour le privé

**But** : le serveur de 2 Go ne construit plus rien ; il télécharge des images faites par GitHub Actions
(GHCR), gratuit en public comme en privé (500 Mo, 2 000 min/mois).
**Hors périmètre** : passer vraiment le dépôt en privé (action de l'utilisateur) ; registre autre que GHCR.

**Critères** : `make deploy` = étiquette calculée du contenu (`backend/`, `frontend/`, Dockerfile, Caddyfile) →
si absente du registre, `images.yml` (workflow_dispatch) construit et publie → le serveur `pull`, re-étiquette,
`up --no-build`. Code inchangé = aucune construction. Jeton `GHCR_TOKEN` (lecture seule) dans `serveur.env`.
Nettoyage : 3 dernières versions par image. Secours : `CONSTRUIRE_SUR_SERVEUR=oui make deploy`.
CI : `timeout-minutes` partout, cache Chromium. Mesures de taille et de minutes dans `docs/claude/recherches/`.

**Tests** : script d'étiquette (stable si seul un `.md` change, change si `backend/` change) ;
`init.py` ajoute les clés GHCR. Pas de test Docker (CI et déploiement réel).
**Documents** : `A-FAIRE.md` (« Le jour où le dépôt repasse en privé », § 9), `infra/README.md`, `03` Journal,
`05`, `06`, `docs/exploitation.md`, skill `deployer`, `Dockerfile` (commentaires).
**Risques** : l'API de suppression des versions de paquets avec GITHUB_TOKEN d'un compte personnel
(étape tolérante) ; GHCR n'accepte que les jetons « classic » (`read:packages`) pour `docker login`.

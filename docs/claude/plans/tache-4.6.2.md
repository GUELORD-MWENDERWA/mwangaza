# Tâche 4.6.2 — Serveur de démonstration gratuit (Oracle Always Free + DuckDNS)

Choix de l'utilisateur (2026-10-04) : Oracle Cloud Always Free (VM ARM, 2 cœurs, 12 Go depuis juin 2026) + adresse DuckDNS ; chaque compte lie sa propre application d'authentification (plus de clé commune sur le serveur) ; rangement du dépôt dans la même PR.

- `infra/serveur/preparer.sh` (une fois) : mises à jour automatiques, Docker, ports 80/443 (règles iptables des images Oracle), SSH par clé seulement.
- `infra/serveur/deployer.sh` : `git archive origin/main` envoyé par SSH, `serveur.env` copié, images construites sur le serveur, `up --wait` ; aussi demo, superuser, logs.
- `infra/reseau/essai.py --serveur` : `infra/serveur/serveur.env` (hors Git : secrets, mot de passe de démo propre au serveur, adresse SSH), DuckDNS vers l'IP publique, page des QR codes.
- Même configuration Caddy que `make reseau` (`docker-compose.reseau.yml`, joker DuckDNS) ; `DJANGO_DEMO_PASSWORD` et page d'accueil choisie par variable.
- `settings.DEMO_PASSWORD` : défini → `make demo` met ce mot de passe, retire la clé commune et garde l'application liée par chacun.
- Gestion `TwoFactorSetup` : « Ajouter à mon application » (lien `otpauth://`, sur téléphone) et « Copier la clé ».
- Rangement : `PROMPT-DEMARRAGE.md` et `docs/claude/revues/` supprimés ; `CLAUDE.md` allégé (adresses, détail de `make demo` → `docs/claude/reference.md`) ; `A-FAIRE.md` nettoyé ; skill `/deployer`.
- `05` : 4.6.3 ajoutée (vrai domaine + Cloudflare, avant les vraies données, avec 4.7) ; elle fermera #34.

Tests : demo avec `DEMO_PASSWORD` (mot de passe du serveur, clé commune retirée, clé liée gardée) ; Vitest : lien et copie. `bash -n` des scripts, `caddy adapt` inchangé.
Risques : « Out of capacity » pour les VM ARM (réessayer, autre domaine de disponibilité) ; Oracle arrête une instance gratuite trop peu utilisée (compte Pay As You Go conseillé, reste à 0 $) ; build du front sur le serveur ARM (~10 min).

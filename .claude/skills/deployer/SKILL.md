---
name: deployer
description: Mettre en ligne, mettre à jour, vérifier ou dépanner le vrai serveur Mwangaza (AWS Lightsail, `mwangazaschool.com`, `make deploy…`). À utiliser quand l'utilisateur dit « déploie », « mets en ligne », « mets à jour le serveur », « le site ne répond plus », « erreur de certificat », ou veut montrer en ligne une PR fusionnée.
argument-hint: "[premiere-fois | mise-a-jour | etat | panne]"
---

# Serveur en ligne : $ARGUMENTS

Tâche 4.6.3. Pas à pas pour l'utilisateur : `A-FAIRE.md` § 9 ter ; commandes en détail : `docs/claude/reference.md` ; décisions : `docs/03-architecture-technique.md` § 9 et journal des décisions.

## Règles

- **C'est le vrai serveur** : des écoles réelles peuvent y avoir leurs données. Aucune donnée fictive dessus hors espaces de démonstration créés par la console (`make demo` est refusé dès qu'un espace réel existe, 4.22).
- **On met en ligne `main`**, fusionnée et CI verte. Une branche seulement à la demande de l'utilisateur : `make deploy ref=origin/<branche>`.
- **Demander avant d'agir sur le serveur** (visible de tous) : `make deploy`, redémarrage. Jamais de commande qui efface une base ou un volume.
- **`infra/serveur/serveur.env`** : hors Git, jamais affiché en entier (secrets), jamais recréé. Lire seulement `SERVEUR` et `MWANGAZA_DOMAIN` (`grep -E '^(SERVEUR|MWANGAZA_DOMAIN)='`). Perdre `DJANGO_SECRET_KEY`, `BACKUP_PASSPHRASE` ou les clés Web Push est irréparable après de vraies données.
- Un espace de démonstration par visiteur (4.17.2) : console (`https://admin.mwangazaschool.com/`) → Écoles → « Nouvelle école », type Démonstration ; sa fiche d'accès (PDF) donne adresses, comptes et mot de passe, « Remettre à zéro » avant le visiteur suivant.

## Première fois

`make deploy-init` (crée `serveur.env`, dit quoi remplir), `make deploy-setup` (une fois), `make deploy` (images construites par GitHub Actions puis téléchargées : ≈ 15 min la première fois, quelques minutes ensuite ; `GHCR_USER` et `GHCR_TOKEN` de `serveur.env` d'abord, `A-FAIRE.md` § 9 quinquies), `make deploy-check`, puis `make deploy-superuser`.

## Mise à jour

`git switch main && git pull`, puis `make deploy` : code envoyé, images publiées par GitHub Actions seulement si le code des images a changé (`gh` connecté ; secours `CONSTRUIRE_SUR_SERVEUR=oui make deploy`) et téléchargées pendant que l'ancienne version reste en ligne, migrations puis droits du compte PostgreSQL de l'application par le conteneur `migrate` (S.5 : Django et Celery n'ont que le compte `mwangaza_app`, lignes seulement), tâche de chaque nuit remise dans le crontab du compte (`infra/backup/sauvegarde.sh`). Puis `make deploy-check`.

## Panne

| Signe | Cause probable | Que faire |
|---|---|---|
| `Remplis SERVEUR…` | `serveur.env` incomplet | le remplir (§ 9 ter) |
| SSH : délai dépassé | instance arrêtée ou adresse IP changée | la démarrer dans la console Lightsail ; IP changée → corriger `SERVEUR` et le DNS Cloudflare |
| SSH marche, pas le site | ports fermés | onglet « Mise en réseau » de Lightsail (80, 443) ; `make deploy-ssh` puis `sudo iptables -L INPUT -n \| grep -E 'dpt:(80\|443)'` ; relancer `make deploy-setup` |
| Erreur de certificat | jeton Cloudflare faux, ou trop de demandes à Let's Encrypt | `make deploy-logs service=caddy` ; corriger `CLOUDFLARE_API_TOKEN` puis `make deploy` ; limite atteinte : attendre, ne pas relancer en boucle |
| `POSTGRES_APP_PASSWORD manque dans serveur.env` | `serveur.env` créé avant S.5 | `make deploy-init` (ajoute la ligne), puis `make deploy` ; rappeler de mettre à jour la copie en lieu sûr |
| `service "migrate" didn't complete successfully` | migration en échec ; l'ancienne version reste en ligne | `make deploy-logs service=migrate` |
| `permission denied for table…` ou `must be owner of…` dans les journaux de Django | du code qui touche à la structure hors d'une migration, ou droits pas redonnés après une restauration à la main | corriger le code (migration) ; droits : `make deploy` relance `migrate` |
| Page blanche ou 502 | Django pas prêt (réglage) | `make deploy-logs service=django` |
| Tout injoignable (HTTPS et SSH en délai dépassé), instance « Running » | machine figée : mémoire saturée (construction sans swap) | console Lightsail : *Metrics*, SSH du navigateur ; `free -h`, `swapon --show`, `sudo journalctl -k \| grep -iE 'oom\|killed process'`, `sudo iptables -S INPUT` (règle `--dport 22`) ; navigateur muet : *Reboot* (jamais Stop/Start sans IP statique) ; puis `make deploy-setup` (swap 2 Go, SSH protégé) |
| Alerte « sauvegarde manquante » (Healthchecks) | clé B2 fausse, bucket plein, `rclone` absent (`make deploy-setup` le pose) | `make deploy-backup` : l'erreur s'affiche ; journal de la nuit : `make deploy-ssh` puis `journalctl -t mwangaza` ; serveur perdu : `make deploy-backup cmd=fetch` |
| `GHCR_USER et GHCR_TOKEN manquent` / `Construction en échec` | jeton absent ou expiré ; construction d'Actions en échec | `A-FAIRE.md` § 9 quinquies ; `gh run view <n> --log-failed` ; secours `CONSTRUIRE_SUR_SERVEUR=oui make deploy` |
| Disque plein | anciennes images (supprimées à chaque `make deploy`) ou cache de construction du secours | `make deploy-ssh` puis `docker system df` ; tout le cache : `docker builder prune -f` (la construction suivante sera plus longue) |

Après une mise en ligne ou une panne réglée : `/noter` (journal de `docs/06-suivi.md`) et `A-FAIRE.md` si l'utilisateur a quelque chose à faire.

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

`make deploy-init` (crée `serveur.env`, dit quoi remplir), `make deploy-setup` (une fois), `make deploy` (images construites par GitHub Actions puis téléchargées : ≈ 15 min la première fois, quelques minutes ensuite ; `GHCR_USER` et `GHCR_TOKEN` de `serveur.env` d'abord, `A-FAIRE.md` § 9 quinquies), `make deploy-check` (`ip=<IP>` : une instance pas encore derrière le DNS ; lignes « domaine » (expiration, verrou de transfert) et « e-mail » (MX, SPF, DKIM, DMARC ; `infra/README.md` « E-mail du domaine »), avertissement seulement), puis `make deploy-superuser`.

## Mise à jour

`git switch main && git pull`, puis `make deploy` : code envoyé, images publiées par GitHub Actions seulement si le code des images a changé (`gh` connecté ; secours `CONSTRUIRE_SUR_SERVEUR=oui make deploy`) et téléchargées pendant que l'ancienne version reste en ligne, migrations puis droits du compte PostgreSQL de l'application par le conteneur `migrate` (S.5 : Django et Celery n'ont que le compte `mwangaza_app`, lignes seulement), tâche de chaque nuit remise dans le crontab du compte (`infra/backup/sauvegarde.sh`). Puis `make deploy-check`.

## Panne

| Signe | Cause probable | Que faire |
|---|---|---|
| `Remplis SERVEUR…` | `serveur.env` incomplet | le remplir (§ 9 ter) |
| SSH : délai dépassé | instance arrêtée ou adresse IP changée | la démarrer dans la console Lightsail ; IP changée → corriger `SERVEUR` et le DNS Cloudflare ; instance qui ne repart pas : « Serveur perdu ou cassé » ci-dessous |
| SSH marche, pas le site | ports fermés | onglet « Mise en réseau » de Lightsail (80, 443) ; `make deploy-ssh` puis `sudo iptables -L INPUT -n \| grep -E 'dpt:(80\|443)'` ; relancer `make deploy-setup` |
| Erreur de certificat | jeton Cloudflare faux, ou trop de demandes à Let's Encrypt | `make deploy-logs service=caddy` ; corriger `CLOUDFLARE_API_TOKEN` puis `make deploy` ; limite atteinte : attendre, ne pas relancer en boucle |
| `POSTGRES_APP_PASSWORD manque dans serveur.env` | `serveur.env` créé avant S.5 | `make deploy-init` (ajoute la ligne), puis `make deploy` ; rappeler de mettre à jour la copie en lieu sûr |
| `service "migrate" didn't complete successfully` | migration en échec ; l'ancienne version reste en ligne | `make deploy-logs service=migrate` |
| `permission denied for table…` ou `must be owner of…` dans les journaux de Django | du code qui touche à la structure hors d'une migration, ou droits pas redonnés après une restauration à la main | corriger le code (migration) ; droits : `make deploy` relance `migrate` |
| Page blanche ou 502 | Django pas prêt (réglage) | `make deploy-logs service=django` |
| Carte Santé : peu de mémoire libre | poids fixe des programmes ou un processus hors de l'application | `make deploy-memoire` (machine, conteneurs, 15 processus les plus lourds) ; comparer à `docs/exploitation.md` |
| Tout injoignable (HTTPS et SSH en délai dépassé), instance « Running » | machine figée : mémoire saturée (construction sans swap) | console Lightsail : *Metrics*, SSH du navigateur ; `free -h`, `swapon --show`, `sudo journalctl -k \| grep -iE 'oom\|killed process'`, `sudo iptables -S INPUT` (règle `--dport 22`) ; navigateur muet : *Reboot* (jamais Stop/Start sans IP statique) ; puis `make deploy-setup` (swap 2 Go, SSH protégé) |
| Alerte « sauvegarde manquante » (Healthchecks) | clé B2 fausse, bucket plein, `rclone` absent (`make deploy-setup` le pose) | `make deploy-backup` : l'erreur s'affiche ; journal de la nuit : `make deploy-ssh` puis `journalctl -t mwangaza` ; serveur perdu : « Serveur perdu ou cassé » ci-dessous |
| `GHCR_USER et GHCR_TOKEN manquent` / `Construction en échec` | jeton absent ou expiré ; construction d'Actions en échec | `A-FAIRE.md` § 9 quinquies ; `gh run view <n> --log-failed` ; secours `CONSTRUIRE_SUR_SERVEUR=oui make deploy` |
| Disque plein | anciennes images (supprimées à chaque `make deploy`) ou cache de construction du secours | `make deploy-ssh` puis `docker system df` ; tout le cache : `docker builder prune -f` (la construction suivante sera plus longue) |

## Serveur perdu ou cassé

Deux chemins, pas à pas pour l'utilisateur : `A-FAIRE.md` § 9 ter, « Serveur perdu ou cassé » (OPS.2). Lui fait les clics dans la console Lightsail ; Claude vérifie et guide.
- **(a) Instantané Lightsail** (instance cassée, compte AWS accessible ; ≈ 15 min) : *Create new instance* depuis le dernier instantané automatique (2:00, 7 gardés) → ajouter HTTPS 443 en IPv4 et IPv6 (le pare-feu ne suit pas l'instantané) → `make deploy-check ip=<IP provisoire>` vert → IP statique détachée de l'ancienne, attachée à la nouvelle → `make deploy-check` → ancienne arrêtée (*Stop*), supprimée seulement après le premier instantané de la nouvelle (la supprimer efface ses instantanés) ; instantanés automatiques et alarmes à refaire sur la nouvelle.
- **(b) Backblaze** (compte bloqué, région en panne ; ≈ 1 h) : serveur neuf, `SERVEUR` et DNS Cloudflare mis à jour, `make deploy-setup`, `make deploy`, `make deploy-backup cmd=fetch`, `cmd="restore --remplacer"`.
- Ancienne encore joignable en SSH : `make deploy-backup` avant la bascule, puis `fetch` et `restore --remplacer` sur la nouvelle (rien de perdu depuis la nuit).
- Une copie qui tourne lance aussi la sauvegarde de 0 h 30 et le planificateur (relances) : un essai se fait de jour et la copie est supprimée dans l'heure.
- Le jour où le pare-feu est limité à Cloudflare (`A-FAIRE.md` 5 ter) : revoir l'étape du 443 et `check ip=` (depuis la machine, le 443 serait refusé).

Après une mise en ligne ou une panne réglée : `/noter` (journal de `docs/06-suivi.md`) et `A-FAIRE.md` si l'utilisateur a quelque chose à faire.

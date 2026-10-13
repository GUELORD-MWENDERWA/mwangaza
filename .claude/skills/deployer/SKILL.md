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

`make deploy-init` (crée `serveur.env`, dit quoi remplir), `make deploy-setup` (une fois), `make deploy` (≈ 15 min : images construites sur le serveur), `make deploy-check`, puis `make deploy-superuser`.

## Mise à jour

`git switch main && git pull`, puis `make deploy` : code envoyé, images construites pendant que l'ancienne version reste en ligne, migrations au démarrage de Django, tâche de chaque nuit remise dans le crontab du compte (`infra/backup/sauvegarde.sh`). Puis `make deploy-check`.

## Panne

| Signe | Cause probable | Que faire |
|---|---|---|
| `Remplis SERVEUR…` | `serveur.env` incomplet | le remplir (§ 9 ter) |
| SSH : délai dépassé | instance arrêtée ou adresse IP changée | la démarrer dans la console Lightsail ; IP changée → corriger `SERVEUR` et le DNS Cloudflare |
| SSH marche, pas le site | ports fermés | onglet « Mise en réseau » de Lightsail (80, 443) ; `make deploy-ssh` puis `sudo iptables -L INPUT -n \| grep -E 'dpt:(80\|443)'` ; relancer `make deploy-setup` |
| Erreur de certificat | jeton Cloudflare faux, ou trop de demandes à Let's Encrypt | `make deploy-logs service=caddy` ; corriger `CLOUDFLARE_API_TOKEN` puis `make deploy` ; limite atteinte : attendre, ne pas relancer en boucle |
| Page blanche ou 502 | Django pas prêt (migration, réglage) | `make deploy-logs service=django` |
| Alerte « sauvegarde manquante » (Healthchecks) | clé B2 fausse, bucket plein, `rclone` absent (`make deploy-setup` le pose) | `make deploy-backup` : l'erreur s'affiche ; journal de la nuit : `make deploy-ssh` puis `journalctl -t mwangaza` ; serveur perdu : `make deploy-backup cmd=fetch` |
| Disque plein | anciennes images | `make deploy-ssh` puis `docker system df` et `docker builder prune -f` |

Après une mise en ligne ou une panne réglée : `/noter` (journal de `docs/06-suivi.md`) et `A-FAIRE.md` si l'utilisateur a quelque chose à faire.

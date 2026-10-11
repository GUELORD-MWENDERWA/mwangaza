---
name: deployer
description: Mettre en ligne, mettre à jour, vérifier ou dépanner le serveur de démonstration Mwangaza (Oracle Cloud « Always Free » + adresse DuckDNS, `make deploy…`). À utiliser quand l'utilisateur dit « déploie », « mets en ligne », « mets à jour le serveur », « remets la démo à zéro », « le site ne répond plus », « erreur de certificat », ou veut montrer en ligne une PR fusionnée.
argument-hint: "[premiere-fois | mise-a-jour | demo | etat | panne]"
---

# Serveur de démonstration : $ARGUMENTS

Tâche 4.6.2. Pas à pas pour l'utilisateur : `A-FAIRE.md` § 9 ter ; commandes en détail : `docs/claude/reference.md` ; décisions : `docs/03-architecture-technique.md` § 9 et journal des décisions.

## Règles

- **Données fictives seulement.** Jamais de vraie école sur ce serveur : elle attend le vrai domaine (4.6.3) et les sauvegardes (4.7). Si on le demande, le rappeler et proposer ces tâches.
- **On met en ligne `main`**, fusionnée et CI verte. Une branche seulement à la demande de l'utilisateur : `make deploy ref=origin/<branche>`.
- **Demander avant d'agir sur le serveur** (visible de tous) : `make deploy`, `make deploy-demo` (remet la démo à zéro, efface les essais faits dessus ; refusé dès que le serveur a un espace réel, 4.22 : démonstrations par la console), redémarrage. Jamais `docker compose down --volumes` ni `docker volume rm` : la base serait effacée.
- **`infra/serveur/serveur.env`** : hors Git, jamais affiché en entier (secrets), jamais recréé. Lire seulement `SERVEUR` et `MWANGAZA_DOMAIN` (`grep -E '^(SERVEUR|MWANGAZA_DOMAIN)='`). Perdre `DJANGO_SECRET_KEY` oblige chacun à relier son application d'authentification ; perdre les clés Web Push, à réabonner chaque appareil. L'utilisateur en garde une copie en lieu sûr.
- Un espace de démonstration par visiteur (4.17.2) : console → Écoles → « Nouvelle école », type Démonstration ; sa fiche d'accès (PDF) donne adresses, comptes et mot de passe, « Remettre à zéro » avant le visiteur suivant ; au plus `DJANGO_DEMO_SPACES_MAX` espaces (5, ceux de `make deploy-demo` compris), à changer dans `serveur.env`.
- Comptes fictifs : mot de passe `DJANGO_DEMO_PASSWORD` (à donner seulement à qui l'utilisateur montre l'application) ; pas de double authentification (espaces de démonstration, 4.17.1) et pas de super-admin fictif : la console s'ouvre avec le compte créé par `make deploy-superuser`, qui lie son application à la première connexion. Super-admin bloqué (téléphone perdu) : console → Comptes → « Réinitialiser la double authentification », depuis un autre super-admin.

## Première fois

L'utilisateur fait `A-FAIRE.md` § 9 ter étapes 1 à 4 (compte Oracle, VM ARM Ubuntu 24.04 avec sa clé SSH, ports 80 et 443 dans la liste de sécurité, adresse DuckDNS à part). Puis : `make deploy-setup` (crée `serveur.env` et dit quoi remplir ; relancer une fois rempli), `make deploy` (premier build ≈ 10 à 15 min sur ARM), `make deploy-demo`, `make deploy-superuser` (le compte de l'utilisateur pour la console : il n'y a pas de super-admin fictif hors développement), puis ouvrir `https://www.<nom>.duckdns.org/`.

## Mise à jour

`git switch main && git pull`, puis `make deploy` : code envoyé, images construites pendant que l'ancienne version reste en ligne, migrations au démarrage de Django. Vérifier : `make deploy-logs` (première ligne : commit en ligne, à comparer à `git rev-parse --short origin/main`) et `curl -s https://admin.<nom>.duckdns.org/api/health/`.

## Panne

| Signe | Cause probable | Que faire |
|---|---|---|
| `Remplis SERVEUR…` | `serveur.env` incomplet | le remplir (§ 9 ter étape 5) |
| SSH : délai dépassé | instance arrêtée par Oracle (peu utilisée pendant 7 jours) ou adresse IP changée | la démarrer sur le site d'Oracle ; IP changée → corriger `SERVEUR`, puis `make deploy` (met DuckDNS à jour) |
| SSH marche, pas le site | ports fermés | liste de sécurité (80, 443) ; `make deploy-ssh` puis `sudo iptables -L INPUT -n \| grep -E 'dpt:(80\|443)'` ; relancer `make deploy-setup` |
| Erreur de certificat | jeton DuckDNS faux, ou trop de demandes à Let's Encrypt | `make deploy-logs service=caddy` ; corriger `DUCKDNS_TOKEN` puis `make deploy` ; limite atteinte : attendre (une semaine au plus), ne pas relancer en boucle |
| Page blanche ou 502 | Django pas prêt (migration, réglage) | `make deploy-logs service=django` |
| Disque plein | anciennes images | `make deploy-ssh` puis `docker system df` et `docker builder prune -f` |

Après une première mise en ligne ou une panne réglée : `/noter` (journal de `docs/06-suivi.md`) et `A-FAIRE.md` si l'utilisateur a quelque chose à faire.

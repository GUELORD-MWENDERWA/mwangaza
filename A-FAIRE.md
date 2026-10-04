# À faire de ton côté

Ce que **toi seul** peux faire, comment le faire, et toutes les commandes du projet.
Claude ne peut pas : installer avec `sudo`, fusionner une PR, parler à l'ITIG, acheter, créer des comptes. Il met ce fichier à jour dès qu'une action t'attend ou qu'une commande est ajoutée.

Ce qui manque en détail (maquettes, informations ITIG, décisions) : [`docs/07-a-fournir.md`](docs/07-a-fournir.md). Ici : **quoi faire, dans quel ordre, avec quelles commandes**.

Dernière mise à jour : 2026-09-26 (PR #83 fusionnée ; tâche 1.5 : super-admin, session support, paramètres de l'école).

## Maintenant

| # | Action | Temps | Fait |
|:-:|---|---|:-:|
| 1 | [Fusionner la PR #75](#1-fusionner-la-pr-75) (documents, 61 maquettes, ce fichier) | 5 min | [x] |
| 2 | [Rouvrir VS Code dans `~/Projets/mwangaza`](#2-le-dossier-sappelle-maintenant-mwangaza) | 1 min | [x] |
| 3 | [Installer Docker](#3-installer-docker) | 15 min | [x] |
| 3 bis | **[Se déconnecter puis se reconnecter](#3-bis-se-déconnecter-puis-se-reconnecter)** (sinon `docker` répond `permission denied`) | 2 min | [x] |
| 4 | [Créer le fichier `.env`](#4-créer-le-fichier-env) | 2 min | [x] |
| 5 | [Vérifier que tout marche](#5-vérifier-que-tout-marche) | 5 min | [x] |
| 5 bis | [Fusionner la PR #76 (correction du `.env`)](#5-bis-fusionner-la-pr-de-correction-du-env) | 2 min | [x] |
| 5 ter | [Fusionner la PR #77 (correction de `make dev`)](#5-ter-fusionner-la-pr-de-correction-de-make-dev) | 2 min | [x] |
| 6 | [Donner tes décisions](#6-tes-décisions) : nom et domaine (Q9), questions Q1 à Q11 | 10 min | [x] |
| 7 | [Relire et fusionner la PR des décisions (#78)](#7-fusionner-la-pr-des-décisions), puis celle de la tâche 0.2 (#79) — dans cet ordre | 15 min | [x] |
| 8 | Après la fusion de la 0.2 : `make install` une fois (nouveaux outils ESLint, Prettier, Vitest, ruff, et contrôles avant chaque commit) — relancé par Claude sur ta machine le 2026-09-26 | 3 min | [x] |
| 9 | [Relire et fusionner la PR #80 (tâche 1.1)](#10-comment-relire-et-fusionner-une-pr) — fusionnée le 2026-09-26 | 15 min | [x] |
| 10 | [Relire et fusionner la PR #81 (tâche 1.2)](#10-comment-relire-et-fusionner-une-pr) (comptes, rôles, permissions), puis `make reset-db` une fois — fusionnée le 2026-09-26 | 20 min | [x] |
| 11 | **[Relire et fusionner la PR #82 (tâche 1.3)](#10-comment-relire-et-fusionner-une-pr)** (connexion, double authentification) : suivre « À tester toi-même », **fusionner sur GitHub**, puis `git switch main && git pull && make install && make migrate && make demo` (`make install` : 2 nouvelles dépendances Python, Argon2 et `cryptography`) — fusionnée le 2026-09-26 | 25 min | [x] |
| 12 | **[Relire et fusionner la PR #83 (tâche 1.4)](#10-comment-relire-et-fusionner-une-pr)** (journal d'audit) : suivre « À tester toi-même », **fusionner sur GitHub**, puis `git switch main && git pull && make migrate` (pas de nouvelle dépendance) — fusionnée le 2026-09-26 | 20 min | [x] |
| 13 | **[Relire et fusionner la PR #84 (tâche 1.5)](#10-comment-relire-et-fusionner-une-pr)** (super-admin : écoles, session support, double authentification de l'administration, paramètres de l'école) : suivre « À tester toi-même », **fusionner sur GitHub**, puis `git switch main && git pull && make migrate && make demo` (pas de nouvelle dépendance ; `make demo` active la double authentification du super-admin de démonstration) — fusionnée le 2026-09-26 | 25 min | [x] |
| 14 | **[Relire et fusionner la PR #85 (tâche 1.6)](#10-comment-relire-et-fusionner-une-pr)** (premiers écrans : connexion, menu, Mon compte, session support) : suivre « À tester toi-même », **fusionner sur GitHub**, puis `git switch main && git pull && make install` (**nouvelles dépendances du front** : React Router, TanStack Query, Tailwind, composants, formulaires, PWA, client de l'API, QR code, outils de test) ; pour `make test-e2e`, une fois : `cd frontend && pnpm exec playwright install chromium` (Chromium de Playwright, ~115 Mo) | 30 min | [x] |
| 15 | **[Relire et fusionner la PR #86 (tâche 1.7)](#10-comment-relire-et-fusionner-une-pr)** (organisation scolaire ; écrans Paramètres de l'école, Organisation scolaire, Comptes du personnel, Rôles et permissions, Journal d'audit) : suivre « À tester toi-même », **fusionner sur GitHub**, puis `git switch main && git pull && make migrate && make demo` (une migration : années, périodes, niveaux, options, classes, format du matricule) | 30 min | [x] |
| 16 | Installer gettext une fois : `sudo apt install gettext` (outils des traductions du serveur, pour `make messages`) — fait le 2026-09-27 | 2 min | [x] |
| 17 | [Mise en ligne : hébergement et domaine](#9-mise-en-ligne-462--comptes-et-achats) (§ 9) : **quand tu le décides**, ne bloque plus rien (2026-10-02) — la production est prête et s'essaie sur ta machine (`make prod-local`) ; démonstration gratuite possible, vraies données d'une école seulement avec le vrai domaine | 1 h | [ ] |
| 18 | **Relire et fusionner la PR du nouveau découpage des versions** (branche `docs/plan-versions`) — fusionnée le 2026-10-02 ; jalons V1.3, V1.4 et issues renumérotées sur GitHub par Claude : V1.0 close avec 4.9 et 4.10, puis V1.1 plateforme et notifications, V1.2 carte et présences, V1.3 paie, V1.4 notes | 15 min | [x] |
| 19 | **Relire et fusionner la PR de la tâche 4.9** (invitation des familles au portail) : suivre « À tester toi-même » de la PR | 15 min | [x] |
| 20 | **Relire et fusionner la PR de la tâche 4.10** (guide de la V1.0 en PDF) : lire `docs/guide/guide-v1.0.pdf` dans la PR ; ensuite tu peux l'envoyer aux écoles — fusionnée le 2026-10-02 | 20 min | [x] |
| 21 | **Relire et fusionner la PR de la tâche 5.1** (identité de la plateforme : nom, logo, couleurs, support, mentions légales sans code) : suivre « À tester toi-même », puis `git switch main && git pull && make migrate && make demo` — fusionnée le 2026-10-02 | 20 min | [x] |
| 22 | **Relire et fusionner la PR de la tâche 5.2.1** (console de la plateforme : connexion du super-admin, tableau de bord de toutes les écoles, santé du serveur) : suivre « À tester toi-même », puis `git switch main && git pull && make install` — fusionnée le 2026-10-02 | 15 min | [x] |
| 23 | **Relire et fusionner la PR de la tâche 5.2.2** (écran « Identité de la plateforme » de la console, journal de la plateforme) : suivre « À tester toi-même », puis `git switch main && git pull && make migrate` ; si `make dev` tournait déjà avant la 5.2.1, `make stop && make dev` pour ouvrir la console (port 5175) — fusionnée le 2026-10-03 | 15 min | [x] |
| 24 | **Relire et fusionner la PR de la tâche 5.3** (console : écoles — liste, nouvelle école avec son directeur, fiche, abonnement, suspendre / réactiver ; administration Django des écoles en lecture seule) : suivre « À tester toi-même », puis `git switch main && git pull` — fusionnée le 2026-10-03, comme la 5.4.1 (comptes) | 15 min | [x] |
| 25 | **Relire et fusionner la PR de la tâche 5.4.2** (console : appareils de toutes les écoles avec « Déconnecter », journal de la plateforme avec filtres, sessions support) : suivre « À tester toi-même », puis `git switch main && git pull` ; si les nouveaux écrans affichent des clés brutes (`console.devices.title`), redémarrer le front : `docker restart mwangaza-dev-frontend-1` — fusionnée le 2026-10-03 | 15 min | [x] |
| 26 | **Relire et fusionner la PR de la tâche 5.4.3** (annonces de la plateforme : rédigées dans la console, bandeau et liste dans la Gestion) : suivre « À tester toi-même », puis `git switch main && git pull && make migrate && make demo` ; si les nouveaux écrans affichent des clés brutes (`platformNews.read`), `docker restart mwangaza-dev-frontend-1` — fusionnée le 2026-10-03 | 15 min | [x] |
| 27 | **Relire et fusionner la PR de la tâche 5.5.1** (notifications : cloche et centre de notifications dans la Gestion, notifications sur l'écran même application fermée, préférences ; une annonce de la plateforme notifie le personnel) : suivre « À tester toi-même », puis `git switch main && git pull && make install && make migrate && make demo` (`make install` : nouvelle dépendance Python `pywebpush`) ; avec `make dev`, l'arrêter (Ctrl+C) et le relancer : l'image de Django est reconstruite avec `pywebpush` — fusionnée le 2026-10-03 | 20 min | [x] |
| 28 | **Relire et fusionner la PR de la tâche 4.11** (essai de l'application construite sur plusieurs appareils : téléphones, autre PC, iPhone, avec un vrai certificat) : lire « À tester toi-même » de la PR, puis `git switch main && git pull` ; pour l'essai lui-même, [§ 9 bis](#9-bis-essai-sur-plusieurs-appareils-411) quand tu veux montrer l'application (compte DuckDNS une fois, puis `make reseau`) | 30 min | [ ] |

À chaque PR : [comment la relire et la fusionner](#10-comment-relire-et-fusionner-une-pr) (§ 10). La V1.0 est faite, guide PDF compris (`docs/guide/guide-v1.0.pdf`) ; la V1.1 avance (5.1 à 5.5.1 faites) ; essai sur plusieurs appareils (4.11) : PR à fusionner, puis [§ 9 bis](#9-bis-essai-sur-plusieurs-appareils-411). Mise en ligne quand tu veux (ligne 17). [Rien à demander à l'ITIG](#8-litig--rien-à-demander).

---

### 1. Fusionner la PR #75

**Ce qui s'est passé** : la PR #73 (inventaire de ce qui manque) a été fermée sans être fusionnée, et la PR #74 (les 20 maquettes manquantes) a été fusionnée dans la branche `docs/inventaire-manques`, **pas dans `main`**. Ce travail n'était donc pas sur `main`. La PR #75 le ramène sur `main`, avec ce fichier. La fusionner = valider les maquettes dessinées (remarque sur un écran : commentaire sur la PR, Claude corrige avant de coder l'écran).

**Sur GitHub** : ouvrir la PR → onglet *Files changed* pour relire → *Merge pull request* → *Confirm merge* → *Delete branch*.

> Avant de fusionner une PR, vérifier en haut de la page : **`base: main`**. Si la base est une autre branche, ne pas fusionner : demander à Claude.

**Ou dans le terminal** :

```bash
gh pr merge 75 --merge --delete-branch
git switch main && git pull
```

Puis, pour effacer les anciennes branches déjà reprises dans #75 (facultatif) :

```bash
git branch -D docs/inventaire-manques docs/a-faire
git push origin --delete docs/inventaire-manques docs/maquettes-manquantes tache/0.1-monorepo
git fetch --prune
```

### 2. Le dossier s'appelle maintenant `mwangaza`

Claude a renommé `~/Projets/saas` en **`~/Projets/mwangaza`** (même nom que le dépôt GitHub). La mémoire de Claude Code a été copiée vers le nouveau chemin.

- VS Code : *Fichier → Ouvrir le dossier…* → `~/Projets/mwangaza`, ou dans un terminal : `code ~/Projets/mwangaza`.
- Relancer Claude Code depuis ce dossier (il demandera peut-être d'accepter le dossier : oui).
- Ignorer `saas` dans la liste des dossiers récents.

Si un jour tu déplaces encore le dossier : `rm -rf backend/.venv && make install` (l'environnement Python contient des chemins absolus).

### 3. Installer Docker

Pour Ubuntu 24.04 (ta machine), d'après la documentation officielle de Docker :

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

**Fait** (Docker 29.8, Compose 5.5). Reste l'étape 3 bis.

### 3 bis. Se déconnecter puis se reconnecter

La commande `sudo usermod -aG docker $USER` t'a bien ajouté au groupe `docker`, mais ta session ouverte ne le sait pas encore : `docker ps` répond `permission denied … docker.sock`.

- **Se déconnecter** de la session Ubuntu (menu en haut à droite → *Se déconnecter*) puis se reconnecter, **ou redémarrer** l'ordinateur.
- Rouvrir VS Code dans `~/Projets/mwangaza`, puis dans un terminal :

```bash
id -nG | grep -w docker      # doit afficher une ligne contenant « docker »
docker run --rm hello-world  # doit afficher « Hello from Docker! »
```

En attendant (sans te déconnecter), dans un seul terminal : `newgrp docker`, puis les commandes Docker dans ce même terminal.

**Sans Docker** (solution de secours) : utiliser le PostgreSQL déjà installé sur ta machine (port 5432).

```bash
sudo -u postgres psql -c "CREATE ROLE mwangaza LOGIN CREATEDB PASSWORD 'mwangaza';"
sudo -u postgres createdb -O mwangaza mwangaza
```

Puis mettre `POSTGRES_PORT=5432` dans `.env` (étape 4). Redis n'est pas nécessaire tant que `CELERY_TASK_ALWAYS_EAGER=true`. Mais `make dev` (tout dans Docker) et les tâches suivantes (Celery, Playwright) seront plus simples avec Docker.

### 4. Créer le fichier `.env`

**Fait.** Tu avais lancé `cp .env.example .env` : c'était la bonne commande. La valeur de `DJANGO_SECRET_KEY` restait vide parce que l'ancienne consigne demandait de **copier-coller à la main** la clé affichée par `python3 …` ; rien ne l'écrivait dans le fichier. Et une clé vide faisait planter Django (`The SECRET_KEY setting must not be empty`). Claude a écrit une clé dans ton `.env` (sans l'afficher) et corrigé le code : une ligne laissée vide vaut maintenant « absente », Django prend alors la clé de développement.

Ton `.env` contient maintenant :

| Variable | Valeur | À changer ? |
|---|---|---|
| `DJANGO_SECRET_KEY` | une clé générée (longue suite de caractères) | non ; vide marcherait aussi sur ta machine |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `mwangaza` | non (ce sont ceux de la base Docker) |
| `POSTGRES_HOST`, `POSTGRES_PORT` | `localhost`, `5433` | non ; `5432` seulement si tu utilises le PostgreSQL installé sur la machine (solution sans Docker) |
| `REDIS_URL` | `redis://localhost:6379/0` | non |
| `CELERY_TASK_ALWAYS_EAGER` | `true` | non |

**Sur un autre ordinateur** : `cp .env.example .env` suffit, rien à remplir.

`.env` n'est jamais commité (il est dans `.gitignore`). Aucun mot de passe, aucune clé dans le dépôt ni dans une conversation avec Claude.

### 5. Vérifier que tout marche

**Déjà vérifié par Claude le 2026-09-26** sur ta machine : `make services`, `make test` (7 tests backend passés, types du front OK), `make migrate` (tables créées), `make dev-local` et `make dev` (les trois adresses ci-dessous répondent). Les conteneurs sont arrêtés.

À refaire **toi-même une fois, après les étapes 5 bis et 5 ter**, pour être sûr que tes commandes marchent. Depuis `~/Projets/mwangaza`, dans le terminal de VS Code :

```bash
git switch main && git pull   # après les fusions 5 bis et 5 ter
make services    # PostgreSQL (port 5433) et Redis dans Docker ; déjà lancés = « Running »
make test        # attendu : « 7 passed », puis « Done » pour gestion et portail
make migrate     # attendu : « No migrations to apply » (déjà fait)
make dev-local   # Django et Vite sur ta machine ; laisser tourner, Ctrl+C pour arrêter
```

Pendant que `make dev-local` tourne, ouvrir dans Chrome ou Firefox :

- http://localhost:8000/api/health/ → `{"status": "ok", "database": "ok"}`
- http://itig.localhost:5173/app/ → application Gestion (encore vide)
- http://localhost:5174/ → Portail (encore vide)

Ensuite, essayer une fois **tout dans Docker** : Ctrl+C, puis `make dev` (images déjà téléchargées : prêt en 30 s environ ; attendre les lignes `VITE … ready`), mêmes adresses. Ctrl+C puis `make stop` pour arrêter.

Dire le résultat à Claude : « tout marche », ou coller le message d'erreur.

**Fait** (2026-09-26 : `make dev` marche chez toi).

### 5 bis. Fusionner la PR de correction du `.env`

PR #76, branche `fix/env-valeurs-vides` : une variable vide dans `.env` ne fait plus planter Django, `.env.example` explique la clé, ce fichier est à jour. Sur GitHub : vérifier **`base: main`** → *Merge pull request* → *Delete branch*. Ou :

```bash
gh pr merge 76 --merge --delete-branch
git switch main && git pull
```

**Fait.**

### 5 ter. Fusionner la PR de correction de `make dev`

Le premier essai de `make dev` a montré deux défauts : le conteneur du front s'arrêtait aussitôt (`pnpm: not found`), et il réinstallait toutes les dépendances du front à chaque lancement, en écrasant celles de ta machine. Corrigé sur la branche `fix/docker-front` : le conteneur utilise les dépendances installées sur ta machine, et `make dev` lance `pnpm install` avant de démarrer Docker. Même démarche qu'en 5 bis (vérifier **`base: main`**) : `gh pr merge 77 --merge --delete-branch` puis `git switch main && git pull`.

**Fait.**

### 6. Tes décisions

**Fait** le 2026-09-26. Tes réponses sont notées dans le journal de [`docs/06-suivi.md`](docs/06-suivi.md) et appliquées aux documents : Mwangaza et `mwangaza.school`, 9 rôles, élève et famille propres à chaque école, taux fixe pour l'année, devise au choix pour chaque barème, formats de reçu au choix de l'école, QR code signé, bulletins à partir de la P2. Principe noté dans `CLAUDE.md` : l'ITIG est l'école d'exemple, rien de propre à une école dans le code.

### 7. Fusionner la PR des décisions

La PR des décisions (#78, branche `docs/decisions-q1-q11`) reporte tes réponses dans les documents. **La fusionner = accepter aussi ce que Claude a proposé** là où tu le lui as demandé (sinon, commentaire sur la PR) :

| Proposition | Où la lire |
|---|---|
| Permissions du directeur des études et du directeur de discipline ; nouvelle permission `classes.manage` (le directeur des études gère classes et inscriptions, aucun des deux ne touche à l'argent) | `docs/04-modele-de-donnees.md` § 8 |
| Parent avec des enfants dans deux écoles : **un seul compte**, relié à la famille de chaque école avec le code famille que chaque école lui remet ; jamais de rattachement par numéro de téléphone (un numéro mal saisi montrerait les enfants à un inconnu) | `docs/03-architecture-technique.md` § 4, maquette `portail/accueil` |
| QR code du reçu signé par l'appareil de la caisse : un reçu imprimé hors ligne est vérifiable tout de suite (« reçu authentique, en attente de synchronisation ») | `docs/03-architecture-technique.md` § 7 |
| Couleur de l'école refusée si le texte posé dessus n'est pas lisible ; couleur Mwangaza par défaut `#0E5C6B` | `docs/04-modele-de-donnees.md` § 1 |
| Montant en lettres : « Cent cinquante dollars américains et vingt-cinq centimes », « Deux cent quatre-vingt-cinq mille francs congolais » | `docs/02-perimetre-v1.md` F3 |
| Logo noir et blanc de l'ITIG pour le reçu thermique | `docs/ecole-pilote/documents/2026-09-26-logo-itig-noir-et-blanc.png` |
| 4 maquettes de la Gestion corrigées (la fiche famille ne montre plus les enfants d'une autre école) | `maquettes/captures/desktop/gestion-famille-fiche.png` et `gestion-eleve-fiche-*.png` |

**Fait** (#78 puis #79 fusionnées le 2026-09-26). Depuis, plus de PR empilées : chaque PR part de `main` (§ 10).

---

## 8. L'ITIG : rien à demander

**On n'attend rien de l'ITIG** (2026-10-02) : c'est l'école d'exemple, pas une étape du projet. Comme toute école, elle saisit ou importe elle-même ses données dans l'application (classes, frais, élèves en Excel, comptes), quand elle veut ; les données de démonstration sont inventées par Claude.

Si un document arrive quand même :

- un fichier → le mettre dans `docs/ecole-pilote/depot/` (hors Git), puis dans Claude Code : `/document-ecole`
- une liste d'élèves ou tout fichier avec des noms reste **hors Git** (`depot/`, `prive/`) : ne jamais le mettre ailleurs dans le dossier.

---

## 9. Mise en ligne (4.6.2) : comptes et achats

**Quand tu le décides** ; rien d'autre n'en dépend. Deux façons :

- **Démonstration gratuite** (données fictives seulement) : serveur Oracle Cloud « Always Free » (carte Visa ou Mastercard demandée à l'inscription, rien n'est prélevé ; un serveur peu utilisé peut être repris par Oracle) et adresse gratuite DuckDNS (`mwangaza.duckdns.org`, chaque école à `itig.mwangaza.duckdns.org`).
- **Vraie mise en ligne** (vraies données d'une école) : les lignes du tableau ci-dessous. À faire **avant** qu'une école saisisse ses vraies données : changer d'adresse ensuite obligerait à réinstaller les applications et rendrait invérifiables les QR des reçus déjà imprimés.


| Quoi | Comment | Fait |
|---|---|:-:|
| Domaine **`mwangaza.school`** (choisi le 2026-09-26) | vérifier qu'il est libre, l'acheter chez un registrar qui vend le `.school` ; activer le renouvellement automatique | [ ] |
| Cloudflare (gratuit) | créer le compte, ajouter le domaine, remplacer les serveurs DNS chez le registrar par ceux que Cloudflare indique | [ ] |
| VPS | 2 vCPU, 4 Go de RAM, Ubuntu 24.04 (Hetzner, DigitalOcean, OVH… ; moins de 20 $ / mois). À la création, ajouter ta clé SSH : `ssh-keygen -t ed25519` puis coller le contenu de `~/.ssh/id_ed25519.pub` | [ ] |
| Stockage objet (sauvegardes, photos) | Backblaze B2 ou Cloudflare R2 : créer un compte et un « bucket » ; Claude dira quelles clés créer | [ ] |
| Suivi d'erreurs | Sentry (offre gratuite) ou GlitchTip | [ ] |
| Clés des notifications sur l'écran (Web Push) | rien à acheter : sur le serveur, une seule fois, `docker compose exec django python manage.py webpush_keys`, puis coller les deux lignes dans `infra/.env` (voir `infra/.env.example`) ; ne plus jamais les changer | [ ] |
| Documents (T5, avant les vraies données d'une école) | conditions d'utilisation, confidentialité, contrat avec chaque école : Claude peut rédiger un brouillon, à faire relire | [ ] |
| Tarif des écoles (T6, avant les abonnements, 9.2) | décider : essai gratuit ? prix par élève ? | [ ] |

Partout : activer la double authentification et garder les codes de secours. Les mots de passe et clés vont dans le `.env` du serveur, jamais dans une conversation ni dans le dépôt : Claude te dira quel nom de variable remplir.

---

## 9 bis. Essai sur plusieurs appareils (4.11)

Pour essayer l'application **construite** (installable, notifications, hors-ligne) sur tes téléphones, un autre PC ou un iPhone, et la **montrer à des clients**, sans toucher à la version en développement. Tous les appareils sont sur le même réseau que ta machine (ton partage de connexion) ; la machine reste allumée. Adresse gratuite DuckDNS et vrai certificat : **rien à installer sur les appareils**.

Une seule fois :

1. Sur https://www.duckdns.org, te connecter (Google, GitHub…), écrire un nom (ex. `mwangaza-demo`) puis **add domain**. Noter le **token** affiché en haut de la page : il ne se donne à personne (ni dans Git, ni dans une conversation).
2. Ouvrir les ports de la machine aux autres appareils : `sudo ufw status` ; si la réponse est « active », `sudo ufw allow 80,443/tcp`.
3. `make reseau` : la première fois, il crée `infra/reseau/reseau.env` (hors Git, avec des secrets neufs) et s'arrête. Dans ce fichier, remplir `MWANGAZA_DOMAIN=mwangaza-demo.duckdns.org` (ton nom) et `DUCKDNS_TOKEN=` (le token).

À chaque essai :

4. `make reseau` : met l'adresse de ta machine dans DuckDNS, construit l'application (5 à 15 min la première fois), demande le certificat (1 à 2 min la première fois, gardé ensuite) et affiche les adresses. Si `make prod-local` tournait, il est arrêté (mêmes ports). `make dev` peut continuer à tourner.
5. La première fois (et pour tout remettre à zéro) : `make reseau-demo`, les données fictives (mêmes comptes qu'en développement, § 11 ; codes de double authentification : `make totp` sur la machine).
6. Sur la machine, ouvrir `https://www.mwangaza-demo.duckdns.org/` : la page montre un QR code par application (Gestion des deux écoles, Portail des parents, console). Les téléphones les scannent avec leur appareil photo. iPhone : ouvrir dans Safari, puis Partager → « Sur l'écran d'accueil » (sans cela, pas de notifications).
7. Réseau changé (autre partage de connexion, téléphone redémarré) : `make reseau-ip`, puis recharger la page sur les appareils (une minute au plus). Fin de l'essai : `make reseau-stop` (données et certificat gardés).

Limites : appareils sur le même réseau que la machine ; les notifications passent par internet (serveurs de Google, Apple, Mozilla). Un appareil qui n'ouvre pas l'adresse : vérifier qu'il est sur ce réseau, puis `make reseau-ip`. Les données de cet essai sont à part (ni celles du développement, ni celles de `make prod-local`) ; tout effacer : `make reseau-stop`, puis `docker volume rm $(docker volume ls -q --filter name=mwangaza-reseau)`.

---

## 10. Comment relire et fusionner une PR

Tu es le chef de projet et le relecteur ; Claude est le développeur. Il code, teste et ouvre **une seule PR par tâche** (corrections et documents compris), toujours sur `main`. Il te la donne dès qu'elle est poussée, contrôles GitHub en cours (≈ 5 min) : commence tes tests pendant ce temps ; il te dit « ✅ contrôles verts » ensuite. **Toi seul fusionnes**, et seulement après le ✅.

Chaque PR se termine par trois sections en français simple : **« À valider »**, **« À tester toi-même »**, **« Après la fusion »**. Le message de fin de Claude dans le terminal reprend les mêmes.

**En 5 étapes** (10 à 20 minutes) :

1. **Ouvrir la PR** : le lien donné par Claude, ou `gh pr view <numéro> --web`. En haut, vérifier **`base: main`** ; sinon, ne pas fusionner et le dire à Claude.
2. **Contrôles verts** : en bas de la page, « All checks have passed » ✔ (ou `gh pr checks <numéro>`). Une croix rouge ✘ : ne pas fusionner, donner le numéro à Claude.
3. **Lire la description** : correspond-elle à la tâche (`docs/05-plan-de-travail.md`) ? Puis **« À valider »** : ce que tu acceptes en fusionnant.
   - D'accord : étape 4.
   - Pas d'accord : un commentaire sur la PR (onglet *Conversation*, ou sur une ligne dans *Files changed*), puis dire à Claude « regarde les commentaires de la PR #n ». Il corrige **dans la même PR** et te la redonne quand elle est verte.
4. **Tester toi-même** : suivre **« À tester toi-même »** (commandes à copier, pages à ouvrir, résultat attendu). La section commence en général par :
   ```bash
   gh pr checkout <numéro>   # récupère la branche de la PR sur ta machine
   ```
   Résultat différent de l'attendu : le dire à Claude avec le message affiché. Tests finis : `git switch main`. La PR n'est **pas encore fusionnée** : « Après la fusion » vient après l'étape 5 (avant, `git pull` répond « Déjà à jour » et rien ne change).
5. **Fusionner** : bouton *Merge pull request* → *Confirm merge* → *Delete branch* (ou `gh pr merge <numéro> --merge --delete-branch`). Puis faire **« Après la fusion »**, en général :
   ```bash
   git switch main && git pull
   ```
   avec `make install` ou `make migrate` quand c'est indiqué, puis la tâche suivante : `/tache X.Y`. `/etat` à tout moment pour savoir où on en est.

**Le code** (onglet *Files changed*) n'est pas obligatoire : regarde-le quand tu veux apprendre comment une chose est faite, ou vérifier un point précis.

**Une PR séparée** n'arrive que dans deux cas : une décision importante à valider avant que Claude continue, ou une réparation urgente qui bloque le travail. Claude dit alors pourquoi elle est séparée.

---

## 11. Commandes du projet

À lancer depuis la racine du dossier (`~/Projets/mwangaza`). `make` seul affiche la liste.

### Disponibles maintenant

| Commande | Effet | Quand |
|---|---|---|
| `make install` | installe les dépendances (Python avec uv, front avec pnpm) et les contrôles avant commit | après un `git pull` qui change les dépendances |
| `make hooks` | installe seulement les contrôles avant commit (pre-commit) : ruff, ESLint, Prettier sur les fichiers du commit, refus d'un `.env` ou d'une clé privée | une fois (déjà fait par `make install`) |
| `make dev` | installe les dépendances du front, puis tout dans Docker : PostgreSQL, Redis, Django, Celery, Gestion, Portail, Console | travailler sur l'application |
| `make services` | seulement PostgreSQL (port 5433) et Redis dans Docker, prêts à l'emploi | rarement : `make dev-local`, `migrate`, `demo`, `test`, `shell` et `superuser` les démarrent d'eux-mêmes |
| `make dev-local` | Django et Vite sur ta machine (lit `.env`) ; **Ctrl+C arrête tout** (seul `^C` s'affiche) | plus rapide que `make dev` |
| `make stop` | arrête les conteneurs Docker | fin de journée |
| `make reset-db` | **efface** la base de développement (et celle des tests), puis la recrée : migrations et données fictives (`make demo`) | quand une PR le demande (ex. tâche 1.2), ou si `make migrate` affiche `InconsistentMigrationHistory` ; tu ne perds que des données fictives |
| `make migrate` | applique les migrations à la base | après un `git pull` qui ajoute des migrations |
| `make makemigrations app=finance name=exchange_rate` | crée une migration | après un changement de modèle |
| `make demo` | crée ou remet à jour les données fictives : identité de la plateforme de départ (nom « Mwangaza », couleurs, sans logo) avec un téléphone de support et des mentions légales fictifs ; écoles `itig` et `volcans` avec leur année 2026-2027, leurs classes, leur format de matricule, leurs frais (grille fictive) et leur taux de l'année ; ~800 élèves à l'ITIG et ~150 aux Volcans avec leurs familles ; réductions, caisses, paiements depuis la rentrée, crédits et demandes d'annulation ; annonces des écoles et trois annonces de la plateforme (non lues à chaque fois : le bandeau s'affiche) et leurs notifications au personnel (non lues aussi : la cloche montre leur nombre) ; un compte par rôle et un compte parent du portail, trois demandes de coordonnées des parents, environ une famille sur trois déjà inscrite au portail (liste des comptes, mot de passe et clé de double authentification affichés à la fin ; détail : `docs/07-a-fournir.md` § 4) ; débloque les connexions bloquées par des essais ratés ; refusé en production | après `make migrate`, ou pour remettre la démonstration à zéro |
| `make totp` | affiche le code de double authentification du moment pour les comptes fictifs qui la demandent (super-admin, directeur, comptable, caissière) ; `make totp key=<clé>` : pour la clé donnée à l'activation ; seulement en développement | se connecter sans téléphone ; ou ajouter une fois la clé affichée par `make demo` dans Google Authenticator ou Aegis |
| `make demo-excel` | écrit `eleves-fictifs.xlsx` à la racine du projet : une liste de ~800 élèves fictifs comme en tient un secrétariat (titre, colonnes NOM, POSTNOM…, fratries, quelques erreurs glissées exprès) ; seulement en développement | essayer l'import des élèves (Élèves → Importer Excel) |
| `make messages` | met à jour les traductions françaises des textes du serveur (`backend/locale/fr/…/django.po`), puis les compile ; demande gettext (`sudo apt install gettext`) ; tous les textes du serveur sont traduits, un test le vérifie | quand Claude le demande ; les fichiers compilés sont dans Git |
| `make test` | tous les tests | avant de fusionner une PR |
| `make test-back` | tests backend (pytest) | |
| `make test-front` | vérification des types du front, puis tests Vitest (logique et écrans) | |
| `make test-e2e` | parcours dans un vrai navigateur (Playwright) : connexion, console du super-admin, menu, activation, session support, paramètres, caisse sans réseau, démarrage hors ligne avec le PIN… ; **remet les données de `make demo` à zéro, avant et après** ; lance Django, la Gestion et la console, ou réutilise ceux de `make dev-local` | une fois avant : `cd frontend && pnpm exec playwright install chromium` ; ensuite quand tu veux, la CI le fait à chaque PR |
| `make lint` | vérifie le code sans rien modifier : ruff (Python), ESLint et Prettier (front) ; `make lint-back` ou `make lint-front` pour une seule partie | avant de fusionner une PR |
| `make format` | corrige automatiquement le format et ce qui peut l'être | quand `make lint` signale un problème de format |
| `make api` | écrit le schéma OpenAPI dans `frontend/packages/api/openapi.yaml`, puis les types TypeScript du client (`src/schema.d.ts`) ; `make api-schema` : seulement le schéma | après tout changement d'API |
| `make build` | construit les deux applications ; la Gestion devient installable (service worker) : l'essayer avec `cd frontend/apps/gestion && pnpm preview`, puis http://itig.localhost:4173/app/ | avant la mise en production |
| `make guide` | écrit le guide de la version en PDF, `docs/guide/guide-v1.0.pdf` (ce qu'elle fait, rôle par rôle, avec des captures des écrans sur les données fictives ; ce qu'elle ne fait pas encore ; la suite) : se connecte avec chaque compte fictif, prend les captures, puis imprime le guide ; **remet les données de `make demo` à zéro, avant et après** ; lance Django, la Gestion et le Portail, ou réutilise ceux de `make dev` / `make dev-local` (≈ 3 min) | à la fin de chaque version (Claude met le texte à jour) ; le PDF est dans Git, prêt à envoyer |
| `make prod-local` | essaie la production sur ta machine : construit les mêmes images que le serveur (Gestion et Portail construits, Django avec gunicorn, Caddy en HTTPS) et les lance ; puis https://itig.localhost/app/, https://parents.localhost/, https://admin.localhost/ (console ; administration de dépannage à `/admin/`) (certificat local : accepter l'avertissement du navigateur). Base vide : `make demo` y est refusé | pour voir la production avant la mise en ligne ; la première fois ≈ 10 min (téléchargements) |
| `make prod-local-stop` | arrête cet essai ; ses données sont gardées (`docker compose -p mwangaza-essai down --volumes` pour tout effacer) | après l'essai |
| `make reseau` | essai sur plusieurs appareils du même réseau (§ 9 bis) : met l'adresse de la machine dans DuckDNS, écrit la page des QR codes, construit et lance l'application avec un vrai certificat ; la première fois, crée `infra/reseau/reseau.env` à remplir | pour essayer sur des téléphones ou montrer l'application |
| `make reseau-demo` | données fictives dans cet essai (comme `make demo`) | la première fois, ou pour tout remettre comme au départ |
| `make reseau-ip` | remet l'adresse de la machine dans DuckDNS (`make reseau-ip ip=192.168.…` pour la choisir) | quand le partage de connexion a changé |
| `make reseau-stop` | arrête cet essai ; données et certificat gardés | après l'essai |
| `make superuser` | crée un compte super-administrateur (identifiant : ton numéro de téléphone) ; à sa première connexion à l'administration, il active la double authentification (clé à saisir dans Google Authenticator ou Aegis) | rarement : `make demo` en crée un (`0000000000`) |
| `make shell` | console Django | explorer les données |
| `python3 maquettes/outils/maquettes.py menu` | réécrit le menu latéral de toutes les maquettes Gestion | après un changement de menu |
| `python3 maquettes/outils/maquettes.py index` | régénère la galerie `maquettes/index.html` | après une nouvelle maquette |
| `node maquettes/outils/captures.mjs` | refait les captures PNG des maquettes | après une modification de maquette |

### Prévues (arrivent avec leur tâche)

Le nom exact est fixé pendant la tâche ; ce tableau est mis à jour à ce moment-là.

| Commande | Tâche | Effet |
|---|---|---|
| commande de déploiement (`make deploy`) | 4.6.2 | met en production sur le VPS en une commande |
| sauvegarde et restauration | 4.7 | sauvegarde de la base, test de restauration |

### Adresses en développement

| Adresse | Quoi |
|---|---|
| http://itig.localhost:5173/app/ | Gestion (le sous-domaine = code de l'école) : connexion avec un compte de `make demo` (mot de passe `mwangaza-demo`, code de `make totp`), menu selon le rôle ; caissier et comptable : guide de première connexion (« Aide et guide » en bas du menu pour le revoir) |
| http://itig.localhost:5173/app/account | Mon compte : langue, mot de passe, double authentification, écoles, déconnexion |
| http://itig.localhost:5173/app/settings | Paramètres de l'école : nom, logo, couleur, fuseau, devises (directeur) |
| http://itig.localhost:5173/app/organisation | Organisation scolaire : année, découpage, niveaux, options, classes, matricule (directeur, directeur des études `0000001002`) |
| http://itig.localhost:5173/app/staff · …/app/roles | Comptes du personnel ; Rôles et permissions (directeur) |
| http://itig.localhost:5173/app/audit | Journal d'audit : qui a fait quoi, quand (directeur, promoteur) |
| http://itig.localhost:5173/app/dashboard | Tableau de bord : encaissé, recouvrement, alertes (directeur `0000001001`, comptable `0000001004`) |
| http://itig.localhost:5173/app/students | Élèves : liste, fiche (identité, famille, finances, historique), nouvel élève, import Excel, liste de classe, fiche d'inscription, situation financière, invitations au portail par classe (`/app/students/invitations` : lettres, message WhatsApp ou SMS, familles pas encore inscrites) (secrétaire `0000001006`, directeur) |
| http://itig.localhost:5173/app/cash | Caisse : ouvrir sa session, encaisser, reçu, réimprimer, demander une annulation, clôturer (caissière `0000001005`) ; marche sans réseau sur un appareil mémorisé |
| http://itig.localhost:5173/app/unpaid | Impayés : liste, export PDF et Excel, situations à imprimer (directeur, comptable) |
| http://itig.localhost:5173/app/fees | Frais : types, barèmes, tranches, taux de l'année (comptable) |
| http://itig.localhost:5173/app/cancellations · …/app/cash-closings · …/app/credits | Annulations à valider ; clôtures de caisse ; crédits d'élèves (comptable) |
| http://itig.localhost:5173/app/announcements | Annonces aux familles : rédiger, joindre un PDF, archiver, « lue par N familles » (directeur) |
| http://itig.localhost:5173/app/parent-requests | Demandes des parents : coordonnées envoyées depuis le portail, à appliquer ou non (secrétaire) |
| http://itig.localhost:5173/app/devices | Appareils de l'école : postes mémorisés, dernière synchro, déconnecter (directeur) |
| http://itig.localhost:5173/app/platform-news | Annonces de la plateforme pour tout le personnel de l'école ; la dernière non lue s'affiche aussi en bandeau en haut de chaque écran (« Fermer » = lue pour ce compte) ; lien en bas du menu avec le nombre de non lues |
| http://itig.localhost:5173/app/notifications | Notifications (cloche en haut de chaque écran, avec le nombre de non lues) : toucher une notification ouvre l'écran lié ; « Activer sur cet appareil », « Envoyer un essai », sortes à recevoir. Les notifications sur l'écran ne marchent qu'avec l'application construite : `make build`, puis `cd frontend/apps/gestion && pnpm preview` et http://itig.localhost:4173/app/notifications |
| http://itig.localhost:5173/app/support | session support « en tant qu'école » (super-admin `0000000000`) : motif, bandeau rouge, « Quitter » |
| http://volcans.localhost:5173/app/ | Gestion de la seconde école fictive : on s'y connecte à part (session propre à chaque adresse) |
| http://itig.localhost:5173/api/school/ | quelle école répond à ce sous-domaine (après `make demo`) |
| http://itig.localhost:5173/api/platform/ | identité de la plateforme (nom, logo, couleurs, contact du support, mentions légales) : répond à toute adresse, même celle d'une école suspendue ; manifestes des applications : `/api/platform/manifest/gestion/` et `…/portail/` |
| http://localhost:5174/ | Portail parents : compte `0002000001`, mot de passe `mwangaza-demo` ; activation depuis le QR d'une lettre d'invitation (`/activate#…` : code déjà rempli) ; mes enfants, paiements et reçus (`/children/…`), annonces (`/announcements`), profil et coordonnées (`/profile`), ajouter un enfant d'une autre école (`/add-school`, code des Volcans affiché par `make demo`), installer (`/install`), guide du parent (`/guide`, aussi « Revoir le guide » du profil) ; première fois : `/activate` |
| http://itig.localhost:5173/v/… | vérification publique d'un reçu (QR du reçu) ou d'une situation financière (`/v/s/…`) |
| http://localhost:8000/api/health/ | l'API répond-elle ? |
| http://localhost:8000/api/docs/ | documentation de l'API |
| http://itig.localhost:5173/api/auth/login/ | se connecter par l'API (l'écran est à `/app/login`) : téléphone d'un compte de `make demo`, mot de passe `mwangaza-demo` ; la réponse donne l'étape suivante (`step`) |
| http://itig.localhost:5173/api/auth/login/totp/ | étape `totp` : code de `make totp` (directeur, comptable, caissière) |
| http://itig.localhost:5173/api/auth/totp/setup/ · …/totp/activate/ | étape `totp_setup` : nouvelle clé, puis premier code (`make totp key=<clé>`) → 8 codes de secours |
| http://itig.localhost:5173/api/auth/password/ · …/logout/ | nouveau mot de passe (provisoire, ou le sien) ; se déconnecter |
| http://itig.localhost:5173/api/me/ | le compte connecté, ses écoles, ses rôles et permissions dans l'école de l'adresse |
| http://itig.localhost:5173/api/roles/ · …/api/staff/ | rôles et comptes du personnel de l'école (directeur seulement) |
| http://itig.localhost:5173/api/audit/ | journal d'audit de l'école, le plus récent d'abord (directeur et promoteur) ; filtres dans l'adresse : `?domain=roles`, `?action=auth.login`, `?since=2026-09-26`, `?search=nom` |
| http://itig.localhost:5173/api/school/settings/ · …/settings/logo/ | paramètres de l'école : nom, nom officiel, couleur, fuseau horaire, devises ; logo (directeur) |
| http://itig.localhost:5173/api/school/logo/ | logo de l'école (public) |
| http://itig.localhost:5173/api/support/ | session support « en tant qu'école » : super-admin connecté à l'adresse de l'école (mot de passe et code), motif, 1 heure au plus |
| http://admin.localhost:5175/ | **Console de la plateforme** (super-admin `0000000000`, mot de passe `mwangaza-demo`, puis le code de `make totp`) : tableau de bord de toutes les écoles (écoles par statut, élèves, paiements et encaissé du jour par devise, écoles les plus actives, santé du serveur) ; **Identité de la plateforme** (http://admin.localhost:5175/identity : nom, logo, icône, couleurs avec aperçu, support, mentions légales ; changer le nom ne demande pas de code ; les 5 dernières modifications) ; **Écoles** (http://admin.localhost:5175/schools : chiffres, recherche, filtre par état, élèves, abonnement, dernière activité, « Ouvrir en tant qu'école » ; « Nouvelle école » http://admin.localhost:5175/schools/new avec son premier directeur — mot de passe provisoire affiché une seule fois ; fiche `/schools/<id>` : noms, adresse, abonnement, suspendre / réactiver, derniers changements) ; **Comptes** (http://admin.localhost:5175/accounts : chercher une personne par son nom ou son numéro dans toutes les écoles, ses écoles et rôles, ses familles du portail ; fiche : noms et téléphone, mot de passe provisoire affiché une seule fois — pas pour un parent seul, son école lui donne un nouveau code famille —, double authentification réinitialisée si le téléphone est perdu, désactiver / réactiver, derniers changements ; un compte super-admin ne se change que dans l'administration) ; **Annonces** (http://admin.localhost:5175/announcements : écrire un message à toutes les écoles ou à certaines, publié tout de suite dans la Gestion de leur personnel ; « lue par N personnes » ; archiver pour le retirer — une annonce ne se modifie pas) ; **Appareils** (http://admin.localhost:5175/devices : appareils mémorisés de toutes les écoles, recherche, en service ou déconnectés, « Déconnecter » après confirmation — noté au journal de l'école et de la plateforme) ; **Journal** (http://admin.localhost:5175/journal : ce que le support a fait dans la console, filtres par type, période et objet ; onglet « Sessions support » http://admin.localhost:5175/journal/support : sessions ouvertes, fermées ou expirées, motif, nombre d'actions) ; tout autre compte y est refusé ; menu du compte : « Administration de dépannage », « Se déconnecter » |
| http://localhost:8000/admin/ | administration Django, pour le dépannage (aussi à http://admin.localhost:5175/admin/, même session que la console) : super-admin `0000000000`, mot de passe `mwangaza-demo`, puis le code de `make totp` ; comptes, journal ; écoles (avec « Ouvrir en tant qu'école »), identité de la plateforme et journal de la plateforme en lecture seule (ils se modifient dans la console) |
| https://itig.localhost/app/ · https://parents.localhost/ · https://admin.localhost/ | essai de la production (`make prod-local`) : Gestion, Portail, console et administration (`/admin/`) servis par Caddy comme sur le serveur ; base vide : la Gestion affiche « Aucune école à cette adresse » tant qu'aucune école n'est créée ; santé de l'API : https://admin.localhost/api/health/ |
| https://www.mwangaza-demo.duckdns.org/ (ton nom DuckDNS) | essai sur plusieurs appareils (`make reseau`, § 9 bis) : page avec les QR codes ; puis `https://itig.…/app/`, `https://volcans.…/app/`, `https://parents.…/`, `https://admin.…/`, depuis tout appareil du même réseau, vrai certificat |

### Git et GitHub

| Commande | Effet |
|---|---|
| `git status` | ce qui a changé |
| `git switch main && git pull` | revenir sur `main` à jour |
| `git log --oneline -10` | derniers commits |
| `gh pr list` | PR ouvertes |
| `gh pr view <n> --web` | ouvrir une PR dans le navigateur |
| `gh pr checkout <n>` | récupérer la branche d'une PR pour l'essayer |
| `gh pr checks <n>` | résultat des contrôles GitHub (CI) d'une PR : tout doit être vert |
| `gh pr merge <n> --merge --delete-branch` | fusionner une PR (vérifier `base: main`) |
| `gh issue list --milestone V1.0` | tâches de la V1.0 |

### Claude Code

| Commande | Quand |
|---|---|
| `/etat` | où on en est, prochaine tâche, bloquants |
| `/tache 1.1` | réaliser une tâche du plan de bout en bout (une PR à relire à la fin) |
| `/noter …` | noter une décision, une réponse de l'ITIG, un blocage |
| `/document-ecole` | après avoir déposé un fichier de l'ITIG dans `docs/ecole-pilote/depot/` |
| `/ecran …` | construire un écran d'après sa maquette |
| `/verifier` | contrôle des règles avant commit |
| `/design`, `/backend`, `/argent`, `/hors-ligne` | utilisées par Claude pendant les tâches |

---

## 12. Dépannage

| Message | Cause | Solution |
|---|---|---|
| `permission denied … docker.sock` | pas encore reconnecté après `usermod` | se déconnecter / reconnecter (ou `newgrp docker` dans ce terminal) |
| `The SECRET_KEY setting must not be empty` | ancienne version du code avec `DJANGO_SECRET_KEY=` vide dans `.env` | `git switch main && git pull` après la fusion de la PR de correction (étape 5 bis) |
| `port is already allocated` (5433, 6379, 8000, 5173 ; 80 et 443 avec `make prod-local`) | un autre programme utilise le port | `ss -ltnp \| grep 6379` pour le trouver ; par ex. `sudo systemctl stop redis-server` |
| `InconsistentMigrationHistory: Migration admin.0001_initial is applied before its dependency accounts.0001_initial` (`make migrate`, `make test`, `make dev`) | base de développement créée avant la tâche 1.2 (nouveau modèle de compte) | `make reset-db` une fois |
| `"code": "too_many_attempts"` à la connexion | 5 essais ratés pour ce numéro en 15 minutes (ou 30 depuis ta machine) | attendre 15 minutes, ou `make demo` (débloque tout en développement) |
| `"code": "totp_required"` sur une page de l'école | session ouverte sans double authentification, alors qu'un rôle l'exige (ex. rôle donné pendant la session) | se déconnecter (`…/api/auth/logout/`) et se reconnecter |
| `"code": "invalid_code"` avec le code de `make totp` | code déjà utilisé (un code ne sert qu'une fois) | attendre le code suivant (30 secondes) et refaire `make totp` |
| `make test-e2e` : `Executable doesn't exist at …/ms-playwright/…` | Chromium de Playwright pas encore téléchargé | une fois : `cd frontend && pnpm exec playwright install chromium` |
| `make test-e2e` : « Ce code n'est pas valable, ou il a déjà servi » | tu t'es connecté avec le même compte fictif dans les 30 secondes d'avant (un code ne sert qu'une fois) | relancer `make test-e2e` (il remet la démonstration à zéro au début) |
| PDF (fiche d'inscription, liste de classe) : `cannot load library 'libpango-1.0-0'`, ou avertissement `HarfBuzz-Subset will be required` (`make dev-local`, `make test`) | bibliothèques de WeasyPrint absentes de ta machine (Docker les a déjà) | `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0` |
| La Gestion affiche « Pas de connexion au serveur » | Django ne tourne pas (ou pas encore) | lancer `make dev-local` ou `make dev`, puis « Réessayer » |
| La Gestion affiche « Aucune école à cette adresse » | adresse sans code d'école (`localhost:5173/app/`) ou code inconnu | http://itig.localhost:5173/app/ ; après `make demo` si la base est neuve |
| Administration Django : impossible de supprimer une école ou un compte (« objets protégés », `Journal d'audit`) | l'école ou le compte apparaît dans le journal d'audit, qui ne s'efface jamais ; une école ne se supprime jamais (bouton retiré) | suspendre l'école, désactiver le compte ; en développement seulement, `make reset-db` repart d'une base vide |
| Administration Django : la connexion demande un code, ou revient au numéro et au mot de passe | depuis la tâche 1.5, l'administration exige la double authentification du super-admin | numéro, mot de passe, puis le code de `make totp` (compte `0000000000` de `make demo`) ; compte créé par `make superuser` : activer la double authentification avec la clé affichée |
| Administration Django, fichier Excel ou PDF en anglais alors qu'on attend du français | le serveur suit la langue choisie dans l'application (Gestion ou Portail) sur ce navigateur | choisir « Français » sur la page de connexion, dans « Mon compte » ou dans le profil du portail, puis recharger |
| `"code": "no_support_session"` sur `/api/support/`, ou `permission_denied` pour le super-admin à l'adresse d'une école | pas de session support ouverte (ou fermée au bout d'une heure) | ouvrir la session : sur la page `/api/support/`, écrire le motif, **POST** |
| `ModuleNotFoundError: No module named 'argon2'` ou `'cryptography'` | dépendances de la tâche 1.3 pas installées | `make install` |
| `connection refused` (port 5433) ou `role "mwangaza" does not exist` | pas de `.env`, ou base Docker arrêtée avec une version d'avant la PR #80 | `cp .env.example .env` (étape 4) ; depuis la PR #80, les commandes `make` qui ont besoin de la base la démarrent d'elles-mêmes (sinon : `make services`, et lire son message) |
| Ctrl+C sur `make dev-local` : `Erreur de segmentation (core dump créé)`, `Traceback`, `SystemExit` | version du Makefile d'avant la PR #80 | après sa fusion : `git switch main && git pull` |
| « Failed », `[ELIFECYCLE] Command failed` ou `ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL` en arrêtant `pnpm dev` ou `make dev` | pnpm compte l'arrêt de Vite comme un échec | rien à faire : c'est normal (`make dev-local` ne l'affiche plus) |
| `ERR_PNPM_UNEXPECTED_STORE` | `pnpm` lancé depuis un autre terminal (celui de VS Code et celui d'Ubuntu ne rangent pas le cache au même endroit) | `cd frontend && pnpm install`, répondre `Y` pour réinstaller ; ensuite, toujours le même terminal |
| `bad interpreter` ou `No such file` dans `backend/.venv` | dossier déplacé ou renommé | `rm -rf backend/.venv && make install` |
| `itig.localhost` ne s'ouvre pas | navigateur qui ne gère pas `*.localhost` | utiliser Chrome ou Firefox |
| `git commit` échoue avec `ruff … Failed` ou `Prettier … Failed` et « files were modified by this hook » | le contrôle avant commit a corrigé le format | `git add` les fichiers corrigés, puis refaire le `git commit` |
| `git commit` échoue avec `ESLint … Failed` ou `ruff (lint Python) … Failed` | une vraie erreur dans le code (variable inutilisée, hook React mal placé…) | corriger l'erreur affichée, puis refaire le commit |
| `git commit` : `uv: not found` ou `frontend/node_modules/.bin/eslint: not found` | outils pas installés, ou `uv` absent du `PATH` du programme qui commite | `make install` ; commiter depuis le terminal de VS Code |
| une PR a une croix rouge ✘ (CI) | un contrôle échoue sur GitHub | `gh pr checks <numéro>` puis ouvrir le lien ; ou dire à Claude le numéro de la PR |

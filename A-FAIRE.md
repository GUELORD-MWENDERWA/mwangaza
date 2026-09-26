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
| 14 | **[Relire et fusionner la PR #PR16 (tâche 1.6)](#10-comment-relire-et-fusionner-une-pr)** (premiers écrans : connexion, menu, Mon compte, session support) : suivre « À tester toi-même », **fusionner sur GitHub**, puis `git switch main && git pull && make install` (**nouvelles dépendances du front** : React Router, TanStack Query, Tailwind, composants, formulaires, PWA, client de l'API, QR code, outils de test) ; pour `make test-e2e`, une fois : `cd frontend && pnpm exec playwright install chromium` (Chromium de Playwright, ~115 Mo) | 30 min | [ ] |

À chaque PR : [comment la relire et la fusionner](#10-comment-relire-et-fusionner-une-pr) (§ 10). Rien d'autre ne bloque : Claude enchaîne les tâches. Quand tu peux : [demander à l'ITIG](#8-litig--quoi-demander) ce qui reste (rien n'est bloquant), et [les comptes et le domaine](#9-avant-la-semaine-4-tâche-46--comptes-et-achats) avant la semaine 4.

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

## 8. L'ITIG : quoi demander

**Rien ne bloque** (décision du 2026-09-26) : l'ITIG est l'école d'exemple ; Claude travaille avec des données fictives réalistes, et l'ITIG saisira ses vraies données elle-même dans l'application. Les documents reçus remplacent les données fictives. Détail : [`docs/07-a-fournir.md`](docs/07-a-fournir.md) § 2.

| À demander | Sert à | Fait |
|---|---|:-:|
| Date de la remise des bulletins de la P1 2026 (I3) | calendrier ; confirme que la P1 reste sur papier | [ ] |
| Qui joue le rôle de promoteur (I4) | comptes à créer en 4.8 | [ ] |
| Photo du reçu actuel (I10) | ajuster le reçu et le montant en lettres (3.2) | [ ] |
| Bulletins vierges et remplis, par niveau et option (I15) | bulletins (V1.2) | [ ] |
| Code de l'école à 7 chiffres, N° ID et N° permanent des élèves ; bulletin pré-imprimé acheté ou non (I18) | bulletins (V1.2) | [ ] |
| Si l'occasion se présente : classes 2026-2027, matricule, grille des frais, liste des élèves en Excel, fiche d'inscription, fonctionnement de la caisse, marque de l'imprimante, logo en bonne qualité (I1, I2, I5–I9, I11, I12) | rendre la démonstration plus proche de la réalité ; tester l'import et l'imprimante en 4.8 | [ ] |

**Conseil** : une seule visite, avec une clé USB. Demander les fichiers Excel dans leur format d'origine, pas en PDF. Une photo au téléphone suffit pour un reçu, une fiche ou un bulletin.

**Message à envoyer** (WhatsApp ou imprimé), à adapter :

> Bonjour, pour préparer le logiciel de gestion de l'ITIG (élèves, frais, caisse, reçus, bulletins), j'aurais besoin de :
> 1. la date prévue pour la remise des bulletins de la 1re période ;
> 2. qui joue le rôle de promoteur de l'école ;
> 3. une photo du reçu de paiement actuel ;
> 4. un bulletin vierge et un bulletin rempli pour chaque niveau et option ;
> 5. le code de l'école imprimé sur les bulletins (7 chiffres), et si les bulletins sont achetés pré-imprimés ;
> 6. si possible : la grille des frais 2026-2027, la liste des élèves en Excel et le logo en bonne qualité.
> Merci !

**Quand tu reçois quelque chose** :

- un fichier → le mettre dans `docs/ecole-pilote/depot/` (hors Git), puis dans Claude Code : `/document-ecole`
- une réponse sans fichier → `/noter l'ITIG dit que …`
- une liste d'élèves ou tout fichier avec des noms reste **hors Git** (`depot/`, `prive/`) : ne jamais le mettre ailleurs dans le dossier.

---

## 9. Avant la semaine 4 (tâche 4.6) : comptes et achats

| Quoi | Comment | Fait |
|---|---|:-:|
| Domaine **`mwangaza.school`** (choisi le 2026-09-26) | vérifier qu'il est libre, l'acheter chez un registrar qui vend le `.school` ; activer le renouvellement automatique | [ ] |
| Cloudflare (gratuit) | créer le compte, ajouter le domaine, remplacer les serveurs DNS chez le registrar par ceux que Cloudflare indique | [ ] |
| VPS | 2 vCPU, 4 Go de RAM, Ubuntu 24.04 (Hetzner, DigitalOcean, OVH… ; moins de 20 $ / mois). À la création, ajouter ta clé SSH : `ssh-keygen -t ed25519` puis coller le contenu de `~/.ssh/id_ed25519.pub` | [ ] |
| Stockage objet (sauvegardes, photos) | Backblaze B2 ou Cloudflare R2 : créer un compte et un « bucket » ; Claude dira quelles clés créer | [ ] |
| Suivi d'erreurs | Sentry (offre gratuite) ou GlitchTip | [ ] |
| Documents (T5, avant 4.8) | conditions d'utilisation, confidentialité, contrat avec l'ITIG : Claude peut rédiger un brouillon, à faire relire | [ ] |
| Tarif du pilote (T6, avant 4.8) | décider : gratuit pendant l'essai ? | [ ] |

Partout : activer la double authentification et garder les codes de secours. Les mots de passe et clés vont dans le `.env` du serveur, jamais dans une conversation ni dans le dépôt : Claude te dira quel nom de variable remplir.

---

## 10. Comment relire et fusionner une PR

Tu es le chef de projet et le relecteur ; Claude est le développeur. Il code, teste et ouvre **une seule PR par tâche** (corrections et documents compris), toujours sur `main`. Il ne te la donne que quand les contrôles GitHub sont verts. **Toi seul fusionnes.**

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
| `make dev` | installe les dépendances du front, puis tout dans Docker : PostgreSQL, Redis, Django, Celery, Gestion, Portail | travailler sur l'application |
| `make services` | seulement PostgreSQL (port 5433) et Redis dans Docker, prêts à l'emploi | rarement : `make dev-local`, `migrate`, `demo`, `test`, `shell` et `superuser` les démarrent d'eux-mêmes |
| `make dev-local` | Django et Vite sur ta machine (lit `.env`) ; **Ctrl+C arrête tout** (seul `^C` s'affiche) | plus rapide que `make dev` |
| `make stop` | arrête les conteneurs Docker | fin de journée |
| `make reset-db` | **efface** la base de développement (et celle des tests), puis la recrée : migrations et données fictives (`make demo`) | quand une PR le demande (ex. tâche 1.2), ou si `make migrate` affiche `InconsistentMigrationHistory` ; tu ne perds que des données fictives |
| `make migrate` | applique les migrations à la base | après un `git pull` qui ajoute des migrations |
| `make makemigrations app=finance name=exchange_rate` | crée une migration | après un changement de modèle |
| `make demo` | crée ou remet à jour les données fictives : écoles `itig` et `volcans`, un compte par rôle (liste, mot de passe et clé de double authentification affichés à la fin ; plus de données à chaque tâche) ; débloque les connexions bloquées par des essais ratés ; refusé en production | après `make migrate`, ou pour remettre la démonstration à zéro |
| `make totp` | affiche le code de double authentification du moment pour les comptes fictifs qui la demandent (super-admin, directeur, comptable, caissière) ; `make totp key=<clé>` : pour la clé donnée à l'activation ; seulement en développement | se connecter sans téléphone ; ou ajouter une fois la clé affichée par `make demo` dans Google Authenticator ou Aegis |
| `make test` | tous les tests | avant de fusionner une PR |
| `make test-back` | tests backend (pytest) | |
| `make test-front` | vérification des types du front, puis tests Vitest (logique et écrans) | |
| `make test-e2e` | parcours dans un vrai navigateur (Playwright) : connexion, menu, activation, session support… ; **remet les données de `make demo` à zéro** ; lance Django et la Gestion, ou réutilise ceux de `make dev-local` | une fois avant : `cd frontend && pnpm exec playwright install chromium` ; ensuite quand tu veux, la CI le fait à chaque PR |
| `make lint` | vérifie le code sans rien modifier : ruff (Python), ESLint et Prettier (front) ; `make lint-back` ou `make lint-front` pour une seule partie | avant de fusionner une PR |
| `make format` | corrige automatiquement le format et ce qui peut l'être | quand `make lint` signale un problème de format |
| `make api` | écrit le schéma OpenAPI dans `frontend/packages/api/openapi.yaml`, puis les types TypeScript du client (`src/schema.d.ts`) ; `make api-schema` : seulement le schéma | après tout changement d'API |
| `make build` | construit les deux applications ; la Gestion devient installable (service worker) : l'essayer avec `cd frontend/apps/gestion && pnpm preview`, puis http://itig.localhost:4173/app/ | avant la mise en production |
| `make superuser` | crée un compte super-administrateur (identifiant : ton numéro de téléphone) ; à sa première connexion à l'administration, il active la double authentification (clé à saisir dans Google Authenticator ou Aegis) | rarement : `make demo` en crée un (`0000000000`) |
| `make shell` | console Django | explorer les données |
| `python3 maquettes/outils/maquettes.py menu` | réécrit le menu latéral de toutes les maquettes Gestion | après un changement de menu |
| `python3 maquettes/outils/maquettes.py index` | régénère la galerie `maquettes/index.html` | après une nouvelle maquette |
| `node maquettes/outils/captures.mjs` | refait les captures PNG des maquettes | après une modification de maquette |

### Prévues (arrivent avec leur tâche)

Le nom exact est fixé pendant la tâche ; ce tableau est mis à jour à ce moment-là.

| Commande | Tâche | Effet |
|---|---|---|
| commande de déploiement | 4.6 | met en production sur le VPS en une commande |
| sauvegarde et restauration | 4.7 | sauvegarde de la base, test de restauration |
| parcours Playwright hors-ligne (dans `make test-e2e`) | 3.5 | parcours dans le navigateur, réseau coupé |

### Adresses en développement

| Adresse | Quoi |
|---|---|
| http://itig.localhost:5173/app/ | Gestion (le sous-domaine = code de l'école) : connexion avec un compte de `make demo` (mot de passe `mwangaza-demo`, code de `make totp`), menu selon le rôle |
| http://itig.localhost:5173/app/account | Mon compte : langue, mot de passe, double authentification, écoles, déconnexion |
| http://itig.localhost:5173/app/support | session support « en tant qu'école » (super-admin `0000000000`) : motif, bandeau rouge, « Quitter » |
| http://volcans.localhost:5173/app/ | Gestion de la seconde école fictive : on s'y connecte à part (session propre à chaque adresse) |
| http://itig.localhost:5173/api/school/ | quelle école répond à ce sous-domaine (après `make demo`) |
| http://localhost:5174/ | Portail parents |
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
| http://localhost:8000/admin/ | administration Django : super-admin `0000000000`, mot de passe `mwangaza-demo`, puis le code de `make totp` ; écoles (créer, suspendre, « Ouvrir en tant qu'école »), comptes, journal |

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
| `port is already allocated` (5433, 6379, 8000, 5173) | un autre programme utilise le port | `ss -ltnp \| grep 6379` pour le trouver ; par ex. `sudo systemctl stop redis-server` |
| `InconsistentMigrationHistory: Migration admin.0001_initial is applied before its dependency accounts.0001_initial` (`make migrate`, `make test`, `make dev`) | base de développement créée avant la tâche 1.2 (nouveau modèle de compte) | `make reset-db` une fois |
| `"code": "too_many_attempts"` à la connexion | 5 essais ratés pour ce numéro en 15 minutes (ou 30 depuis ta machine) | attendre 15 minutes, ou `make demo` (débloque tout en développement) |
| `"code": "totp_required"` sur une page de l'école | session ouverte sans double authentification, alors qu'un rôle l'exige (ex. rôle donné pendant la session) | se déconnecter (`…/api/auth/logout/`) et se reconnecter |
| `"code": "invalid_code"` avec le code de `make totp` | code déjà utilisé (un code ne sert qu'une fois) | attendre le code suivant (30 secondes) et refaire `make totp` |
| `make test-e2e` : `Executable doesn't exist at …/ms-playwright/…` | Chromium de Playwright pas encore téléchargé | une fois : `cd frontend && pnpm exec playwright install chromium` |
| `make test-e2e` : « Ce code n'est pas valable, ou il a déjà servi » | tu t'es connecté avec le même compte fictif dans les 30 secondes d'avant (un code ne sert qu'une fois) | relancer `make test-e2e` (il remet la démonstration à zéro au début) |
| La Gestion affiche « Pas de connexion au serveur » | Django ne tourne pas (ou pas encore) | lancer `make dev-local` ou `make dev`, puis « Réessayer » |
| La Gestion affiche « Aucune école à cette adresse » | adresse sans code d'école (`localhost:5173/app/`) ou code inconnu | http://itig.localhost:5173/app/ ; après `make demo` si la base est neuve |
| Administration Django : impossible de supprimer une école ou un compte (« objets protégés », `Journal d'audit`) | l'école ou le compte apparaît dans le journal d'audit, qui ne s'efface jamais ; une école ne se supprime jamais (bouton retiré) | suspendre l'école, désactiver le compte ; en développement seulement, `make reset-db` repart d'une base vide |
| Administration Django : la connexion demande un code, ou revient au numéro et au mot de passe | depuis la tâche 1.5, l'administration exige la double authentification du super-admin | numéro, mot de passe, puis le code de `make totp` (compte `0000000000` de `make demo`) ; compte créé par `make superuser` : activer la double authentification avec la clé affichée |
| Administration Django : textes en anglais (« Schools », « Open as the school ») mêlés au français | les textes du serveur ne sont pas encore traduits | normal pour l'instant (traduction du serveur prévue en 4.5) |
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

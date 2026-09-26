# À faire de ton côté

Ce que **toi seul** peux faire, comment le faire, et toutes les commandes du projet.
Claude ne peut pas : installer avec `sudo`, fusionner une PR, parler à l'ITIG, acheter, créer des comptes. Il met ce fichier à jour dès qu'une action t'attend ou qu'une commande est ajoutée.

Ce qui manque en détail (maquettes, informations ITIG, décisions) : [`docs/07-a-fournir.md`](docs/07-a-fournir.md). Ici : **quoi faire, dans quel ordre, avec quelles commandes**.

Dernière mise à jour : 2026-09-26 (après installation de Docker).

## Maintenant, avant que Claude continue (tâche 0.2)

| # | Action | Temps | Fait |
|:-:|---|---|:-:|
| 1 | [Fusionner la PR #75](#1-fusionner-la-pr-75) (documents, 61 maquettes, ce fichier) | 5 min | [x] |
| 2 | [Rouvrir VS Code dans `~/Projets/mwangaza`](#2-le-dossier-sappelle-maintenant-mwangaza) | 1 min | [x] |
| 3 | [Installer Docker](#3-installer-docker) | 15 min | [x] |
| 3 bis | **[Se déconnecter puis se reconnecter](#3-bis-se-déconnecter-puis-se-reconnecter)** (sinon `docker` répond `permission denied`) | 2 min | [x] |
| 4 | [Créer le fichier `.env`](#4-créer-le-fichier-env) | 2 min | [x] |
| 5 | [Vérifier que tout marche](#5-vérifier-que-tout-marche) : Claude l'a vérifié le 2026-09-26 ; à refaire toi-même une fois | 5 min | [ ] |
| 5 bis | [Fusionner la PR #76 (correction du `.env`)](#5-bis-fusionner-la-pr-de-correction-du-env) | 2 min | [x] |
| 5 ter | [Fusionner la PR de correction de `make dev`](#5-ter-fusionner-la-pr-de-correction-de-make-dev) | 2 min | [ ] |
| 6 | [Donner tes décisions](#6-tes-décisions) : nom et domaine (Q9), questions Q1 à Q11 | 10 min | [ ] |

Quand c'est fait, dans Claude Code : **`/tache 0.2`**. Tout marche déjà (vérifié par Claude) : l'étape 5 sert à ce que **toi** saches lancer les commandes.

Cette semaine aussi : [aller à l'ITIG](#7-litig--quoi-demander-et-quand) avec la liste de la semaine 1 (nécessaire pour la tâche 1.7).

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

### 5 bis. Fusionner la PR de correction du `.env`

PR #76, branche `fix/env-valeurs-vides` : une variable vide dans `.env` ne fait plus planter Django, `.env.example` explique la clé, ce fichier est à jour. Sur GitHub : vérifier **`base: main`** → *Merge pull request* → *Delete branch*. Ou :

```bash
gh pr merge 76 --merge --delete-branch
git switch main && git pull
```

**Fait.**

### 5 ter. Fusionner la PR de correction de `make dev`

Le premier essai de `make dev` a montré deux défauts : le conteneur du front s'arrêtait aussitôt (`pnpm: not found`), et il réinstallait toutes les dépendances du front à chaque lancement, en écrasant celles de ta machine. Corrigé sur la branche `fix/docker-front` : le conteneur utilise les dépendances installées sur ta machine, et `make dev` lance `pnpm install` avant de démarrer Docker. Même démarche qu'en 5 bis (vérifier **`base: main`**).

### 6. Tes décisions

| Sujet | Où lire | Comment répondre |
|---|---|---|
| **Nom et domaine** (Q9, T1) : proposition = garder Mwangaza et acheter `mwangaza.africa` | `docs/06-suivi.md` → Questions ouvertes, Q9 | `/noter Q9 : on garde Mwangaza, domaine mwangaza.africa` (ou ton choix). Acheter le domaine avant la tâche 4.6 |
| **Questions Q1 à Q11** (T2) : chaque question a une proposition | `docs/06-suivi.md` → Questions ouvertes | `/noter Q1 à Q11 : OK` ou `/noter Q1 à Q11 : OK sauf Q7 → …` |
| **Maquettes dessinées** (M1 à M20) | ouvrir `maquettes/index.html` dans le navigateur | fusionner la PR #75 = validées ; sinon commentaire sur la PR |

---

## 7. L'ITIG : quoi demander et quand

Le détail et ce qu'on utilise en attendant : [`docs/07-a-fournir.md`](docs/07-a-fournir.md) § 2. Rien ne bloque les tâches 0.2 à 1.6 : Claude travaille avec des données fictives.

| Avant | Tâche | À demander (numéros de `07`) |
|---|---|---|
| **fin de la semaine 1** | 1.2, 1.7 | I1 classes 2026-2027 (sections par niveau, options) · I2 format du matricule · I3 calendrier (périodes, examens, date de proclamation de la P1) · I4 qui fait quoi (préfet, directeurs, économe, caissiers, secrétaires) et **qui est le « promoteur »** (Q7) · I13 code `itig` dans l'adresse |
| **semaine 2** | 2.3 à 2.6 | I5 grille des frais 2026-2027 · I6 réductions pratiquées et qui les accorde · I7 **liste des élèves en Excel** (même partielle) · I8 fiche d'inscription et liste de classe actuelles |
| **semaine 3** | 3.1, 3.2, 3.8 | I9 fonctionnement de la caisse (caissiers, annulations, clôture, taux du jour) · I10 **photo du reçu actuel** · I11 imprimante thermique (marque, modèle, papier 58 ou 80 mm), ordinateurs, connexion internet · I12 logo en haute qualité + noir et blanc, nom officiel exact |
| plus tard (V1.1, V1.2) | 5.x, 6.x | I14 grille salariale et primes · I15 bulletin vierge et rempli par niveau · I16 règles de délibération · I17 conduite et sanctions · I18 code de l'école à 7 chiffres |

**Conseil** : une seule visite pour tout demander (avec une clé USB), en visant d'abord la semaine 1 et la semaine 2. Demander les fichiers Excel dans leur format d'origine, pas en PDF. Une photo au téléphone suffit pour un reçu, une fiche ou un bulletin.

**Message à envoyer** (WhatsApp ou imprimé), à adapter :

> Bonjour, pour préparer le logiciel de gestion de l'ITIG (élèves, frais, caisse, reçus), j'aurais besoin de :
> 1. la liste des classes 2026-2027 (sections par niveau et par option) et le calendrier scolaire (périodes, examens) ;
> 2. le format actuel du matricule des élèves ;
> 3. qui occupe chaque fonction (préfet, directeurs, économe, caissiers, secrétaires) et qui joue le rôle de promoteur ;
> 4. la grille des frais 2026-2027 (montants, devises, tranches, dates limites) et les réductions accordées ;
> 5. la liste des élèves au format Excel ;
> 6. une photo du reçu de paiement actuel, de la fiche d'inscription et d'une liste de classe ;
> 7. la marque et le modèle de l'imprimante de reçus ;
> 8. le logo en bonne qualité.
> Merci !

**Quand tu reçois quelque chose** :

- un fichier → le mettre dans `docs/ecole-pilote/depot/` (hors Git), puis dans Claude Code : `/document-ecole`
- une réponse sans fichier → `/noter l'ITIG dit que …`
- une liste d'élèves ou tout fichier avec des noms reste **hors Git** (`depot/`, `prive/`) : ne jamais le mettre ailleurs dans le dossier.

---

## 8. Avant la semaine 4 (tâche 4.6) : comptes et achats

| Quoi | Comment | Fait |
|---|---|:-:|
| Domaine | l'acheter chez un registrar qui vend l'extension choisie ; activer le renouvellement automatique | [ ] |
| Cloudflare (gratuit) | créer le compte, ajouter le domaine, remplacer les serveurs DNS chez le registrar par ceux que Cloudflare indique | [ ] |
| VPS | 2 vCPU, 4 Go de RAM, Ubuntu 24.04 (Hetzner, DigitalOcean, OVH… ; moins de 20 $ / mois). À la création, ajouter ta clé SSH : `ssh-keygen -t ed25519` puis coller le contenu de `~/.ssh/id_ed25519.pub` | [ ] |
| Stockage objet (sauvegardes, photos) | Backblaze B2 ou Cloudflare R2 : créer un compte et un « bucket » ; Claude dira quelles clés créer | [ ] |
| Suivi d'erreurs | Sentry (offre gratuite) ou GlitchTip | [ ] |
| Documents (T5, avant 4.8) | conditions d'utilisation, confidentialité, contrat avec l'ITIG : Claude peut rédiger un brouillon, à faire relire | [ ] |
| Tarif du pilote (T6, avant 4.8) | décider : gratuit pendant l'essai ? | [ ] |

Partout : activer la double authentification et garder les codes de secours. Les mots de passe et clés vont dans le `.env` du serveur, jamais dans une conversation ni dans le dépôt : Claude te dira quel nom de variable remplir.

---

## 9. À chaque tâche (la routine)

1. Dans Claude Code : `/tache X.Y` (ex. `/tache 0.2`). `/etat` à tout moment pour savoir où on en est.
2. Claude code, teste, commite, pousse et ouvre la PR. **Il ne fusionne jamais.**
3. Toi : relire la PR sur GitHub, puis l'essayer :
   ```bash
   gh pr checkout <numéro>
   make test
   make dev          # ou make dev-local, puis regarder l'écran concerné
   ```
4. Fusionner (**`base: main`**), puis :
   ```bash
   git switch main && git pull
   ```
5. Tâche suivante.

---

## 10. Commandes du projet

À lancer depuis la racine du dossier (`~/Projets/mwangaza`). `make` seul affiche la liste.

### Disponibles maintenant

| Commande | Effet | Quand |
|---|---|---|
| `make install` | installe les dépendances (Python avec uv, front avec pnpm) | après un `git pull` qui change les dépendances |
| `make dev` | installe les dépendances du front, puis tout dans Docker : PostgreSQL, Redis, Django, Celery, Gestion, Portail | travailler sur l'application |
| `make services` | seulement PostgreSQL (port 5433) et Redis dans Docker | avant `make dev-local` ou `make test` |
| `make dev-local` | Django et Vite sur ta machine (lit `.env`) | plus rapide que `make dev` |
| `make stop` | arrête les conteneurs Docker | fin de journée |
| `make migrate` | applique les migrations à la base | après un `git pull` qui ajoute des migrations |
| `make makemigrations app=finance name=exchange_rate` | crée une migration | après un changement de modèle |
| `make test` | tous les tests | avant de fusionner une PR |
| `make test-back` | tests backend (pytest) | |
| `make test-front` | vérification des types du front | |
| `make lint` | lint et format | fonctionnel à partir de la tâche 0.2 |
| `make api` | écrit le schéma OpenAPI dans `frontend/packages/api/openapi.yaml` | après tout changement d'API |
| `make build` | construit les deux applications | avant la mise en production |
| `make superuser` | crée un compte super-administrateur | une fois par base |
| `make shell` | console Django | explorer les données |
| `python3 maquettes/outils/maquettes.py menu` | réécrit le menu latéral de toutes les maquettes Gestion | après un changement de menu |
| `python3 maquettes/outils/maquettes.py index` | régénère la galerie `maquettes/index.html` | après une nouvelle maquette |
| `node maquettes/outils/captures.mjs` | refait les captures PNG des maquettes | après une modification de maquette |

### Prévues (arrivent avec leur tâche)

Le nom exact est fixé pendant la tâche ; ce tableau est mis à jour à ce moment-là.

| Commande | Tâche | Effet |
|---|---|---|
| `make lint` (ruff, ESLint, Prettier) | 0.2 | vérifie et met en forme le code |
| `make test-front` (Vitest) | 0.2 | vrais tests du front, en plus des types |
| `pre-commit install` (une seule fois) | 0.2 | contrôles automatiques avant chaque commit |
| `make demo` | 1.5 | recrée les données fictives : école `itig` (démo), école `volcans`, un compte par rôle |
| commande de déploiement | 4.6 | met en production sur le VPS en une commande |
| sauvegarde et restauration | 4.7 | sauvegarde de la base, test de restauration |
| tests Playwright (hors-ligne) | 3.5 | parcours dans le navigateur, réseau coupé |

### Adresses en développement

| Adresse | Quoi |
|---|---|
| http://itig.localhost:5173/app/ | Gestion (le sous-domaine = code de l'école) |
| http://localhost:5174/ | Portail parents |
| http://localhost:8000/api/health/ | l'API répond-elle ? |
| http://localhost:8000/api/docs/ | documentation de l'API |

### Git et GitHub

| Commande | Effet |
|---|---|
| `git status` | ce qui a changé |
| `git switch main && git pull` | revenir sur `main` à jour |
| `git log --oneline -10` | derniers commits |
| `gh pr list` | PR ouvertes |
| `gh pr view <n> --web` | ouvrir une PR dans le navigateur |
| `gh pr checkout <n>` | récupérer la branche d'une PR pour l'essayer |
| `gh pr merge <n> --merge --delete-branch` | fusionner une PR (vérifier `base: main`) |
| `gh issue list --milestone V1.0` | tâches de la V1.0 |

### Claude Code

| Commande | Quand |
|---|---|
| `/etat` | où on en est, prochaine tâche, bloquants |
| `/tache 0.2` | réaliser une tâche du plan de bout en bout |
| `/noter …` | noter une décision, une réponse de l'ITIG, un blocage |
| `/document-ecole` | après avoir déposé un fichier de l'ITIG dans `docs/ecole-pilote/depot/` |
| `/ecran …` | construire un écran d'après sa maquette |
| `/verifier` | contrôle des règles avant commit |
| `/design`, `/backend`, `/argent`, `/hors-ligne` | utilisées par Claude pendant les tâches |

---

## 11. Dépannage

| Message | Cause | Solution |
|---|---|---|
| `permission denied … docker.sock` | pas encore reconnecté après `usermod` | se déconnecter / reconnecter (ou `newgrp docker` dans ce terminal) |
| `The SECRET_KEY setting must not be empty` | ancienne version du code avec `DJANGO_SECRET_KEY=` vide dans `.env` | `git switch main && git pull` après la fusion de la PR de correction (étape 5 bis) |
| `port is already allocated` (5433, 6379, 8000, 5173) | un autre programme utilise le port | `ss -ltnp \| grep 6379` pour le trouver ; par ex. `sudo systemctl stop redis-server` |
| `connection refused` ou `role "mwangaza" does not exist` | pas de `.env`, ou base Docker arrêtée | étapes 4 et 5 : `cp .env.example .env`, `make services` |
| `ERR_PNPM_UNEXPECTED_STORE` | `pnpm` lancé depuis un autre terminal (celui de VS Code et celui d'Ubuntu ne rangent pas le cache au même endroit) | `cd frontend && pnpm install`, répondre `Y` pour réinstaller ; ensuite, toujours le même terminal |
| `bad interpreter` ou `No such file` dans `backend/.venv` | dossier déplacé ou renommé | `rm -rf backend/.venv && make install` |
| `itig.localhost` ne s'ouvre pas | navigateur qui ne gère pas `*.localhost` | utiliser Chrome ou Firefox |

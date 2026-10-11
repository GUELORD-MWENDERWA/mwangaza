# À faire de ton côté

Ce que **toi seul** peux faire, comment le faire, et toutes les commandes du projet.
Claude ne peut pas : installer avec `sudo`, fusionner une PR, parler à l'ITIG, acheter, créer des comptes. Il met ce fichier à jour dès qu'une action t'attend ou qu'une commande est ajoutée.

Ce qui manque en détail (maquettes, informations ITIG, décisions) : [`docs/07-a-fournir.md`](docs/07-a-fournir.md). Ici : **quoi faire, dans quel ordre, avec quelles commandes**.

Dernière mise à jour : 2026-10-11 (tâche 4.17.1 : espaces de démonstration, règles du serveur et `make demo`).

## Maintenant

| # | Action | Temps | Fait |
|:-:|---|---|:-:|
| 1 | **Relire et fusionner la PR « 4.17.1 — Espaces de démonstration : règles du serveur et make demo »** (lire « À valider » : découpage de la 4.17, numéros fictifs en `000…`, code à 6 chiffres gardé en développement), puis `git switch main && git pull && make demo` : `itig` et `volcans` passent sous l'onglet « Démonstration » de la console. Essai sur plusieurs appareils ou serveur en ligne déjà lancés : il n'y a plus de super-admin fictif `0000000000` hors développement — après `make reseau-demo` ou `make deploy-demo`, créer le tien avec `make reseau-superuser` ou `make deploy-superuser` | 15 min | [ ] |
| 2 | **Essayer le Portail sur ton vrai téléphone**, ce que je ne peux pas faire (navigateur, puis application installée ; Android et iPhone si possible) : [§ 9 bis](#9-bis-essai-sur-plusieurs-appareils-411) (`make reseau`), parent `0002000001`, quitter l'application, la rouvrir plus tard et le lendemain, couper le réseau. Me dire si une déconnexion revient (quand, sur quel téléphone), et **à quel moment l'import exige un matricule** (Q14, [`docs/06-suivi.md`](docs/06-suivi.md)) | 15 min | [ ] |
| 3 | **Mettre le serveur de démonstration en ligne**, quand tu veux : [§ 9 ter](#9-ter-serveur-de-démonstration-en-ligne-462) (compte Oracle Cloud, serveur gratuit, adresse DuckDNS, `make deploy-setup`, `make deploy`) | 1 h | [ ] |
| 4 | Juste après : garder une **copie de `infra/serveur/serveur.env`** en lieu sûr (clé USB, gestionnaire de mots de passe) | 2 min | [ ] |
| 5 | **Avant la première vraie école** : vrai domaine et sauvegardes, [§ 9](#9-vraie-mise-en-ligne-463-47--comptes-et-achats) (tâches 4.6.3 et 4.7.2, après le bloc « Lancement — version finie ») | 1 h | [ ] |

Déjà fait : installation de la machine (Docker, `.env`, gettext), décisions (nom, domaine, Q1 à Q11), PR des tâches 0.1 à 4.11 et 5.1 à 5.5.1 ; historique complet : [`docs/06-suivi.md`](docs/06-suivi.md). À chaque PR : [comment la relire et la fusionner](#10-comment-relire-et-fusionner-une-pr) (§ 10). [Rien à demander à l'ITIG](#8-litig--rien-à-demander).

---

## 7. Installer le projet sur une machine

Déjà fait sur ta machine. Pour un autre ordinateur sous Ubuntu 24.04 :

1. **Docker** (documentation officielle), puis **se déconnecter et se reconnecter** (sinon `docker` répond `permission denied`) :
   ```bash
   sudo apt-get update && sudo apt-get install -y ca-certificates curl gettext
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   sudo usermod -aG docker $USER
   ```
2. **Outils** : [uv](https://docs.astral.sh/uv/) (Python), Node 22, `corepack enable pnpm`, Git, make.
3. **Projet** : `git clone` du dépôt dans `~/Projets/mwangaza`, puis `cp .env.example .env` (rien à remplir), `make install`, `make migrate demo`.
4. **Vérifier** : `make dev`, puis http://localhost:8000/api/health/ (`"status": "ok"`), http://itig.localhost:5173/app/ et http://localhost:5174/. Ctrl+C puis `make stop` pour arrêter.

`.env` n'est jamais commité. Aucun mot de passe ni aucune clé dans le dépôt ou dans une conversation avec Claude.

---

## 8. L'ITIG : rien à demander

**On n'attend rien de l'ITIG** (2026-10-02) : c'est l'école d'exemple, pas une étape du projet. Comme toute école, elle saisit ou importe elle-même ses données dans l'application (classes, frais, élèves en Excel, comptes), quand elle veut ; les données de démonstration sont inventées par Claude.

Si un document arrive quand même :

- un fichier → le mettre dans `docs/ecole-pilote/depot/` (hors Git), puis dans Claude Code : `/document-ecole`
- une liste d'élèves ou tout fichier avec des noms reste **hors Git** (`depot/`, `prive/`) : ne jamais le mettre ailleurs dans le dossier.

---

## 9. Vraie mise en ligne (4.6.3, 4.7) : comptes et achats

À faire **avant** qu'une école saisisse ses vraies données : changer d'adresse ensuite obligerait à réinstaller les applications et rendrait invérifiables les QR des reçus déjà imprimés. Le serveur Oracle du § 9 ter peut servir aussi pour la vraie mise en ligne au début ; il lui manque le vrai domaine et les sauvegardes.

| Quoi | Comment | Fait |
|---|---|:-:|
| Domaine **`mwangaza.school`** (choisi le 2026-09-26) | vérifier qu'il est libre, l'acheter chez un registrar qui vend le `.school` ; activer le renouvellement automatique | [ ] |
| Cloudflare (gratuit) | créer le compte, ajouter le domaine, remplacer les serveurs DNS chez le registrar par ceux que Cloudflare indique | [ ] |
| Serveur | celui du § 9 ter (gratuit), ou un VPS payant (2 vCPU, 4 Go, Ubuntu 24.04, moins de 20 $ / mois) si une école l'exige | [ ] |
| Stockage objet (sauvegardes, photos) | gratuit : Oracle Object Storage (20 Go, même compte) ou Backblaze B2 (10 Go) ; Claude dira quelles clés créer (4.7.2) | [ ] |
| Suivi d'erreurs et sonde de disponibilité | Sentry (offre gratuite) ou GlitchTip ; UptimeRobot (gratuit) | [ ] |
| Documents (T5, avant les vraies données d'une école) | conditions d'utilisation, confidentialité, contrat avec chaque école : Claude peut rédiger un brouillon, à faire relire | [ ] |
| Tarif des écoles (T6, avant les abonnements, 9.2) | décider : essai gratuit ? prix par élève ? | [ ] |

Partout : activer la double authentification et garder les codes de secours. Les mots de passe et clés vont dans le fichier de valeurs du serveur, jamais dans une conversation ni dans le dépôt : Claude te dira quel nom de variable remplir.

---

## 9 bis. Essai sur plusieurs appareils (4.11)

Pour essayer l'application **construite** (installable, notifications, hors-ligne) sur tes téléphones, un autre PC ou un iPhone, et la **montrer à des clients**, sans toucher à la version en développement. Tous les appareils sont sur le même réseau que ta machine (ton partage de connexion) ; la machine reste allumée. Adresse gratuite DuckDNS et vrai certificat : **rien à installer sur les appareils**.

Une seule fois :

1. Sur https://www.duckdns.org, te connecter (Google, GitHub…), écrire un nom (ex. `mwangaza-demo`) puis **add domain**. Noter le **token** affiché en haut de la page : il ne se donne à personne (ni dans Git, ni dans une conversation).
2. Ouvrir les ports de la machine aux autres appareils : `sudo ufw status` ; si la réponse est « active », `sudo ufw allow 80,443/tcp`.
3. `make reseau` : la première fois, il crée `infra/reseau/reseau.env` (hors Git, avec des secrets neufs) et s'arrête. Dans ce fichier, remplir `MWANGAZA_DOMAIN=mwangaza-demo.duckdns.org` (ton nom) et `DUCKDNS_TOKEN=` (le token).

À chaque essai :

4. `make reseau` : met l'adresse de ta machine dans DuckDNS, construit l'application (5 à 15 min la première fois), demande le certificat (1 à 2 min la première fois, gardé ensuite) et affiche les adresses. Si `make prod-local` tournait, il est arrêté (mêmes ports). `make dev` peut continuer à tourner.
5. La première fois (et pour tout remettre à zéro) : `make reseau-demo`, les données fictives (mêmes comptes qu'en développement, § 11, mais **sans code à 6 chiffres** : un espace de démonstration ne le demande pas), puis `make reseau-superuser` pour ouvrir la console : ton propre compte super-admin, avec ton numéro (il n'y a pas de super-admin fictif hors développement).
6. Sur la machine, ouvrir `https://www.mwangaza-demo.duckdns.org/` : la page montre un QR code par application (Gestion des deux écoles, Portail des parents, console). Les téléphones les scannent avec leur appareil photo. iPhone : ouvrir dans Safari, puis Partager → « Sur l'écran d'accueil » (sans cela, pas de notifications).
7. Réseau changé (autre partage de connexion, téléphone redémarré) : `make reseau-ip`, puis recharger la page sur les appareils (une minute au plus). Fin de l'essai : `make reseau-stop` (données et certificat gardés).

Limites : appareils sur le même réseau que la machine ; les notifications passent par internet (serveurs de Google, Apple, Mozilla). Un appareil qui n'ouvre pas l'adresse : vérifier qu'il est sur ce réseau, puis `make reseau-ip`. Les données de cet essai sont à part (ni celles du développement, ni celles de `make prod-local`) ; tout effacer : `make reseau-stop`, puis `docker volume rm $(docker volume ls -q --filter name=mwangaza-reseau)`.

---

## 9 ter. Serveur de démonstration en ligne (4.6.2)

L'application construite, **en ligne 24 h/24**, joignable depuis n'importe quel réseau (clients, écoles intéressées), même ta machine éteinte, pour **0 $** : serveur gratuit à vie d'Oracle Cloud (« Always Free » : processeur ARM, 2 cœurs, 12 Go de mémoire) et adresse gratuite DuckDNS, avec un vrai certificat. **Données fictives seulement** (pas de sauvegarde, adresse provisoire).

Une seule fois :

1. **Compte Oracle Cloud** : https://signup.cloud.oracle.com → « Start for free ». Une carte Visa ou Mastercard est demandée pour vérifier ton identité : rien n'est prélevé (une petite autorisation peut apparaître puis disparaître). **Région d'origine** : la plus proche de Goma est Johannesburg ; sinon une région d'Europe ; elle ne se change plus. Conseillé ensuite : *Billing → Upgrade to Pay As You Go* : ça reste à 0 $ tant que tu ne crées que des ressources marquées « Always Free », et Oracle n'arrête plus le serveur quand il est peu utilisé.
2. **Clé SSH** sur ta machine : `ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519` (Entrée à chaque question), puis `cat ~/.ssh/id_ed25519.pub` pour l'afficher.
3. **Le serveur** : *Compute → Instances → Create instance*. Image : **Canonical Ubuntu 24.04** ; *Shape* : **Ampere → VM.Standard.A1.Flex, 2 OCPU, 12 Go** (le maximum gratuit) ; réseau : nouveau réseau avec sous-réseau public, « Assign a public IPv4 address » coché ; *SSH keys* : « Paste public keys », coller la ligne de l'étape 2. *Create*. Si Oracle répond « Out of capacity » : réessayer plus tard ou choisir un autre *availability domain*. Noter l'**adresse IP publique** du serveur.
4. **Ouvrir les ports 80 et 443** : sur la page du serveur, cliquer le *subnet*, puis sa *Default Security List* → *Add Ingress Rules* : *Source CIDR* `0.0.0.0/0`, protocole TCP, *Destination port range* `80,443`.
5. **Une adresse DuckDNS à part** : sur https://www.duckdns.org, un autre nom que celui de l'essai du § 9 bis (ex. `mwangaza-goma`) → *add domain*. Même *token* que pour le § 9 bis.
6. `make deploy-setup` : la première fois, il crée `infra/serveur/serveur.env` (hors Git, avec des secrets neufs) et s'arrête. Y remplir `SERVEUR=ubuntu@<adresse IP de l'étape 3>`, `MWANGAZA_DOMAIN=mwangaza-goma.duckdns.org` et `DUCKDNS_TOKEN=`. Relancer `make deploy-setup` (≈ 5 min : mises à jour automatiques, Docker, pare-feu, SSH par clé seulement). Puis **copier `serveur.env` en lieu sûr** : sans lui, chacun devrait relier son application d'authentification.
7. `make deploy` (≈ 15 min la première fois : l'application est construite sur le serveur), puis `make deploy-demo` : les données fictives ; le mot de passe des comptes fictifs s'affiche (c'est `DJANGO_DEMO_PASSWORD` de `serveur.env`, propre à ce serveur ; ne le donner qu'à ceux à qui tu montres l'application). Pour un visiteur précis, préfère un espace à lui : console → Écoles → « Nouvelle école », type Démonstration, puis sa fiche d'accès (PDF) ; « Remettre à zéro » avant le visiteur suivant.
8. Ouvrir `https://www.mwangaza-goma.duckdns.org/` : un QR code par application. Les comptes fictifs (directeur `0000001001`, caissière `0000001005`…) entrent avec le mot de passe seul : un espace de démonstration ne demande pas de code à 6 chiffres. Console (`https://admin.mwangaza-goma.duckdns.org/`) : avec **ton** compte super-admin, créé par `make deploy-superuser` (il n'y a pas de compte `0000000000` hors développement) ; sa première connexion se termine dans l'administration, où il lie Google Authenticator (QR code) ; garder les codes de secours.

Ensuite :

- **Mettre à jour** après une PR fusionnée : `git switch main && git pull && make deploy` (l'ancienne version reste en ligne pendant la construction).
- **Remettre la démo à zéro** : `make deploy-demo` (les applications d'authentification déjà liées sont gardées). Un client a lié son téléphone à un compte : console → Comptes → « Réinitialiser la double authentification ».
- **Ton propre compte super-admin** (ton numéro), nécessaire pour la console : `make deploy-superuser`.
- **Un problème** : `make deploy-logs` (journaux ; `make deploy-logs service=caddy` pour le certificat), ou dans Claude Code : `/deployer panne`.

Limites : Oracle peut arrêter un serveur gratuit peu utilisé (sauf compte *Pay As You Go*) : le redémarrer sur le site d'Oracle ; si son adresse IP a changé, corriger `SERVEUR` puis `make deploy`. Pas de sauvegarde : jamais de vraies données ici (§ 9).

---

## 10. Comment relire et fusionner une PR

Tu es le chef de projet et le relecteur ; Claude est le développeur. Il code, teste et ouvre **une seule PR par tâche** (corrections et documents compris), toujours sur `main`. Il te la donne dès qu'elle est poussée, contrôles GitHub en cours (≈ 5 min) : commence tes tests pendant ce temps ; il te dit « ✅ contrôles verts » ensuite. **Toi seul fusionnes**, et seulement après le ✅.

Chaque PR se termine par trois sections en français simple : **« À valider »**, **« À tester toi-même »**, **« Après la fusion »**. Le message de fin de Claude dans le terminal reprend les mêmes.

**En 5 étapes** (10 à 20 minutes) :

1. **Ouvrir la PR** : le lien donné par Claude, ou `gh pr view <numéro> --web`. En haut, vérifier **`base: main`** ; sinon, ne pas fusionner et le dire à Claude.
2. **Contrôles verts** : en bas de la page, « All checks have passed » ✔ (ou `gh pr checks <numéro>`). Une croix rouge ✘ : ne pas fusionner, donner le numéro à Claude. Un contrôle gris « Skipped » est normal : il n'a pas de rapport avec les fichiers de la PR (une PR de documents ou de maquettes ne lance aucun test, une PR d'écrans ne lance pas les tests du serveur) ; tout est relancé sur `main` après la fusion.
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
| `make demo` | crée ou remet à jour les données fictives : identité de la plateforme de départ (nom « Mwangaza », couleurs, sans logo) avec un téléphone de support et des mentions légales fictifs ; écoles `itig` et `volcans`, rangées comme **espaces de démonstration** (onglet « Démonstration » de la console, hors de ses chiffres), avec leur année 2026-2027, leurs classes, leur format de matricule, leurs frais (grille fictive) et leur taux de l'année ; ~800 élèves à l'ITIG et ~150 aux Volcans avec leurs familles ; réductions, caisses, paiements depuis la rentrée, crédits et demandes d'annulation ; annonces des écoles et trois annonces de la plateforme (non lues à chaque fois : le bandeau s'affiche) et leurs notifications au personnel (non lues aussi : la cloche montre leur nombre) ; un compte par rôle et un compte parent du portail, trois demandes de coordonnées des parents, environ une famille sur trois déjà inscrite au portail (liste des comptes, mot de passe et clé de double authentification affichés à la fin ; le code à 6 chiffres n'est demandé qu'en développement, au directeur, au comptable et à la caissière — les autres comptes, promoteur compris, entrent sans code ; super-admin `0000000000` en développement seulement ; détail : `docs/07-a-fournir.md` § 4) ; débloque les connexions bloquées par des essais ratés ; refusé en production (sauf les essais et le serveur de démonstration) | après `make migrate`, ou pour remettre la démonstration à zéro |
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
| `make build` | construit les applications ; la Gestion devient installable (service worker) : l'essayer avec `cd frontend/apps/gestion && pnpm preview`, puis http://itig.localhost:4173/app/ | avant la mise en production |
| `make guide` | écrit le guide de la version en PDF, `docs/guide/guide-v1.0.pdf` (ce qu'elle fait, rôle par rôle, avec des captures des écrans sur les données fictives ; ce qu'elle ne fait pas encore ; la suite) : se connecte avec chaque compte fictif, prend les captures, puis imprime le guide ; **remet les données de `make demo` à zéro, avant et après** ; lance Django, la Gestion et le Portail, ou réutilise ceux de `make dev` / `make dev-local` (≈ 3 min) | à la fin de chaque version (Claude met le texte à jour) ; le PDF est dans Git, prêt à envoyer |
| `make prod-local` | essaie la production sur ta machine : construit les mêmes images que le serveur (Gestion et Portail construits, Django avec gunicorn, Caddy en HTTPS) et les lance ; puis https://itig.localhost/app/, https://parents.localhost/, https://admin.localhost/ (console ; administration de dépannage à `/admin/`) (certificat local : accepter l'avertissement du navigateur). Base vide : `make demo` y est refusé | pour voir la production avant la mise en ligne ; la première fois ≈ 10 min (téléchargements) |
| `make prod-local-stop` | arrête cet essai ; ses données sont gardées (`docker compose -p mwangaza-essai down --volumes` pour tout effacer) | après l'essai |
| `make reseau` | essai sur plusieurs appareils du même réseau (§ 9 bis) : met l'adresse de la machine dans DuckDNS, écrit la page des QR codes, construit et lance l'application avec un vrai certificat ; la première fois, crée `infra/reseau/reseau.env` à remplir | pour essayer sur des téléphones ou montrer l'application |
| `make reseau-demo` | données fictives dans cet essai (comme `make demo`, sans code à 6 chiffres ni super-admin fictif) | la première fois, ou pour tout remettre comme au départ |
| `make reseau-superuser` | crée ton compte super-administrateur dans cet essai (ton numéro, un mot de passe) | une fois, pour ouvrir la console |
| `make reseau-ip` | remet l'adresse de la machine dans DuckDNS (`make reseau-ip ip=192.168.…` pour la choisir) | quand le partage de connexion a changé |
| `make reseau-stop` | arrête cet essai ; données et certificat gardés | après l'essai |
| `make deploy-setup` | serveur de démonstration en ligne (§ 9 ter) : prépare le serveur (mises à jour automatiques, Docker, pare-feu, SSH par clé) ; la première fois, crée `infra/serveur/serveur.env` à remplir | une seule fois |
| `make deploy` | met en ligne la dernière version de `main` sur le serveur de démonstration : met son adresse dans DuckDNS, envoie le code, construit l'application sur le serveur et la relance (`make deploy ref=origin/<branche>` pour une autre branche) | après une PR fusionnée que tu veux montrer |
| `make deploy-demo` | données fictives sur le serveur de démonstration, avec le mot de passe propre au serveur (affiché à la fin) ; chacun lie son application d'authentification à la première connexion | la première fois, ou pour remettre la démo à zéro |
| `make deploy-superuser` | crée un compte super-administrateur sur le serveur de démonstration | pour ton propre compte |
| `make deploy-logs` | derniers journaux du serveur et version en ligne (`make deploy-logs service=django`, `caddy`…) | quand quelque chose ne marche pas |
| `make deploy-ssh` | ouvre une session sur le serveur | dépannage |
| `make superuser` | crée un compte super-administrateur (identifiant : ton numéro de téléphone) ; à sa première connexion à l'administration, il active la double authentification (clé à saisir dans Google Authenticator ou Aegis) | rarement en développement : `make demo` y crée un (`0000000000`) |
| `make shell` | console Django | explorer les données |
| `python3 maquettes/outils/maquettes.py menu` | réécrit le menu latéral de toutes les maquettes Gestion | après un changement de menu |
| `python3 maquettes/outils/maquettes.py index` | régénère la galerie `maquettes/index.html` | après une nouvelle maquette |
| `node maquettes/outils/captures.mjs` | refait les captures PNG des maquettes | après une modification de maquette |

### Prévues (arrivent avec leur tâche)

Le nom exact est fixé pendant la tâche ; ce tableau est mis à jour à ce moment-là.

| Commande | Tâche | Effet |
|---|---|---|
| sauvegarde et restauration | 4.7.1 | sauvegarde de la base, test de restauration |

### Adresses en développement

| Adresse | Quoi |
|---|---|
| http://itig.localhost:5173/app/ | Gestion (le sous-domaine = code de l'école) : connexion avec un compte de `make demo` (mot de passe `mwangaza-demo`, code de `make totp`), menu selon le rôle ; caissier et comptable : guide de première connexion (« Aide et guide » en bas du menu pour le revoir) |
| http://itig.localhost:5173/app/account | Mon compte : langue, mot de passe, double authentification, écoles, déconnexion |
| http://itig.localhost:5173/app/settings | Paramètres de l'école : nom, logo, couleur, fuseau, devises (directeur) |
| http://itig.localhost:5173/app/organisation | Organisation scolaire : année, découpage, niveaux, options, classes, matricule — son format, et l'interrupteur « Attribuer un matricule automatiquement » (sur non, l'école garde les siens ou n'en a pas) (directeur, directeur des études `0000001002`) |
| http://itig.localhost:5173/app/staff · …/app/roles | Comptes du personnel ; Rôles et permissions (directeur) ; dans un espace de démonstration (`itig`, `volcans`), une personne s'ajoute avec un numéro fictif commençant par `000` (ex. `0001234567`), jamais un vrai numéro — et l'inverse dans un espace réel ou d'essai |
| http://itig.localhost:5173/app/audit | Journal d'audit : qui a fait quoi, quand (directeur, promoteur) |
| http://itig.localhost:5173/app/dashboard | Tableau de bord : encaissé, recouvrement, alertes (directeur `0000001001`, comptable `0000001004`) |
| http://itig.localhost:5173/app/students | Élèves : liste, fiche (identité, famille, finances, historique), nouvel élève, import Excel (`/app/students/import` : « Imports précédents », puis « Annuler cet import » sur un import fini), liste de classe, fiche d'inscription, situation financière, invitations au portail par classe (`/app/students/invitations` : lettres, message WhatsApp ou SMS, familles pas encore inscrites) (secrétaire `0000001006`, directeur) |
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
| http://itig.localhost:5173/api/auth/totp/setup/ · …/totp/activate/ | étape `totp_setup` : nouvelle clé, puis premier code (`make totp key=<clé>`) → 8 codes de secours ; seulement dans un espace réel ou d'essai (un espace de démonstration ne demande pas la double authentification) |
| http://itig.localhost:5173/api/auth/password/ · …/logout/ | nouveau mot de passe (provisoire, ou le sien) ; se déconnecter |
| http://itig.localhost:5173/api/me/ | le compte connecté, ses écoles, ses rôles et permissions dans l'école de l'adresse |
| http://itig.localhost:5173/api/roles/ · …/api/staff/ | rôles et comptes du personnel de l'école (directeur seulement) |
| http://itig.localhost:5173/api/audit/ | journal d'audit de l'école, le plus récent d'abord (directeur et promoteur) ; filtres dans l'adresse : `?domain=roles`, `?action=auth.login`, `?since=2026-09-26`, `?search=nom` |
| http://itig.localhost:5173/api/school/settings/ · …/settings/logo/ | paramètres de l'école : nom, nom officiel, couleur, fuseau horaire, devises ; logo (directeur) |
| http://itig.localhost:5173/api/school/logo/ | logo de l'école (public) |
| http://itig.localhost:5173/api/support/ | session support « en tant qu'école » : super-admin connecté à l'adresse de l'école (mot de passe et code), motif, 1 heure au plus |
| http://admin.localhost:5175/ | **Console de la plateforme** (super-admin `0000000000`, mot de passe `mwangaza-demo`, puis le code de `make totp`) : tableau de bord des écoles réelles (les espaces d'essai et de démonstration n'y comptent pas ; écoles par statut, élèves, paiements et encaissé du jour par devise, écoles les plus actives, santé du serveur) ; **Identité de la plateforme** (http://admin.localhost:5175/identity : nom, logo, icône, couleurs avec aperçu, support, mentions légales ; changer le nom ne demande pas de code ; les 5 dernières modifications) ; **Écoles** (http://admin.localhost:5175/schools : un onglet par type d'espace — Réels, Essai, Démonstration —, chiffres des espaces réels, recherche, filtre par état, élèves, abonnement, dernière activité, « Ouvrir en tant qu'école » ; « Nouvelle école » http://admin.localhost:5175/schools/new avec son type d'espace (choisi une fois pour toutes) et son premier directeur — mot de passe provisoire affiché une seule fois ; type **Démonstration** : seulement un nom, un code et « Petite école » (≈ 150 élèves) ou « Grande école » (≈ 800) — l'espace se remplit seul de données fictives en moins d'une minute, puis sa fiche donne la **fiche d'accès** à remettre au visiteur (adresses, mot de passe, un numéro par rôle, parents du portail ; « Télécharger le PDF ») et « Remettre à zéro » (même adresse, mêmes numéros, nouveau mot de passe) ; au plus 5 espaces de démonstration sur la plateforme (`DJANGO_DEMO_SPACES_MAX`), un seul se crée ou se supprime à la fois ; fiche `/schools/<id>` : type d'espace, noms, adresse, abonnement, suspendre / réactiver, arrêter avec un motif / relancer, derniers changements ; pour un espace d'essai ou de démonstration seulement : « Supprimer », en retapant son code — tout est effacé pour de bon en quelques secondes, l'espace reste « Suppression en cours » puis disparaît de la liste) ; **Comptes** (http://admin.localhost:5175/accounts : chercher une personne par son nom ou son numéro dans toutes les écoles, ses écoles et rôles, ses familles du portail ; fiche : noms et téléphone, mot de passe provisoire affiché une seule fois — pas pour un parent seul, son école lui donne un nouveau code famille —, double authentification réinitialisée si le téléphone est perdu, désactiver / réactiver, derniers changements ; un compte super-admin ne se change que dans l'administration) ; **Annonces** (http://admin.localhost:5175/announcements : écrire un message à toutes les écoles ou à certaines, publié tout de suite dans la Gestion de leur personnel ; « lue par N personnes » ; archiver pour le retirer — une annonce ne se modifie pas) ; **Appareils** (http://admin.localhost:5175/devices : appareils mémorisés de toutes les écoles, recherche, en service ou déconnectés, « Déconnecter » après confirmation — noté au journal de l'école et de la plateforme) ; **Journal** (http://admin.localhost:5175/journal : ce que le support a fait dans la console, filtres par type, période et objet ; onglet « Sessions support » http://admin.localhost:5175/journal/support : sessions ouvertes, fermées ou expirées, motif, nombre d'actions) ; tout autre compte y est refusé ; menu du compte : « Administration de dépannage », « Se déconnecter » |
| http://localhost:8000/admin/ | administration Django, pour le dépannage (aussi à http://admin.localhost:5175/admin/, même session que la console) : super-admin `0000000000`, mot de passe `mwangaza-demo`, puis le code de `make totp` ; comptes, journal ; écoles (avec « Ouvrir en tant qu'école »), identité de la plateforme et journal de la plateforme en lecture seule (ils se modifient dans la console) |
| https://itig.localhost/app/ · https://parents.localhost/ · https://admin.localhost/ | essai de la production (`make prod-local`) : Gestion, Portail, console et administration (`/admin/`) servis par Caddy comme sur le serveur ; base vide : la Gestion affiche « Aucune école à cette adresse » tant qu'aucune école n'est créée ; santé de l'API : https://admin.localhost/api/health/ |
| https://www.mwangaza-demo.duckdns.org/ (ton nom DuckDNS) | essai sur plusieurs appareils (`make reseau`, § 9 bis) : page avec les QR codes ; puis `https://itig.…/app/`, `https://volcans.…/app/`, `https://parents.…/`, `https://admin.…/`, depuis tout appareil du même réseau, vrai certificat |
| https://www.mwangaza-goma.duckdns.org/ (ton second nom DuckDNS) | serveur de démonstration en ligne (`make deploy`, § 9 ter) : mêmes applications, depuis n'importe quel réseau ; comptes fictifs avec le mot de passe du serveur (`DJANGO_DEMO_PASSWORD` de `infra/serveur/serveur.env`) ; santé de l'API : `https://admin.….duckdns.org/api/health/` |

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
| `/deployer …` | mettre en ligne ou à jour le serveur de démonstration, le dépanner (`/deployer panne`) |
| `/design`, `/backend`, `/argent`, `/hors-ligne` | utilisées par Claude pendant les tâches |

---

## 12. Dépannage

| Message | Cause | Solution |
|---|---|---|
| `permission denied … docker.sock` | pas encore reconnecté après `usermod` | se déconnecter / reconnecter (ou `newgrp docker` dans ce terminal) |
| `port is already allocated` (5433, 6379, 8000, 5173 ; 80 et 443 avec `make prod-local`) | un autre programme utilise le port | `ss -ltnp \| grep 6379` pour le trouver ; par ex. `sudo systemctl stop redis-server` |
| `InconsistentMigrationHistory: Migration admin.0001_initial is applied before its dependency accounts.0001_initial` (`make migrate`, `make test`, `make dev`) | base de développement créée avant la tâche 1.2 (nouveau modèle de compte) | `make reset-db` une fois |
| `"code": "too_many_attempts"` à la connexion | 5 essais ratés pour ce numéro en 15 minutes (ou 30 depuis ta machine) | attendre 15 minutes, ou `make demo` (débloque tout en développement) |
| `"code": "totp_required"` sur une page de l'école | session ouverte sans double authentification, alors qu'un rôle l'exige (ex. rôle donné pendant la session) | se déconnecter (`…/api/auth/logout/`) et se reconnecter |
| `"code": "invalid_code"` avec le code de `make totp` | code déjà utilisé (un code ne sert qu'une fois) | attendre le code suivant (30 secondes) et refaire `make totp` |
| `make test-e2e` : `Executable doesn't exist at …/ms-playwright/…` | Chromium de Playwright pas encore téléchargé | une fois : `cd frontend && pnpm exec playwright install chromium` |
| `make test-e2e` : « Ce code n'est pas valable, ou il a déjà servi » | tu t'es connecté avec le même compte fictif dans les 30 secondes d'avant (un code ne sert qu'une fois) | relancer `make test-e2e` (il remet la démonstration à zéro au début) |
| PDF (fiche d'inscription, liste de classe) : `cannot load library 'libpango-1.0-0'`, ou avertissement `HarfBuzz-Subset will be required` (`make dev-local`, `make test`) | bibliothèques de WeasyPrint absentes de ta machine (Docker les a déjà) | `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0` |
| Le Portail change de compte ou se déconnecte tout seul, en développement | l'administration Django (`http://localhost:8000/admin/`) et le Portail (`http://localhost:5174/`) sont tous deux à `localhost` : ils partagent le même cookie de session, quel que soit le port | ouvrir l'administration dans une fenêtre privée, ou se reconnecter au Portail (rien de tel en ligne : chaque application a son adresse) |
| La Gestion affiche « Pas de connexion au serveur » | Django ne tourne pas (ou pas encore) | lancer `make dev-local` ou `make dev`, puis « Réessayer » |
| La Gestion affiche « Aucune école à cette adresse » | adresse sans code d'école (`localhost:5173/app/`) ou code inconnu | http://itig.localhost:5173/app/ ; après `make demo` si la base est neuve |
| Administration Django : impossible de supprimer une école ou un compte (« objets protégés », `Journal d'audit`) | l'école ou le compte apparaît dans le journal d'audit, qui ne s'efface jamais ; une école ne se supprime jamais (bouton retiré) | suspendre l'école, désactiver le compte ; en développement seulement, `make reset-db` repart d'une base vide |
| Administration Django : la connexion demande un code, ou revient au numéro et au mot de passe | depuis la tâche 1.5, l'administration exige la double authentification du super-admin | numéro, mot de passe, puis le code de `make totp` (compte `0000000000` de `make demo`) ; compte créé par `make superuser` : activer la double authentification avec la clé affichée |
| Administration Django, fichier Excel ou PDF en anglais alors qu'on attend du français | le serveur suit la langue choisie dans l'application (Gestion ou Portail) sur ce navigateur | choisir « Français » sur la page de connexion, dans « Mon compte » ou dans le profil du portail, puis recharger |
| `"code": "no_support_session"` sur `/api/support/`, ou `permission_denied` pour le super-admin à l'adresse d'une école | pas de session support ouverte (ou fermée au bout d'une heure) | ouvrir la session : sur la page `/api/support/`, écrire le motif, **POST** |
| `connection refused` (port 5433) ou `role "mwangaza" does not exist` | pas de `.env`, ou base Docker arrêtée | `cp .env.example .env` (§ 7) ; les commandes `make` qui ont besoin de la base la démarrent d'elles-mêmes (sinon : `make services`, et lire son message) |
| « Failed », `[ELIFECYCLE] Command failed` ou `ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL` en arrêtant `pnpm dev` ou `make dev` | pnpm compte l'arrêt de Vite comme un échec | rien à faire : c'est normal (`make dev-local` ne l'affiche plus) |
| `ERR_PNPM_UNEXPECTED_STORE` | `pnpm` lancé depuis un autre terminal (celui de VS Code et celui d'Ubuntu ne rangent pas le cache au même endroit) | `cd frontend && pnpm install`, répondre `Y` pour réinstaller ; ensuite, toujours le même terminal |
| `bad interpreter` ou `No such file` dans `backend/.venv` | dossier déplacé ou renommé | `rm -rf backend/.venv && make install` |
| `itig.localhost` ne s'ouvre pas | navigateur qui ne gère pas `*.localhost` | utiliser Chrome ou Firefox |
| `git commit` échoue avec `ruff … Failed` ou `Prettier … Failed` et « files were modified by this hook » | le contrôle avant commit a corrigé le format | `git add` les fichiers corrigés, puis refaire le `git commit` |
| `git commit` échoue avec `ESLint … Failed` ou `ruff (lint Python) … Failed` | une vraie erreur dans le code (variable inutilisée, hook React mal placé…) | corriger l'erreur affichée, puis refaire le commit |
| `git commit` : `uv: not found` ou `frontend/node_modules/.bin/eslint: not found` | outils pas installés, ou `uv` absent du `PATH` du programme qui commite | `make install` ; commiter depuis le terminal de VS Code |
| `make deploy…` : `Permission denied (publickey)` | la clé SSH donnée à Oracle n'est pas celle de cette machine, ou `SERVEUR` n'est pas `ubuntu@…` | vérifier `SERVEUR` dans `infra/serveur/serveur.env` ; `ssh ubuntu@<IP>` doit ouvrir une session |
| `make deploy…` : `REMOTE HOST IDENTIFICATION HAS CHANGED` | serveur recréé à la même adresse IP | `ssh-keygen -R <IP>`, puis relancer |
| `make deploy…` : délai dépassé, ou le site ne répond plus | serveur arrêté par Oracle, ou ports 80 et 443 fermés | § 9 ter, « Limites » et étape 4 ; dans Claude Code : `/deployer panne` |
| une PR a une croix rouge ✘ (CI) | un contrôle échoue sur GitHub | `gh pr checks <numéro>` puis ouvrir le lien ; ou dire à Claude le numéro de la PR |

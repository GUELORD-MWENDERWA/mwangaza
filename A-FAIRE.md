# À faire de ton côté

Ce que **toi seul** peux faire, comment le faire, et toutes les commandes du projet.
Claude ne peut pas : installer avec `sudo`, fusionner une PR, parler à l'ITIG, acheter, créer des comptes. Il met ce fichier à jour dès qu'une action t'attend ou qu'une commande est ajoutée.

Ce qui manque en détail (maquettes, informations ITIG, décisions) : [`docs/07-a-fournir.md`](docs/07-a-fournir.md). Ici : **quoi faire, dans quel ordre, avec quelles commandes**.

Dernière mise à jour : 2026-10-14 (logo M-flamme, alignements au téléphone et site public pour la visibilité sur Google et les IA : action 6 octies).

## Maintenant

| # | Action | Temps | Fait |
|:-:|---|---|:-:|
| 1 | ~~Relire et fusionner la PR « L.0 — plan révisé »~~ : fait (2026-10-13) ; la file des tâches est dans `docs/05-plan-de-travail.md` § 2 | | [x] |
| 2 | ~~Sauvegardes hors du serveur, alertes, suivi d'erreurs (UptimeRobot, copie des clés)~~ : fait (L.1, vérifié le 2026-10-13) | | [x] |
| 3 | ~~Clés du serveur gardées hors du serveur~~ : fait (L.2, 2026-10-13) — garder hors du serveur `BACKUP_PASSPHRASE` (sans elle, les sauvegardes B2 sont illisibles) et une copie de `infra/serveur/serveur.env`** dans un gestionnaire de mots de passe ; changement de chaque clé : [§ 9 septies](#9-septies-garder-et-changer-les-clés-du-serveur-s2) | 2 min | [x] |
| 4 | **Lire le guide de la version** (`docs/guide/guide-v1.1.pdf`, remis à jour pour le lancement : modules, rôles libres, sécurité) et préparer ta présentation (`docs/guide/presentation-v1.1.pdf`) : sur le vrai serveur, dans deux espaces de démonstration créés depuis la console (une grande école, une petite), fiches d'accès imprimées | 1 h | [ ] |
| 5 | **Avant la première vraie école** : ~~essai sur de vrais téléphones et imprimantes (L.4)~~ fait le 2026-10-15, sans défaut ; reste les étapes non cochées du [§ 9 quater « Le jour du lancement »](#9-quater-le-jour-du-lancement-première-vraie-école) | 2 h | [ ] |
| 5 bis | **Pour DOC.1 et DOC.2 (avant L.4)** : préparer, pour une école d'essai, une photo ou un scan net du **cachet** et de la **signature du chef** (et d'un caissier), à l'encre foncée sur papier blanc, en PNG ou JPEG ; avoir quelques feuilles **demi A4** (A5, 21 × 14,8 cm) ou **tiers d'A4** (une feuille A4 coupée en trois, 21 × 9,9 cm) pour essayer l'impression d'un reçu | 15 min | [ ] |
| 6 | **GitHub › Settings › Code security** du dépôt : activer « Secret scanning » et « Push protection » (tâche S.2 : une clé poussée par erreur est bloquée) ; puis **Dependabot** : Settings › Code security › « Dependabot alerts » activé | 5 min | [ ] |
| 6 ter | **PR de Dependabot du 2026-10-13**, après la fusion de S.3.1 : fusionner **#225** (Actions, verte) ; **fermer #223, #226, #221 et #222** si Dependabot ne les a pas fermées lui-même (bouton « Close pull request ») — Django 6.1, TypeScript 7 et Python 3.14 ne se prennent pas ainsi. Il rouvrira des PR propres, sans versions majeures | 5 min | [ ] |
| 6 quater | **Alertes du super-admin sur tes appareils** (S.3.2), après la fusion et `make deploy` : sur chaque appareil (ordinateur, téléphone), ouvrir https://admin.mwangazaschool.com/journal, cliquer « Recevoir les alertes sur cet appareil » et accepter la demande du navigateur. Sur iPhone : d'abord Partager → « Sur l'écran d'accueil », puis ouvrir la console depuis cette icône. Essai : te déconnecter puis te reconnecter → une alerte « Connexion d'un compte de la plateforme » s'affiche sur chaque appareil abonné | 5 min | [ ] |
| 6 quinquies | **Après la fusion de S.4 : `make deploy`** puis `make deploy-check` — la limite de 10 Mo par envoi et la purge du cache de construction (environ 6 Go libérés la première fois) n'existent qu'une fois en ligne. Une école qui avait un logo SVG le garde ; pour le changer, elle envoie un PNG ou un JPEG | 15 min | [ ] |
| 6 sexies | **Après la fusion de S.5 : `make deploy-init`, puis `make deploy` et `make deploy-check`** (une seule mise en ligne suffit pour S.4 et S.5). `make deploy-init` ajoute à `infra/serveur/serveur.env` la ligne `POSTGRES_APP_PASSWORD` : le mot de passe du nouveau compte PostgreSQL de l'application, qui ne peut que lire et écrire des lignes. Sans elle, `make deploy` s'arrête tout de suite et le dit. Ensuite, mets à jour ta copie de `serveur.env` dans le gestionnaire de mots de passe. Fusionnée avant, A.2 (purge de nuit des opérations de synchronisation) part avec la même mise en ligne | 20 min | [ ] |
| 6 septies | **Après la fusion de S.6.1 et S.6.2 : `make deploy`** puis `make deploy-check` (une seule mise en ligne pour les deux) — la Row Level Security (chaque table d'une école ne montre que l'école de la connexion) n'existe sur le serveur qu'une fois la nouvelle version en ligne, et c'est là seulement qu'elle s'applique (le compte `mwangaza_app`). Puis ouvrir https://admin.mwangazaschool.com/ (liste des espaces, Comptes, Journal) et une école de démonstration (Élèves, Caisse, Impayés, un reçu, Annonces) : tout doit s'afficher comme avant ; sur le Portail, le parent de démonstration voit ses enfants. Une liste vide ou une erreur inattendue : `make deploy-logs`, et me le dire | 10 min | [ ] |
| 6 octies | **Visibilité sur Google et les IA**, après la fusion du logo M-flamme et `make deploy` : ① console https://admin.mwangazaschool.com/identity : vrai téléphone (WhatsApp) et e-mail du support — la page publique les affiche ; ② https://search.google.com/search-console → « Ajouter une propriété » → **Domaine** `mwangazaschool.com` → copier l'enregistrement TXT → Cloudflare › DNS › Ajouter un enregistrement TXT (nom `@`) → « Valider » ; puis « Sitemaps » : `https://mwangazaschool.com/sitemap.xml` ; puis « Inspection de l'URL » sur `https://mwangazaschool.com/` et `/en/` → « Demander l'indexation » ; ③ https://www.bing.com/webmasters → « Importer depuis Google Search Console » (Bing alimente ChatGPT, Copilot et DuckDuckGo) ; ④ vérifier : https://search.google.com/test/rich-results?url=https://mwangazaschool.com/ (données structurées valides) et envoie-toi le lien sur WhatsApp (aperçu avec le logo) ; ⑤ facultatif, mais ce qui aide le plus ensuite : des liens vers `mwangazaschool.com` depuis tes profils (LinkedIn, Facebook, GitHub), une fiche Google Business Profile « logiciel » à Goma, les sites des écoles clientes. Compter quelques jours à quelques semaines avant d'apparaître dans les résultats. | 30 min | [ ] |
| 6 bis | **CSP : après une semaine de `make deploy` sans message « Content-Security-Policy » dans la console du navigateur** (F12, sur les trois adresses), ajouter la ligne `CSP_HEADER=Content-Security-Policy` dans `infra/serveur/serveur.env` puis `make deploy` ; **Cloudflare en nuage orange** (DNS › les enregistrements `*`, `admin`, `parents` et la racine) : à faire avec Claude, pas seul | 15 min | [ ] |
| 7 | **Un vrai bulletin EPST rempli** (ou le modèle officiel), photo ou scan, déposé dans `depot/` : il sert au gabarit du bulletin (8.3, V1.2) | 15 min | [ ] |
| 8 | **Démarches Mobile Money et SMS** : contacter un agrégateur (M-Pesa, Airtel Money, Orange Money) et un fournisseur SMS / WhatsApp ; les contrats sont longs à obtenir (9.3 et 9.4, V2) | à ton rythme | [ ] |

Déjà fait : installation de la machine (Docker, `.env`, gettext), décisions (nom, domaine, Q1 à Q11), PR des tâches 0.1 à 4.22, 4.24 et 5.1 à 5.7 ; historique complet : [`docs/06-suivi.md`](docs/06-suivi.md). À chaque PR : [comment la relire et la fusionner](#10-comment-relire-et-fusionner-une-pr) (§ 10). [Rien à demander à l'ITIG](#8-litig--rien-à-demander).

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

Fait **avant** qu'une école saisisse ses vraies données : changer d'adresse ensuite obligerait à réinstaller les applications et rendrait invérifiables les QR des reçus déjà imprimés. Serveur en ligne (§ 9 ter), comptes des sauvegardes et des alertes créés et vérifiés (§ 9 bis, L.1 et L.2, 2026-10-13). Restent les deux dernières lignes.

| Quoi | Comment | Fait |
|---|---|:-:|
| Domaine **`mwangazaschool.com`** | acheté ; renouvellement automatique | [x] |
| Cloudflare (gratuit) | DNS fait ; reste le passage en proxy, nuage orange (« Maintenant » 6 bis, avec Claude) | [x] |
| Serveur | AWS Lightsail (§ 9 ter) | [x] |
| Stockage objet des sauvegardes | **Backblaze B2** (10 Go gratuits, compte séparé d'AWS) : § 9 bis, étapes 1 et 2 | [x] |
| Clé des sauvegardes (4.7.2) | une phrase secrète `BACKUP_PASSPHRASE` dans le fichier de valeurs du serveur : dès qu'elle y est, la sauvegarde de chaque nuit se fait. **La noter aussi hors du serveur** (gestionnaire de mots de passe), avec `DJANGO_SECRET_KEY` : sans ces deux clés, une sauvegarde ne se relit pas | [x] |
| Alerte de sauvegarde, suivi d'erreurs, sonde de disponibilité | Healthchecks.io, Sentry, UptimeRobot (tous gratuits) : § 9 bis, étapes 3 à 5 | [x] |
| Documents (T5, avant les vraies données d'une école) | conditions d'utilisation, confidentialité, contrat avec chaque école : Claude peut rédiger un brouillon, à faire relire | [ ] |
| Tarif des écoles (T6, avant les abonnements, 9.2) | décider : essai gratuit ? prix par élève ? | [ ] |

Partout : activer la double authentification et garder les codes de secours. Les mots de passe et clés vont dans le fichier de valeurs du serveur, jamais dans une conversation ni dans le dépôt : Claude te dira quel nom de variable remplir.

---

## 9 ter. Le vrai serveur AWS Lightsail (en ligne depuis le 2026-10-13)

`infra/serveur/serveur.env` (créé par `make deploy-init`) : MODE=production, `ubuntu@15.236.78.55` (IP statique), clé `~/.ssh/LightsailDefaultKey-eu-west-3.pem`, secrets et clés des services. Cloudflare : enregistrements `A` `@` et `*` vers 15.236.78.55 ; Lightsail › Mise en réseau : 22, 80 et 443 ouverts, en IPv4 et IPv6. **Garder une copie de `serveur.env`** (§ 9 septies). Commandes : `make deploy`, `make deploy-check`, `make deploy-logs`, `make deploy-backup`, `make deploy-ssh` (CLAUDE.md, skill `/deployer`).

**Après la panne du 2026-10-13 (serveur figé pendant la construction)** — fait le 2026-10-13 dans la console Lightsail (à refaire seulement sur un nouveau serveur) :
- **IP statique** (15.236.78.55) : onglet *Mise en réseau* → *Créer une IP statique* → l'attacher à `mwangaza-vps-prod`. Sans elle, un arrêt puis démarrage (pas un simple redémarrage) change l'adresse et casse le DNS et `SERVEUR`. Si l'adresse change, mets-la à jour dans `serveur.env` et dans les enregistrements `A` de Cloudflare (`@` et `*`).
- **HTTPS en IPv6** : dans le pare-feu, la règle HTTPS 443 doit être cochée **aussi pour IPv6** (comme 22 et 80).
- **Alarmes** : onglet *Metrics* de l'instance → *Add alarm* : « Status check failed (instance) » et « CPU utilization » > 90 % pendant 15 min, notification par e-mail. Avec le moniteur UptimeRobot (§ 9 bis, étape 5), tu es prévenu en quelques minutes d'un serveur muet.
- **Mémoire** : `make deploy-setup` pose maintenant 2 Go de swap et protège SSH (sans danger si relancé) ; `make deploy` refuse de construire sans swap. Les conteneurs ont des limites de mémoire : un conteneur qui déborde est relancé seul, la machine ne se fige plus.
- **Disque** : `make deploy` supprime les anciennes images et ramène le cache de construction à 2 Go (S.4 ; il avait atteint 8 Go). Pour voir où va la place : `make deploy-ssh` puis `docker system df`.

## 9 sexies. Guide de démarrage du personnel : installer la Gestion (4.24)

À la première ouverture de `https://<école>.mwangazaschool.com/app/` dans un navigateur, un écran demande d'installer l'application ; il faut le faire **avant** la connexion. Donne ces étapes au personnel :
1. **Android ou ordinateur (Chrome, Edge)** : touche **« Installer l'application »** ; si le bouton manque, menu du navigateur → « Installer l'application ».
2. **iPhone (Safari seulement)** : Partager → « Sur l'écran d'accueil » → Ajouter.
3. Quand l'écran dit « installée », **ferme l'onglet** et ouvre **Mwangaza depuis son icône** (bureau, écran d'accueil ou menu des applications). Le guide de la caisse ou de la comptabilité s'y lance à la première connexion.
4. Appareil qui ne sait pas installer : « Continuer dans le navigateur » apparaît (après 2 refus, sur iPhone, ou sans invite) ; l'écran revient à la prochaine ouverture du navigateur. Les caisses doivent rester sur l'application installée (hors-ligne).

## 9 quater. Le jour du lancement (première vraie école)

Achats, serveur et sauvegardes sont faits ; le code du lancement est fini (L.5, 2026-10-14). Restent les étapes non cochées, dans l'ordre, sans en sauter une. Toutes les adresses sont sur `mwangazaschool.com`.

| # | Étape | Comment | Fait |
|:-:|---|---|:-:|
| 1 | **Achats et comptes** | [§ 9](#9-vraie-mise-en-ligne-463-47--comptes-et-achats) : domaine, Cloudflare, serveur AWS Lightsail, Backblaze B2, Healthchecks, Sentry, UptimeRobot ; `BACKUP_PASSPHRASE` et copie de `serveur.env` gardées **hors du serveur** (L.1, L.2) | [x] |
| 2 | **Vrai domaine** | `mwangazaschool.com` en ligne depuis le 2026-10-13 (4.6.3) : `make deploy-check` vert sur les trois adresses | [x] |
| 3 | **Sauvegardes hors du serveur, alertes** | vérifiées le 2026-10-13 (L.1) : `make deploy-backup` affiche « Copie hors du serveur : b2:… » ; restauration réelle depuis B2 essayée (L.2, [§ 9 bis](#9-bis-brancher-les-sauvegardes-hors-du-serveur-472)) | [x] |
| 4 | **Mesure sur le vrai serveur** | fait le 2026-10-13 (4.23) : tableau de bord 0,6 s, impayés 0,7 s pour 800 élèves, rien à corriger | [x] |
| 5 | **Ton compte super-admin** | créé le 2026-10-13 (`make deploy-superuser`) ; reste : double authentification liée à ton téléphone, codes de secours rangés, alertes de la console sur tes appareils (« Maintenant » 6 quater) | [ ] |
| 5 bis | **Dernière version en ligne** | code des tâches P0 fusionné (modules et rôles libres M.2, M.3 ; sécurité S.1 à S.5 ; L.2, L.5). Mettre en ligne `main` : `make deploy-init` (ajoute `POSTGRES_APP_PASSWORD`, S.5), `make deploy`, `make deploy-check` (« Maintenant » 6 quinquies et 6 sexies) | [ ] |
| 5 ter | **Cloudflare en proxy** | nuage orange sur `@`, `*`, `admin` et `parents`, pare-feu du serveur limité à Cloudflare : **avec Claude**, pas seul (« Maintenant » 6 bis). La CSP imposée attend une semaine sans message : elle ne bloque pas le lancement | [ ] |
| 5 quater | **Essai sur de vrais téléphones** (L.4) | sur `https://<démo>.mwangazaschool.com/app/` : un Android et un iPhone, Gestion installée, caisse hors ligne, imprimante thermique 58 / 80 mm et A4, Portail installé et notifications, QR d'un reçu imprimé scanné. Fait le 2026-10-15, aucun défaut | [x] |
| 6 | **Identité de la plateforme** | console `https://admin.mwangazaschool.com/` → Identité : nom, logo (PNG, JPEG ou SVG), contact du support, mentions légales — les vraies valeurs | [ ] |
| 7 | **Premier espace réel** | console → Écoles → Nouvelle école → type **Réel** : nom, code (c'est son adresse, `https://<code>.mwangazaschool.com/app/` : il ne change plus), **modules** qu'elle prend (les six sont cochés : décocher ceux qu'elle ne prend pas), premier directeur avec son vrai numéro. Lui remettre l'adresse, son mot de passe provisoire et les étapes d'installation ([§ 9 sexies](#9-sexies-guide-de-démarrage-du-personnel--installer-la-gestion-424)) | [ ] |
| 8 | **L'école se met en route** | le directeur suit la liste « Mise en route » de son tableau de bord : année, classes, frais et taux, comptes du personnel, caisse et appareil, élèves (import Excel). Les rôles de départ se renomment à ses mots (« Préfet des études »…). Rentrée déjà passée : « Reprise » (ce que chaque élève a déjà payé) | [ ] |
| 9 | **Premier encaissement** | un vrai paiement : reçu imprimé, QR vérifié avec un téléphone ; le soir, clôture de caisse ; le parent voit le reçu sur `https://parents.mwangazaschool.com/` | [ ] |
| 10 | **Le lendemain** | la sauvegarde de la nuit est arrivée (Healthchecks vert, `make deploy-backup cmd=fetch` si tu veux la voir) ; aucune alerte (Sentry, UptimeRobot) | [ ] |

À ne plus faire une fois l'étape 7 passée : `make demo` sur cette plateforme (refusés d'office dès qu'un espace réel existe) ; changer de domaine ; saisir de vraies données dans un espace d'essai ou de démonstration (ils se suppriment). Montrer l'application à une autre école : console → Écoles → onglet « Démonstration », sa fiche d'accès à imprimer.

---

## 9 bis. Brancher les sauvegardes hors du serveur (4.7.2)

**Fait et vérifié le 2026-10-13 (L.1)** : à refaire seulement pour un nouveau serveur ou une clé changée. Ces sept étapes sont des comptes à créer ; les clés vont dans `infra/serveur/serveur.env` (lignes déjà présentes pour un nouveau fichier ; **à ajouter à la main** dans le tien : `BACKUP_B2_BUCKET`, `BACKUP_B2_ACCOUNT`, `BACKUP_B2_KEY`, `BACKUP_PING_URL`, `SENTRY_DSN`, modèle : `infra/.env.example`). Aucune n'est obligatoire pour que l'application marche, **toutes le sont avant la première vraie école**.

| # | Quoi | Comment |
|:-:|---|---|
| 1 | Bucket B2 | `backblaze.com` → compte B2 → *Buckets* → créer `mwangaza-sauvegardes`, **Private** ; *Lifecycle* : « Keep only the last version of the file ». Le nom va dans `BACKUP_B2_BUCKET` |
| 2 | Clé B2 | *Application Keys* → nouvelle clé **limitée à ce bucket**, lecture et écriture. `keyID` → `BACKUP_B2_ACCOUNT`, `applicationKey` → `BACKUP_B2_KEY` (affichée une seule fois) |
| 3 | Alerte de sauvegarde | `healthchecks.io` → nouveau contrôle, période 1 jour, délai de grâce 2 h, ton e-mail ; son adresse de ping (`https://hc-ping.com/…`, **sans** `/fail`) → `BACKUP_PING_URL` |
| 4 | Suivi d'erreurs | `sentry.io` → projet **Django** → adresse « DSN » → `SENTRY_DSN` |
| 5 | Sonde de disponibilité | `uptimerobot.com` → moniteur HTTP(s) sur `https://admin.mwangazaschool.com/api/health/`, toutes les 5 minutes, alerte par e-mail |
| 6 | Mettre en route | `make deploy-setup` (installe `rclone`, sans danger si déjà fait), puis `make deploy` |
| 7 | Vérifier | `make deploy-backup` : doit afficher « Copie hors du serveur : b2:… » ; le fichier est dans le bucket ; Healthchecks passe au vert. Puis `make deploy-backup cmd=restore` : « Essai réussi » |

**Garder aussi hors du serveur** : `BACKUP_PASSPHRASE`, `DJANGO_SECRET_KEY` et les clés B2 (gestionnaire de mots de passe). Serveur perdu : `make deploy-setup`, `make deploy`, `make deploy-backup cmd=fetch`, puis `make deploy-backup cmd="restore --remplacer"` (remet la sauvegarde en service après confirmation).

**Essai réel du 2026-10-13 (L.2)** : `cmd=fetch` rapatrie la base et les fichiers depuis B2 en ≈ 7 s, `cmd=restore` les déchiffre et les restaure dans une base à part en ≈ 8 s (60 tables, 364 lignes, identique à la base en service table par table ; archive de fichiers vide : aucun logo ni photo encore). Même chose avec une base plus grosse : compter plus long, la durée suit la taille de la sauvegarde. Remplacer la base en service (`--remplacer`) n'a pas été fait sur le vrai serveur : seulement l'essai.

---

## 9 septies. Garder et changer les clés du serveur (S.2)

**Copie** : `infra/serveur/serveur.env` contient toutes les clés. Garde-en une copie dans un gestionnaire de mots de passe (pas sur la même machine ni dans le dépôt) ; sans `DJANGO_SECRET_KEY` et `BACKUP_PASSPHRASE`, une sauvegarde ne se relit pas. Une clé a fuité (poussée par erreur, message envoyé) : la changer **tout de suite**, puis `make deploy`. Clé nouvelle : `openssl rand -base64 48`.

| Clé | Changer |
|---|---|
| `DJANGO_SECRET_KEY` | Mettre l'**ancienne** dans `DJANGO_SECRET_KEY_FALLBACKS` (virgules), la nouvelle dans `DJANGO_SECRET_KEY`, `make deploy`. Sans cela, chacun doit réactiver sa double authentification. |
| `POSTGRES_PASSWORD` | Compte propriétaire de la base : il ne sert qu'aux migrations et aux sauvegardes. `make deploy-ssh`, puis dans le dossier du serveur : `docker compose exec db psql -U mwangaza -c "ALTER USER mwangaza PASSWORD '<nouveau>'"` ; mettre le même dans `serveur.env`, `make deploy`. |
| `POSTGRES_APP_PASSWORD` | Compte de l'application (S.5), sans droit sur la structure de la base. Changer la ligne dans `serveur.env`, puis `make deploy` : la mise en ligne remet le compte à cette valeur. Ligne absente : `make deploy-init` en crée une. |
| `BACKUP_PASSPHRASE` | Les anciennes sauvegardes gardent l'ancienne phrase : la noter avec leur date avant de changer. Nouvelle phrase dans `serveur.env`, `make deploy`, puis `make deploy-backup` et `make deploy-backup cmd=restore`. |
| `BACKUP_B2_KEY` | Backblaze › *Application Keys* : créer une nouvelle clé limitée au bucket, la coller (avec `BACKUP_B2_ACCOUNT`), `make deploy`, `make deploy-backup`, puis supprimer l'ancienne clé. |
| `SENTRY_DSN`, `BACKUP_PING_URL` | Régénérer dans Sentry / Healthchecks, coller, `make deploy`. |
| `WEBPUSH_VAPID_*` | **Ne pas changer** : tous les appareils abonnés devraient se réabonner. |

**Adresses autorisées pour le compte super-admin (facultatif, S.3.1)** : la ligne `DJANGO_CONSOLE_ALLOWED_IPS=` de `serveur.env` (à ajouter ; vide ou absente = toutes les adresses) limite d'où ton compte super-admin peut être utilisé : adresses ou réseaux séparés par des virgules, ex. `41.243.10.25,102.69.0.0/16`, puis `make deploy`. Ailleurs, la console répond « numéro ou mot de passe incorrect » et l'essai est noté au journal (console › Journal › « Accès du super-admin »). **Avec un téléphone en partage de connexion ou une clé 4G, l'adresse change sans cesse : laisse la ligne vide**, sinon tu te fermes la porte ; elle sert le jour où tu as une adresse fixe ou un VPN. Enfermé dehors : `make deploy-ssh`, vider la ligne, `make deploy`. Dans tous les cas, ta session de la console se ferme maintenant après 2 heures sans activité.

**GitHub** : « Secret scanning » et « Push protection » (Settings › Code security) bloquent le `git push` qui contient une clé connue. Les mises à jour de dépendances arrivent chaque lundi en PR « Bump… » (groupées, sans les versions majeures) : coches vertes → tu peux fusionner ; une coche rouge → ne fusionne pas, montre-la à Claude. Une PR qui change `python` ou `node` dans un `Dockerfile` ne se fusionne pas sur ses coches (la CI ne construit pas l'image). L'audit des failles (`audit.yml`) tourne le lundi et sur `main`.

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
| `make demo` | crée ou remet à jour les données fictives : identité de la plateforme de départ (nom « Mwangaza », couleurs, sans logo) avec un téléphone de support et des mentions légales fictifs ; écoles `itig` et `volcans`, rangées comme **espaces de démonstration** (onglet « Démonstration » de la console, hors de ses chiffres), avec leur année 2026-2027, leurs classes et leurs cours (grilles officielles, quelques enseignants), les notes de la 1re période (deux interrogations et un devoir par cours, quelques cases vides), leur format de matricule, leurs frais (grille fictive) et leur taux de l'année ; ~800 élèves à l'ITIG et ~150 aux Volcans avec leurs familles ; réductions, caisses, paiements depuis la rentrée, crédits et demandes d'annulation ; annonces des écoles et trois annonces de la plateforme (non lues à chaque fois : le bandeau s'affiche) et leurs notifications au personnel (non lues aussi : la cloche montre leur nombre) ; notifications du parent fictif (paiement reçu, annonces de l'école), alerte « Droits sensibles » du directeur et annulations à valider pour le directeur et le comptable ; relances aux parents activées dans les deux écoles et envoyées aux familles qui ont un compte (échéance proche, retard de paiement) ; un compte par rôle et un compte parent du portail, trois demandes de coordonnées des parents, environ une famille sur trois déjà inscrite au portail (liste des comptes, mot de passe et clé de double authentification affichés à la fin ; le code à 6 chiffres n'est demandé qu'en développement, au directeur, au comptable et à la caissière — les autres comptes, promoteur compris, entrent sans code ; super-admin `0000000000` en développement seulement ; détail : `docs/07-a-fournir.md` § 4) ; débloque les connexions bloquées par des essais ratés ; refusé en production (sauf les essais et le serveur de démonstration), et partout dès qu'un espace réel existe (les démonstrations se créent alors dans la console) | après `make migrate`, ou pour remettre la démonstration à zéro |
| `make relances` | envoie tout de suite les notifications à heure fixe du jour : relances aux parents (échéance proche, retard) des écoles qui les ont activées, « Caisse encore ouverte » au directeur et au comptable ; efface celles de plus de 90 jours ; une école déjà servie aujourd'hui ne reçoit rien de plus | essayer les relances sans attendre 8 h ou l'heure de clôture (en service, le serveur le fait seul toutes les 15 minutes) |
| `make totp` | affiche le code de double authentification du moment pour les comptes fictifs qui la demandent (super-admin, directeur, comptable, caissière) ; `make totp key=<clé>` : pour la clé donnée à l'activation ; seulement en développement | se connecter sans téléphone ; ou ajouter une fois la clé affichée par `make demo` dans Google Authenticator ou Aegis |
| `make demo-excel` | écrit `eleves-fictifs.xlsx` à la racine du projet : une liste de ~800 élèves fictifs comme en tient un secrétariat (titre, colonnes NOM, POSTNOM…, fratries, quelques erreurs glissées exprès) ; seulement en développement | essayer l'import des élèves (Élèves → Importer Excel) |
| `make messages` | met à jour les traductions françaises des textes du serveur (`backend/locale/fr/…/django.po`), puis les compile ; demande gettext (`sudo apt install gettext`) ; tous les textes du serveur sont traduits, un test le vérifie | quand Claude le demande ; les fichiers compilés sont dans Git |
| `make test` | tous les tests | avant de fusionner une PR |
| `make test-back` | tests backend (pytest) | |
| `make test-front` | vérification des types du front, puis tests Vitest (logique et écrans) | |
| `make test-e2e` | parcours dans un vrai navigateur (Playwright) : connexion, console du super-admin, menu, activation, session support, paramètres, caisse sans réseau, démarrage hors ligne avec le PIN, école neuve de bout en bout (espace créé dans la console → mise en route → encaissement → le parent voit le reçu)… ; **remet les données de `make demo` à zéro, avant et après** ; lance Django, la Gestion, le Portail et la console, ou réutilise ceux de `make dev-local` | une fois avant : `cd frontend && pnpm exec playwright install chromium` ; ensuite quand tu veux, la CI le fait à chaque PR |
| `make lint` | vérifie le code sans rien modifier : ruff (Python), ESLint et Prettier (front) ; `make lint-back` ou `make lint-front` pour une seule partie | avant de fusionner une PR |
| `make format` | corrige automatiquement le format et ce qui peut l'être | quand `make lint` signale un problème de format |
| `make api` | écrit le schéma OpenAPI dans `frontend/packages/api/openapi.yaml`, puis les types TypeScript du client (`src/schema.d.ts`) ; `make api-schema` : seulement le schéma | après tout changement d'API |
| `make build` | construit les applications ; la Gestion devient installable (service worker) : l'essayer avec `cd frontend/apps/gestion && pnpm preview`, puis http://itig.localhost:4173/app/ | avant la mise en production |
| `make apercu` | photographie **chaque écran** des trois applications (Gestion, portail des parents, console) à trois largeurs : téléphone (390 px), tablette (820 px), ordinateur (1440 px) ; les images vont dans `frontend/apercu/captures/` (un dossier par application et par largeur, et `documents/` pour les documents imprimés : situation financière, fiche d'inscription, liste de classe, impayés, lettres, circulaire, convocation), et `rapport.json` liste ce qui dépasserait de l'écran (vide = tout tient) ; `make apercu ecran=portail` pour une seule application, `make apercu ecran=gestion/dashboard` pour un seul écran ; lit les données de `make demo` sans les changer (≈ 3 min) | pour voir d'un coup tout le design, par exemple avant de valider une refonte |
| `make guide` | écrit deux PDF : le guide de la version, `docs/guide/guide-v1.1.pdf` (le guide de la V1.0 reste à côté ; ce qu'elle fait, rôle par rôle, avec des captures des écrans sur les données fictives ; ce qu'elle ne fait pas encore ; la suite), et le **guide de présentation**, `docs/guide/presentation-v1.1.pdf` (pour toi, quand tu montres la plateforme à une école : commandes de l'essai sur plusieurs appareils, adresses, comptes de test, déroulé en 20 minutes écran par écran, questions de la fin) : se connecte avec chaque compte fictif, prend les captures, puis imprime le guide ; **remet les données de `make demo` à zéro, avant et après** ; lance Django, la Gestion et le Portail, ou réutilise ceux de `make dev` / `make dev-local` (≈ 3 min) | à la fin de chaque version (Claude met le texte des deux à jour) ; les PDF sont dans Git : le guide de la version est prêt à envoyer, le guide de présentation reste pour toi |
| `make prod-local` | essaie la production sur ta machine : construit les mêmes images que le serveur (Gestion et Portail construits, Django avec gunicorn, Caddy en HTTPS) et les lance ; puis https://itig.localhost/app/, https://parents.localhost/, https://admin.localhost/ (console ; administration de dépannage à `/admin/`) (certificat local : accepter l'avertissement du navigateur). Base vide : `make demo` y est refusé | pour voir la production avant la mise en ligne ; la première fois ≈ 10 min (téléchargements) |
| `make prod-local-stop` | arrête cet essai ; ses données sont gardées (`docker compose -p mwangaza-essai down --volumes` pour tout effacer) | après l'essai |
| `make deploy-init` · `make deploy-check` | vrai serveur AWS (§ 9 ter) : créer `serveur.env` de production, ou y ajouter une clé apparue depuis (`POSTGRES_APP_PASSWORD`, S.5) ; vérifier HTTPS et la santé de l'API | une fois / après chaque mise en ligne |
| `make deploy-setup` | prépare le serveur (mises à jour automatiques, Docker, pare-feu, SSH par clé) | une seule fois |
| `make deploy` | met en ligne la dernière version de `main` sur le vrai serveur : envoie le code, construit l'application sur le serveur et la relance (`make deploy ref=origin/<branche>` pour une autre branche) | après une PR fusionnée que tu veux montrer |
| `make deploy-superuser` | crée un compte super-administrateur sur le vrai serveur | pour ton propre compte |
| `make deploy-logs` | derniers journaux du serveur et version en ligne (`make deploy-logs service=django`, `caddy`…) | quand quelque chose ne marche pas |
| `make deploy-backup` | lance la sauvegarde **maintenant** sur le serveur, copie vers Backblaze comprise (celle de la nuit fait la même chose) ; `cmd=fetch` rapatrie la dernière copie du bucket (serveur neuf), `cmd=restore` essaie de la relire | après avoir rempli § 9 bis ; une fois par mois pour l'essai |
| `make deploy-ssh` | ouvre une session sur le serveur | dépannage |
| `make backup` | sauvegarde ta base et tes fichiers (logos, photos, pièces jointes) dans `sauvegardes/dev/`, chiffrés ; efface aussi les sessions expirées et les vieilles sauvegardes (base : 30 jours, fichiers : 7) | pour essayer ; sur le serveur, c'est fait chaque nuit tout seul |
| `make restore` | essai de restauration : la dernière sauvegarde est relue dans une base à part et comparée à la base en service, puis la base à part est effacée (rien ne change). `make restore file=sauvegardes/dev/<fichier>` pour une autre ; `make restore remplacer=oui` la remet en service (il faut taper REMPLACER ; l'ancienne base est gardée) | une fois par mois sur le serveur ; `remplacer=oui` seulement après une panne |
| `make superuser` | crée un compte super-administrateur (identifiant : ton numéro de téléphone) ; à sa première connexion à l'administration, il active la double authentification (clé à saisir dans Google Authenticator ou Aegis) | rarement en développement : `make demo` y crée un (`0000000000`) |
| `make shell` | console Django | explorer les données |
| `python3 maquettes/outils/maquettes.py menu` | réécrit le menu latéral de toutes les maquettes Gestion | après un changement de menu |
| `python3 maquettes/outils/maquettes.py index` | régénère la galerie `maquettes/index.html` | après une nouvelle maquette |
| `node maquettes/outils/captures.mjs` | refait les captures PNG des maquettes (téléphone et bureau) et signale tout ce qui dépasse de l'écran | après une modification de maquette |

### Prévues (arrivent avec leur tâche)

Le nom exact est fixé pendant la tâche ; ce tableau est mis à jour à ce moment-là.

Rien pour l'instant.

### Adresses en développement

| Adresse | Quoi |
|---|---|
| http://itig.localhost:5173/app/ | Gestion (le sous-domaine = code de l'école) : connexion avec un compte de `make demo` (mot de passe `mwangaza-demo`, code de `make totp`), menu selon le rôle ; caissier et comptable : guide de première connexion (« Aide et guide » en bas du menu pour le revoir) |
| http://itig.localhost:5173/app/account | Mon compte : langue, ma signature (posée sur les reçus que je donne), mot de passe, double authentification, écoles, déconnexion |
| http://itig.localhost:5173/app/settings | Paramètres de l'école : nom, logo, couleur, fuseau, devises, alertes au directeur, relances aux parents (à activer ; jours avant l'échéance, intervalle des rappels), cachet de l'école, nom, titre et signature du chef (directeur) |
| http://itig.localhost:5173/app/organisation | Organisation scolaire : année, découpage, niveaux, options, classes, matricule — son format, et l'interrupteur « Attribuer un matricule automatiquement » (sur non, l'école garde les siens ou n'en a pas) (directeur, directeur des études `0000001002`) |
| http://itig.localhost:5173/app/courses | Cours et maxima (directeur, directeur des études ; module « Cours, notes et bulletins ») : choisir la classe, appliquer un modèle officiel, corriger maxima, examen, heures et enseignant, « Enregistrer » ; « Copier vers d'autres classes » |
| http://itig.localhost:5173/app/teaching-loads | Charges des enseignants : heures par semaine de chacun, cours sans enseignant |
| http://itig.localhost:5173/app/grades | Saisie des notes : un cours, une période, ses évaluations et les notes des élèves (enseignant `0000001008` : ses cours ; secrétaire : toutes les classes) |
| http://itig.localhost:5173/app/grade-validation | Validation des notes (directrice des études `0000001002`, avec le code de `make totp`) : feuilles envoyées à ouvrir et valider, dates limites de saisie |
| http://itig.localhost:5173/app/staff · …/app/roles | Comptes du personnel ; Rôles et permissions (directeur) : chaque rôle se renomme, se modifie et se supprime s'il n'est donné à personne (plus de rôle « prédéfini ») ; dans un espace de démonstration (`itig`, `volcans`), une personne s'ajoute avec un numéro fictif commençant par `000` (ex. `0001234567`), jamais un vrai numéro — et l'inverse dans un espace réel ou d'essai |
| http://itig.localhost:5173/app/audit | Journal d'audit : qui a fait quoi, quand (directeur, promoteur) |
| http://itig.localhost:5173/app/dashboard | Tableau de bord : encaissé, recouvrement, alertes (directeur `0000001001`, comptable `0000001004`) ; dans une école neuve (espace réel ou d'essai créé dans la console, pas `itig` ni `volcans`), la liste « Mise en route » du directeur, en haut (aussi sur l'accueil, juste après la connexion) |
| http://itig.localhost:5173/app/students | Élèves : liste, fiche (identité, famille, finances, historique), nouvel élève, import Excel (`/app/students/import` : « Imports précédents », puis « Annuler cet import » sur un import fini), liste de classe, fiche d'inscription, situation financière, invitations au portail par classe (`/app/students/invitations` : lettres, message WhatsApp ou SMS, familles pas encore inscrites) (secrétaire `0000001006`, directeur) |
| http://itig.localhost:5173/app/cash | Caisse : ouvrir sa session, encaisser, reçu, réimprimer, demander une annulation, clôturer (caissière `0000001005`) ; marche sans réseau sur un appareil mémorisé |
| http://itig.localhost:5173/app/unpaid | Impayés : liste, export PDF et Excel, situations à imprimer (directeur, comptable) |
| http://itig.localhost:5173/app/fees | Frais : types, barèmes, tranches, taux de l'année (comptable) |
| http://itig.localhost:5173/app/fees/prior-payments | Reprise en cours d'année : importer ce que chaque élève avait payé avant Mwangaza (directeur, comptable) |
| http://itig.localhost:5173/app/cancellations · …/app/cash-closings · …/app/credits | Annulations à valider ; clôtures de caisse ; crédits d'élèves (comptable) |
| http://itig.localhost:5173/app/cash-closings/register | Registre des reçus (jour, mois ou dates ; PDF et Excel) |
| http://itig.localhost:5173/app/announcements | Annonces aux familles ou au personnel : rédiger, joindre un PDF, archiver, « lue par N familles », « Circulaire à imprimer » (directeur) |
| http://itig.localhost:5173/app/staff-news · …/app/calendar | Annonces au personnel et calendrier de l'école : lus par tous les rôles (enseignant `0000001008`) ; le directeur, la secrétaire, les directeurs des études et de discipline ajoutent des événements |
| http://itig.localhost:5173/app/summons | Convocations des parents : choisir l'élève, le jour, l'heure, le motif ; lettre PDF ; « vue par le parent » (directeur de discipline `0000001003`) |
| http://itig.localhost:5173/app/parent-requests | Demandes des parents : coordonnées envoyées depuis le portail, à appliquer ou non (secrétaire) |
| http://itig.localhost:5173/app/devices | Appareils de l'école : postes mémorisés, dernière synchro, déconnecter (directeur) |
| http://itig.localhost:5173/app/platform-news | Annonces de la plateforme pour tout le personnel de l'école ; la dernière non lue s'affiche aussi en bandeau en haut de chaque écran (« Fermer » = lue pour ce compte) ; lien en bas du menu avec le nombre de non lues |
| http://itig.localhost:5173/app/notifications | Notifications (cloche en haut de chaque écran, avec le nombre de non lues) : toucher une notification ouvre l'écran lié ; « Activer sur cet appareil », « Envoyer un essai », sortes à recevoir (directeur et comptable : « Annulation à valider », « Écart de caisse », « Caisse encore ouverte »). Les notifications sur l'écran ne marchent qu'avec l'application construite : `make build`, puis `cd frontend/apps/gestion && pnpm preview` et http://itig.localhost:4173/app/notifications |
| http://itig.localhost:5173/app/support | session support « en tant qu'école » (super-admin `0000000000`) : motif, bandeau rouge, « Quitter » |
| http://volcans.localhost:5173/app/ | Gestion de la seconde école fictive : on s'y connecte à part (session propre à chaque adresse) |
| http://itig.localhost:5173/api/school/ | quelle école répond à ce sous-domaine (après `make demo`) |
| http://itig.localhost:5173/api/platform/ | identité de la plateforme (nom, logo, couleurs, contact du support, mentions légales) : répond à toute adresse, même celle d'une école suspendue ; manifestes des applications : `/api/platform/manifest/gestion/` et `…/portail/` |
| http://localhost:5174/ | Portail parents : compte `0002000001`, mot de passe `mwangaza-demo` ; activation depuis le QR d'une lettre d'invitation (`/activate#…` : code déjà rempli) ; mes enfants, paiements et reçus (`/children/…`), annonces (`/announcements`), calendrier et convocations (`/calendar`), titulaire de la classe sur la page de l'enfant, notifications (`/notifications`, la cloche en haut : paiement reçu, annonces de l'école, échéance proche, retard de paiement, et en bas « Que recevoir sur l'écran » ; « Activer sur cet appareil » seulement dans l'application construite : `make reseau`), profil et coordonnées (`/profile`), ajouter un enfant d'une autre école (`/add-school`, code des Volcans affiché par `make demo`), installer (`/install`), guide du parent (`/guide`, aussi « Revoir le guide » du profil) ; première fois : `/activate` |
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
| http://admin.localhost:5175/ | **Console de la plateforme** (super-admin `0000000000`, mot de passe `mwangaza-demo`, puis le code de `make totp`) : tableau de bord des écoles réelles (les espaces d'essai et de démonstration n'y comptent pas ; écoles par statut, élèves, paiements et encaissé du jour par devise, écoles les plus actives, santé du serveur dont mémoire et swap, carte « Plateforme » : dernières sauvegardes, planificateur, dernière synchronisation de chaque école) ; **Identité de la plateforme** (http://admin.localhost:5175/identity : nom, logo, icône, couleurs avec aperçu, support, mentions légales ; changer le nom ne demande pas de code ; les 5 dernières modifications) ; **Écoles** (http://admin.localhost:5175/schools : un onglet par type d'espace — Réels, Essai, Démonstration —, chiffres des espaces réels, recherche, filtre par état, élèves, abonnement, dernière activité, « Ouvrir en tant qu'école » ; « Nouvelle école » http://admin.localhost:5175/schools/new avec son type d'espace (choisi une fois pour toutes) et son premier directeur — mot de passe provisoire affiché une seule fois ; type **Démonstration** : seulement un nom, un code et « Petite école » (≈ 150 élèves) ou « Grande école » (≈ 800) — l'espace se remplit seul de données fictives en moins d'une minute, puis sa fiche donne la **fiche d'accès** à remettre au visiteur (adresses, mot de passe, un numéro par rôle, parents du portail ; « Télécharger le PDF ») et « Remettre à zéro » (même adresse, mêmes numéros, nouveau mot de passe) ; au plus 5 espaces de démonstration sur la plateforme (`DJANGO_DEMO_SPACES_MAX`), un seul se crée ou se supprime à la fois ; fiche `/schools/<id>` : type d'espace, noms, adresse, abonnement, suspendre / réactiver, arrêter avec un motif / relancer, derniers changements ; pour un espace d'essai ou de démonstration seulement : « Supprimer », en retapant son code — tout est effacé pour de bon en quelques secondes, l'espace reste « Suppression en cours » puis disparaît de la liste) ; **Comptes** (http://admin.localhost:5175/accounts : chercher une personne par son nom ou son numéro dans toutes les écoles, ses écoles et rôles, ses familles du portail ; fiche : noms et téléphone, mot de passe provisoire affiché une seule fois — pas pour un parent seul, son école lui donne un nouveau code famille —, double authentification réinitialisée si le téléphone est perdu, désactiver / réactiver, derniers changements ; un compte super-admin ne se change que dans l'administration) ; **Annonces** (http://admin.localhost:5175/announcements : écrire un message à toutes les écoles ou à certaines, publié tout de suite dans la Gestion de leur personnel ; « lue par N personnes » ; archiver pour le retirer — une annonce ne se modifie pas) ; **Appareils** (http://admin.localhost:5175/devices : appareils mémorisés de toutes les écoles, recherche, en service ou déconnectés, « Déconnecter » après confirmation — noté au journal de l'école et de la plateforme) ; **Journal** (http://admin.localhost:5175/journal : ce que le support a fait dans la console, filtres par type, période et objet ; en haut, « Alertes sur cet appareil » : le bouton « Recevoir les alertes sur cet appareil » affiche sur l'écran, même console fermée, chaque connexion d'un compte super-admin, chaque code refusé et chaque session support ouverte ; onglet « Sessions support » http://admin.localhost:5175/journal/support : sessions ouvertes, fermées ou expirées, motif, nombre d'actions) ; tout autre compte y est refusé ; menu du compte : « Administration de dépannage », « Se déconnecter » |
| http://localhost:8000/ | site public de la plateforme (en anglais : http://localhost:8000/en/) : la page que Google et les assistants IA lisent ; aussi http://localhost:8000/robots.txt, /sitemap.xml et /llms.txt |
| http://localhost:8000/admin/ | administration Django, pour le dépannage (aussi à http://admin.localhost:5175/admin/, même session que la console) : super-admin `0000000000`, mot de passe `mwangaza-demo`, puis le code de `make totp` ; comptes, journal ; écoles (avec « Ouvrir en tant qu'école »), identité de la plateforme et journal de la plateforme en lecture seule (ils se modifient dans la console) |
| https://itig.localhost/app/ · https://parents.localhost/ · https://admin.localhost/ | essai de la production (`make prod-local`) : Gestion, Portail, console et administration (`/admin/`) servis par Caddy comme sur le serveur ; base vide : la Gestion affiche « Aucune école à cette adresse » tant qu'aucune école n'est créée ; santé de l'API : https://admin.localhost/api/health/ |

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
| « Image en PNG ou JPEG », « L'image dépasse 1 Mo » ou « … 2 048 pixels de côté » en envoyant un logo ou une photo | depuis S.4, une école n'envoie plus de SVG, et toute image est limitée en poids et en dimensions puis ré-encodée | exporter le logo en PNG (fond transparent gardé) ou en JPEG, 2 048 px de côté au plus ; une photo prise au téléphone est réduite toute seule par la Gestion |
| `permission denied … docker.sock` | pas encore reconnecté après `usermod` | se déconnecter / reconnecter (ou `newgrp docker` dans ce terminal) |
| `port is already allocated` (5433, 6379, 8000, 5173 ; 80 et 443 avec `make prod-local`) | un autre programme utilise le port | `ss -ltnp \| grep 6379` pour le trouver ; par ex. `sudo systemctl stop redis-server` |
| `InconsistentMigrationHistory: Migration admin.0001_initial is applied before its dependency accounts.0001_initial` (`make migrate`, `make test`, `make dev`) | base de développement créée avant la tâche 1.2 (nouveau modèle de compte) | `make reset-db` une fois |
| `make demo` ou `make test-e2e` : « Cette plateforme a un espace réel. […] refusé, rien n'a été modifié » (ou « Code pris par un espace qui n'est pas de démonstration ») | depuis la tâche 4.22, les données fictives ne s'écrivent plus sur une plateforme qui a une vraie école, ni par-dessus un espace d'essai nommé `itig` ou `volcans` | sur ta machine : `make reset-db` (efface la base de développement et la recrée) ; essai sur plusieurs appareils ou serveur : créer la démonstration dans la console, Écoles, onglet « Démonstration ». Essai dont `itig` et `volcans` datent d'avant les espaces (ils y sont « réels » : pas de bandeau, pas de « SPÉCIMEN ») : repartir d'une base neuve — `make reseau-stop`, `docker volume rm mwangaza-reseau_db-data mwangaza-reseau_media`, puis `make reseau`, `make reseau-demo`, `make reseau-superuser` (certificat et adresse gardés ; chaque appareil se reconnecte) |
| `"code": "too_many_attempts"` à la connexion | 5 essais ratés pour ce numéro en 15 minutes (ou 30 depuis ta machine) | attendre 15 minutes, ou `make demo` (débloque tout en développement) |
| `"code": "totp_required"` sur une page de l'école | session ouverte sans double authentification, alors qu'un rôle l'exige (ex. rôle donné pendant la session) | se déconnecter (`…/api/auth/logout/`) et se reconnecter |
| `"code": "invalid_code"` avec le code de `make totp` | code déjà utilisé (un code ne sert qu'une fois) | attendre le code suivant (30 secondes) et refaire `make totp` |
| `make test-e2e` ou `make guide` : `Executable doesn't exist at …/ms-playwright/…` | Chromium de Playwright pas encore téléchargé, ou Playwright mis à jour depuis (PR de Dependabot) | `cd frontend && pnpm exec playwright install chromium` ; à refaire après chaque mise à jour de Playwright |
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
| `make deploy` : `POSTGRES_APP_PASSWORD manque dans serveur.env` | `serveur.env` créé avant S.5 | `make deploy-init` (ajoute la ligne), puis `make deploy` ; mettre à jour la copie en lieu sûr |
| `make deploy` : `service "migrate" didn't complete successfully` | une migration a échoué ; l'ancienne version reste en ligne | `make deploy-logs service=migrate`, corriger, puis `make deploy` |
| `make deploy…` : `Permission denied (publickey)` | la clé SSH de Lightsail (`SSH_KEY`) n'est pas la bonne de cette machine, ou `SERVEUR` n'est pas `ubuntu@…` | vérifier `SERVEUR` dans `infra/serveur/serveur.env` ; `ssh ubuntu@<IP>` doit ouvrir une session |
| `make deploy…` : `REMOTE HOST IDENTIFICATION HAS CHANGED` | serveur recréé à la même adresse IP | `ssh-keygen -R <IP>`, puis relancer |
| Console : « Mémoire disponible » autour de 30 à 40 % alors qu'aucune école n'est ouverte | normal : c'est le poids fixe des programmes (Django 3 processus ≈ 320 Mo, Celery ≈ 256 Mo, Docker ≈ 170 Mo, PostgreSQL), le même avec 0 ou 20 écoles ; il monte pendant les heures qui suivent `make deploy`, puis se stabilise | rien à faire. À surveiller : mémoire sous 15 % (orange) ou 7 % (rouge), swap au-dessus de 50 %, ou un chiffre qui baisse **de jour en jour** → `make deploy-logs`, puis le montrer à Claude |
| `make deploy…` : SSH « Connection timed out » alors que l'instance est « Running » et les ports ouverts | machine figée (mémoire saturée pendant une construction, serveur sans swap) | console Lightsail : *Metrics* (CPU à 100 % puis plat, contrôle d'état en échec), SSH du navigateur ; s'il expire aussi : *Reboot* (pas Stop/Start) ; ensuite `make deploy-setup` (swap, SSH protégé), `make deploy-check`. Détail : skill `/deployer`, ligne « injoignable » |
| `make deploy…` : « Pas de swap sur le serveur » | serveur préparé avant le 2026-10-13 | `make deploy-setup`, puis relancer |
| `make deploy…` : délai dépassé, ou le site ne répond plus | serveur arrêté, ou ports 80 et 443 fermés (onglet « Mise en réseau » de Lightsail) | § 9 ter ; dans Claude Code : `/deployer panne` |
| une PR a une croix rouge ✘ (CI) | un contrôle échoue sur GitHub | `gh pr checks <numéro>` puis ouvrir le lien ; ou dire à Claude le numéro de la PR |

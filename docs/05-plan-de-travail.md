# Plan de travail — Mwangaza

Révisé et validé le 2026-10-13 (tâche L.0), après vérification dans le code (les constats sont marqués **Vérifié**). L'ancien plan, avec tout l'historique « ajouté le… », est archivé dans `archives/05-plan-de-travail-2026-10-13.md` : ne pas le relire à chaque tâche.

Pour lancer une tâche dans Claude Code : `/tache M.2.1` (ou « Fais la tâche M.2.1 du plan de travail. »). **Toujours prendre la première tâche non cochée de la file (§ 2)**, sauf demande contraire. État, tâche en cours et journal : `06-suivi.md` (`/etat`). Ce qui manque encore : `07-a-fournir.md`. Les références (A1, F5…) renvoient à `02-perimetre-v1.md`.

Sur GitHub : chaque version est un jalon, chaque tâche une issue « X.Y — titre » ; la PR ferme son issue (`Closes #n`). Les numéros des tâches ne changent jamais (même quand l'ordre change), pour ne pas casser les issues.

---

## 1. Légende

**Priorité**

| Code | Sens |
|---|---|
| **P0** | Bloquant : à faire avant les vraies données d'une première école |
| **P1** | Prioritaire : la prochaine chose utile pour une école qui utilise Mwangaza |
| **P2** | Utile, pas prioritaire : vient après les P1 de sa version |
| **P3** | Planifié, fait en dernier dans sa version ; une école qui le demande le fait avancer |

**Taille** (pour découper avant de coder) : **S** = une PR courte, un module serveur ; **M** = un module serveur + un ou deux écrans ; **L** = à découper en X.Y.1, X.Y.2… avant de commencer (règle : plus d'un module serveur ou plus de deux écrans → découpage).

**Qui** : 🤖 Claude Code · 👤 toi (achat, compte, clé, essai sur un vrai téléphone, décision).

`[x]` fait · `[ ]` à faire · ~~barré~~ retiré.

---

## 2. La file : l'ordre de travail

C'est la seule liste à suivre. Le détail de chaque tâche est plus bas. **Validée le 2026-10-13** par l'utilisateur (journal de `06`) : ordre, Cloudflare en proxy, lecture seule si abonnement impayé, dépendances `pip-audit`, OR-Tools et `anthropic` acceptées, IA sur `claude-opus-5-5` par défaut.

| # | Tâche | Prio | Taille | Qui |
|---|---|---|---|---|
| | **Lancement** (§ 3, § 4, § 4 bis) | | | |
| 1 | ~~**L.0**~~ ✓ Installer ce plan et remettre les documents d'aplomb | P0 | S | 🤖 |
| 2 | ~~**L.1**~~ ✓ Clés du serveur (`serveur.env`) : B2, Healthchecks, Sentry, UptimeRobot | P0 | S | 👤 |
| 3 | ~~**S.1**~~ ✓ En-têtes de sécurité et CSP des trois applications (ex-L.3) | P0 | S | 🤖 |
| 4 | ~~**S.2**~~ ✓ Dépendances et secrets surveillés (Dependabot, audit en CI, fuite de secrets) | P0 | S | 🤖 + 👤 |
| 5 | ~~**M.2.1**~~ ✓ Modules : serveur et tâches de fond | P0 | M | 🤖 |
| 6 | ~~**M.2.2**~~ ✓ Modules : écrans | P0 | S à M | 🤖 |
| 7 | ~~**L.2**~~ ✓ Restauration réelle depuis B2 | P0 | S | 🤖 + 👤 |
| 8 | ~~**S.3.1**~~ ✓ Comptes à privilèges : journal, session courte, adresses autorisées, alerte de l'école | P0 | S | 🤖 |
| 8 bis | ~~**S.3.2**~~ ✓ Comptes à privilèges : alertes sur l'écran du super-admin (push dans la console) | P0 | S à M | 🤖 |
| 9 | ~~**S.4**~~ ✓ Fichiers envoyés : logos sans SVG, images ré-encodées, limites de taille | P0 | S | 🤖 |
| 10 | ~~**M.3.1**~~ ✓ Rôles : codes de rôle remplacés par des permissions | P0 | M | 🤖 |
| 11 | ~~**M.3.2**~~ ✓ Rôles entièrement libres | P0 | M | 🤖 |
| 12 | ~~**S.5**~~ ✓ Base de données : droits minimaux, paiements non effaçables | P0 | S | 🤖 |
| 13 | ~~**L.4** Essai sur de vrais téléphones et imprimantes~~ (fait 2026-10-15) | P0 | S | 👤 |
| 14 | ~~**L.5**~~ ✓ Guide régénéré, version déclarée prête | P0 | S | 🤖 |
| 15 | **🚀 Premier espace réel** (`A-FAIRE.md`, « Le jour du lancement ») | — | — | 👤 |
| | **V1.2 — Notes, bulletins et finances de l'école** (§ 7) | | | |
| 16 | ~~**A.2**~~ ✓ Purge des opérations de synchronisation (`SyncOperation` ; `ChangeLog` gardé) | P1 | S | 🤖 |
| 17 | ~~**S.6.1**~~ ✓ Row Level Security PostgreSQL : socle et tables de finance (ex-9.15, avancée) | P1 | M | 🤖 |
| 17 bis | ~~**S.6.2**~~ ✓ Row Level Security : toutes les autres tables d'une école | P1 | M | 🤖 |
| 18 | ~~**8.1**~~ ✓ Cours, volumes horaires et charges des enseignants | P1 | M | 🤖 |
| 19 | ~~**8.2.1**~~ ✓ Saisie des notes en ligne (évaluations, notes, droits, journal) | P1 | M | 🤖 |
| 19 a | ~~**DOC.1** Signature et cachet de l'école sur tous les documents (§ 3)~~ | P0 | M | 🤖 |
| 19 b | ~~**DOC.2** Reçu sur demi ou tiers de feuille A4 (§ 3)~~ | P0 | M | 🤖 |
| 19 c | ~~**DOC.3** Registre des reçus : PDF et Excel par période et par caisse (§ 3)~~ | P0 | M | 🤖 |
| 19 bis | ~~**8.2.2**~~ ✓ Contrôle des notes (date limite, envoi, validation) ; ~~**8.2.3**~~ ✓ notes hors ligne ; **~~8.3.1~~ ✓, ~~8.3.2~~ ✓, 8.3.3 → 8.3.6, 8.5.1, 8.4, 8.8** bulletin fidèle, impression au choix, fiches de cotes, conduite, délibération, Portail | P1 | L | 🤖 |
| 20 | **FIN.1 → FIN.3** Dépenses, sorties de caisse, budget | P1 | M | 🤖 |
| | **V1.3 — Plateforme commerciale** | | | |
| 21 | **ABO.1 → ABO.3** Abonnements par module, factures, échéances | P1 | L | 🤖 |
| 22 | **WEB.1** Site de la plateforme | P1 | S | 🤖 |
| 23 | **S.7 → S.9** Protection des données, détection, revue ASVS | P1 | M | 🤖 |
| | **V1.4 — Emploi du temps et intelligence artificielle** | | | |
| 24 | **EDT.1 → EDT.4** Emploi du temps (données, éditeur, génération, publication) | P1 | L | 🤖 |
| 25 | **IA.1 → IA.5** Socle IA piloté par la console (usages, crédits), grille de cours depuis un PDF, aide à l'emploi du temps, assistant, rédaction | P1 / P2 | L | 🤖 |
| | **V1.5 — Carte et présences** (QR d'abord) | P1 / P2 | L | 🤖 |
| | **V1.6 — Bibliothèque et ateliers** (moteur commun INV) | P2 | L | 🤖 |
| | **V1.7 — Sites des écoles, personnel et paie, vie scolaire** | P2 | L | 🤖 |
| | **V2** (§ 7) | P2 / P3 | — | 🤖 |

> **Pourquoi cet ordre** : d'abord ce qui protège les vraies données (P0), puis ce qu'une école utilise chaque trimestre (notes, bulletins), puis ce qui te fait vivre (abonnements, site de la plateforme), puis l'emploi du temps, qui a besoin des cours et des charges de la 8.1, et l'IA, qui a besoin d'un socle sûr. La bibliothèque et les ateliers partagent un même moteur de prêts et de stock : ils se font ensemble.

---

## 3. Lancement : ce qui manque pour une vraie école (P0)

La V1.0 et la V1.1 sont faites (annexe). Il reste à fermer ce qui touche la sécurité des vraies données.

- [x] **L.0** Installer ce plan *(P0, S, 🤖)*
   - Remplacer `docs/05-plan-de-travail.md` par ce fichier ; l'ancien va dans `docs/archives/05-plan-de-travail-2026-10-13.md` (garder l'historique, ne plus le relire à chaque tâche).
   - Mettre à jour les fichiers listés au § 9 (domaine, état, a-fournir, CLAUDE.md, skill `/tache`).
   - Une seule PR, aucun code applicatif touché.

- [x] **L.1** Clés du serveur *(P0, S, 👤)* — `A-FAIRE.md` § 9 : créer les comptes Backblaze B2, Healthchecks, Sentry, UptimeRobot et mettre les clés dans `serveur.env`. Puis `make deploy-check` doit être vert et la première copie de nuit doit arriver dans B2. *Rien de réel ne doit entrer sur le serveur avant.*

- [x] **L.2** Restauration réelle depuis B2 *(P0, S, 🤖 + 👤)* — la 4.7.1 a essayé la restauration sur la machine, jamais depuis la copie hors serveur. **Vérifié** : les commandes existent déjà (`make deploy-backup cmd=fetch` rapatrie la copie du stockage objet, `cmd=restore` l'essaie) ; il reste à les lancer pour de vrai une fois L.1 faite. Vérifier le nombre d'écoles, d'élèves, de paiements et les fichiers (logos, photos) ; noter la durée et la procédure exacte dans `A-FAIRE.md` (« Si le serveur est perdu »). Vérifier aussi que la clé de chiffrement des sauvegardes est gardée **ailleurs que sur le serveur** (👤 : gestionnaire de mots de passe). Une sauvegarde jamais restaurée n'est pas une sauvegarde.

- ~~**L.3**~~ Compléments de sécurité : remplacée par **S.1** et **S.2** (§ 4 bis). Ce qui est déjà en place y est listé.

- [x] **L.4** Essai sur de vrais téléphones *(P0, S, 👤)* — ce que la recette 4.21 n'a pas pu faire : sur le vrai serveur, un Android et un iPhone ; installation obligatoire de la Gestion (4.24) ; caisse hors ligne (couper le réseau, encaisser, reconnecter) ; impression sur une vraie imprimante thermique 58 / 80 mm et en A4 ; Portail installé, notifications sur iPhone ; scan du QR d'un reçu imprimé. Chaque défaut trouvé devient une tâche L.4.x en tête de file.

- [x] **L.5** Clôture de la version *(P0, S, 🤖)* — après M.3 : texte du guide mis à jour (modules, rôles libres), `make guide` → `docs/guide/guide-v1.1.pdf`, « Le jour du lancement » de `A-FAIRE.md` relu avec le vrai domaine `mwangazaschool.com`.

**Documents de l'école (demande de l'utilisateur du 2026-10-15, avant L.4 : l'essai des imprimantes en dépend).** Maquettes d'abord (390 et 1440 px pour les écrans, chaque format pour les documents), une PR chacune.

- [x] **DOC.1** Signature et cachet *(P0, M, 🤖)* — l'école dépose son **cachet** et la **signature du chef d'établissement** (avec son nom et son titre) dans ses paramètres (`school.configure`) ; **chaque caissier dépose sa signature** dans « Mon compte ». Images contrôlées comme en S.4 (PNG ou JPEG, transparence du PNG gardée, fond blanc retiré si possible sans dépendance), jamais publiques : servies seulement dans les documents d'un compte connecté ou intégrées au PDF ; tout changement au journal de l'école. Partout où un document se signe : reçu (signature du caissier qui l'a donné + cachet ; thermique en noir et blanc), reçu d'annulation, fiche d'inscription, situation financière, circulaire, convocation, lettre d'invitation, bordereau de clôture ; plus tard bulletins (8.3), attestations, palmarès. Sans image déposée : la ligne de signature à la main, comme aujourd'hui. L'authenticité reste prouvée par le QR du reçu (F4), pas par l'image.
- [x] **DOC.2** Reçu en bande *(P0, M, 🤖)* — **un reçu par feuille**, jamais plusieurs sur une même page (les paiements n'arrivent pas en même temps) : sur imprimante ordinaire, feuille de la **largeur d'un A4 et de hauteur réduite**, au choix de l'école : **demi A4** (21 × 14,8 cm) ou **tiers d'A4** (21 × 9,9 cm) ; les reçus thermiques 58 / 80 mm restent ; remplace `a6`, `a5`, `small` (migration `schools.0017`) ; **réglage `copies` retiré** (un seul exemplaire). Le **registre des reçus** (ci-dessous) a été découpé en DOC.3 (décision de la tâche : un module serveur de documents en plus de la mise en page).
- [x] **DOC.3** Registre des reçus *(P0, M, 🤖, après DOC.2)* — **Registre des reçus** (PDF et Excel, `finance.view_reports`) : par période (jour, mois, dates choisies) et par caisse, une ligne par reçu (numéro, date, élève, classe, montant, devise, caissier, annulé ou non), totaux par devise et par caisse, cachet et signature du chef à la fin ; produit en tâche de fond par paquets s'il est long. Il **remplace la souche** : le reçu ne s'imprime plus qu'en un exemplaire (réglage `copies` retiré ou réduit à 1, à décider dans la tâche).

---

## 4. Modules et rôles libres (P0 : avant le premier espace réel)

Décidé le 2026-10-13 : chaque fonction est un module donné par la plateforme (socle toujours actif ; école neuve = aucun module ; écoles existantes et démonstrations = tous), puis plus aucun rôle imposé.

**Pourquoi P0** : depuis M.1, le serveur refuse (403) les droits d'un module absent, mais les écrans et les tâches de fond ne le savent pas encore : une école neuve verrait des menus qui échouent. Et changer le modèle des rôles est bien plus sûr **avant** d'avoir de vraies écoles à migrer. Enfin, chaque nouveau module (§ 6) se branchera sur ce système : il doit être fini avant.

- [x] **M.1** Modules : catalogue (`accounts/modules.py`), `School.modules`, droits d'un module absent retirés côté serveur (403, `/me`), carte « Fonctions de l'école » dans la console

- [x] **M.2.1** Modules — serveur et tâches de fond *(P0, M)*
   - Modules `portal`, `notifications`, `offline` ajoutés au catalogue.
   - **Vérifié** : le catalogue (`accounts/modules.py`) a trois modules, `students`, `finance` et `communication`, sans aucune dépendance entre eux. Une école peut donc avoir `finance` sans `students`, ce qui n'a pas de sens.
   - **Dépendances entre modules** dans le catalogue (`finance` → `students` ; relances → `notifications` ; `portal` → `students`) : activer un module active ce dont il dépend ; désactiver refuse tant qu'un module actif en dépend. Tranché une fois dans le catalogue, pas dans chaque écran.
   - Désactiver un module **ne supprime aucune donnée** : elles sont cachées et reviennent à la réactivation (à écrire dans `docs/03`).
   - Tâches de fond qui ignorent les écoles sans le module : relances, notifications à heure fixe, purge, envoi des annonces. Une requête filtrée par module, pas une boucle qui teste chaque école.
   - Portail : connexion refusée proprement (message « non proposé par l'école ») si l'école n'a pas `portal` ; un parent avec des enfants dans plusieurs écoles ne voit que celles qui l'ont.
   - Synchronisation : sans `offline`, pas d'instantané ni de file sur l'appareil ; l'instantané n'emporte que les données des modules actifs (rien d'ajouté à la première synchronisation).
   - Création d'une école (console) : modules choisis à la création.
   - Tests : une école sans chaque module → 403 côté API, tâche de fond qui la saute, isolation entre écoles.

- [x] **M.2.2** Modules — écrans *(P0, S à M)*
   - **Vérifié** : les droits d'un module absent sont déjà retirés de `/me` (`get_school_access`), et le menu de la Gestion suit les permissions depuis la 1.6. Le menu cache donc probablement déjà ces écrans (à confirmer par un test), ce qui rend la tâche plus petite que prévu.
   - Menu de la Gestion et du Portail piloté par `/me` (modules et droits), jamais par le nom du rôle.
   - Message « Aucun module activé — contactez le support » pour une école neuve sans module ; liste de mise en route (4.20.1) limitée aux modules actifs.
   - Console : cases des modules à la création, dépendances expliquées.
   - Parcours Playwright « école neuve » : créé avec un choix de modules, vérifier qu'un module absent n'apparaît nulle part.

- [x] **M.3.1** Rôles — droits déduits des permissions *(P0, M)*
   - **Vérifié, inventaire** de ce qui lit un code de rôle aujourd'hui :
     - `schools/services.py:95` : le directeur d'une école créée reçoit le rôle `head` (code).
     - `gestion/src/features/guide/guides.ts:62` : le guide de première connexion est choisi par les codes `cashier` / `accountant`.
     - `gestion/src/features/roles/RolesPage.tsx:189` : note affichée pour le rôle `parent`.
     - `gestion/src/lib/people.ts:16` : nom du rôle traduit depuis son code.
     - `audit/serializers.py:97`, `audit/views.py:144` : filtre du journal par rôle système.
     - `accounts/services.py:122, 244` et `accounts/models.py:139, 167, 180` : rôles système, contrainte sur `code`, rôle système non supprimable.
     - `accounts/demo.py:126` et `sync/demo.py:37` : données de démonstration par code.
     - Déjà correct : les notifications au personnel visent une permission (`notifications/events.py:61`), pas un rôle.
   - Remplacer chaque usage par une permission (guide choisi selon les permissions détenues, filtre du journal par rôle de l'école, rôle du directeur pris dans le modèle de départ).
   - Aucun changement visible pour les écoles existantes : tests avant / après.
   - **Fait** : premier directeur = premier rôle de départ qui a `roles.manage` ; guide et note de l'écran des rôles d'après les droits ; journal : nom du rôle de l'école donné par le serveur (`role_code` retiré de l'API) ; appareils fictifs portés par le compte fictif. **Reste pour M.3.2** (le code ne sert plus qu'à cela) : `Role.code`, `is_system` et leurs contraintes, nom traduit depuis le code (`gestion/src/lib/people.ts`), rôles système remis à zéro par `make demo` (`accounts/demo.py`).

- [x] **M.3.2** Rôles entièrement libres *(P0, M)*
   - Plus de rôle système ni de code de rôle ; un **modèle de départ** modifiable proposé à la création d'une école (les 9 rôles actuels comme suggestion).
   - Garde-fou : on ne peut pas retirer à tous les comptes la permission `roles.manage` (l'école se bloquerait).
   - Migration des écoles existantes et des démonstrations ; `make demo` avec des rôles nommés librement ; fiche d'accès des démonstrations par rôle de l'espace.
   - **Fait** : `Role.code` et « rôle système » retirés (base, API, écrans) ; un rôle = un nom obligatoire et des permissions, tous renommables et supprimables s'ils ne sont donnés à personne. Modèle de départ : les 9 rôles, dans le code (`accounts/roles.py`), copiés une fois à la création de l'école, nommés en français. Migration : chaque ancien rôle système prend le nom que l'école voyait. Garde-fou : déjà en place, vérifié par un test. **Écarté** (regard senior) : éditeur du modèle de départ dans la console et choix des rôles à la création d'une école — neuf lignes que l'école ajuste elle-même en deux minutes.

---

## 4 bis. Sécurité renforcée (bloc S)

Demande du 2026-10-13 : « la partie sécurité est à renforcer au maximum ». Point de départ **vérifié dans le code** : la base est déjà solide (isolation testée par école, permissions côté serveur, double authentification avec codes de secours, limitation des tentatives à la connexion et à l'activation du Portail, clé TOTP chiffrée avec rotation par `SECRET_KEY_FALLBACKS`, PDF qui ne chargent que des `data:` (pas de requête vers l'extérieur), SVG servis avec une CSP `sandbox`, pare-feu, SSH par clé, cookies sécurisés, HSTS côté Django). Le bloc S ferme ce qui reste, du plus urgent au plus profond.

**P0 — avant les vraies données**

- [x] **S.1** En-têtes et CSP *(P0, S)* — remplace L.3. Dans `infra/routes.caddy`, pour les fichiers des trois applications : HSTS (comme Django), `X-Frame-Options: DENY` et `frame-ancestors 'none'`, `Permissions-Policy` (caméra seulement là où le scan QR viendra), CSP stricte (`default-src 'self'`, pas de `unsafe-eval`, `connect-src 'self'`, `img-src 'self' data: blob:`), d'abord en `Content-Security-Policy-Report-Only` une semaine, puis imposée (`CSP_HEADER=Content-Security-Policy`, 👤 voir `A-FAIRE.md`). Retirer le commentaire périmé sur le certificat d'origine (`infra/docker-compose.yml`). Test : chaque réponse porte les en-têtes.
- [x] **S.2** Dépendances et secrets surveillés *(P0, S)* — **vérifié** : `03` § 8 annonce « Dependabot » mais le dépôt n'a pas de `.github/dependabot.yml`. `.github/dependabot.yml` (pip, npm, Docker, Actions ; un fichier, aucune dépendance) ; `pip-audit` et `pnpm audit --prod` dans la CI, bloquants sur les failles hautes (`pip-audit` accepté le 2026-10-13) ; 👤 activer dans GitHub « Secret scanning » et « Push protection » ; 👤 copie chiffrée de `serveur.env` hors du serveur et de la machine (gestionnaire de mots de passe), procédure de changement de chaque clé dans `A-FAIRE.md`.
- [x] **S.3.1** Comptes à privilèges — serveur *(P0, S)* — S.3 coupée en deux : la console n'a ni centre de notifications ni service worker, le push au super-admin est un chantier à part. Fait ici : journal de la plateforme pour chaque connexion d'un compte super-admin, chaque code de double authentification refusé et chaque essai depuis une adresse non autorisée ; session du super-admin fermée après 2 h sans activité ; liste d'adresses IP autorisées en réglage du serveur (`DJANGO_CONSOLE_ALLOWED_IPS`, vide = toutes). Côté école : notification « Droits sensibles » à ceux qui gèrent les rôles (auteur compris, sauf l'intéressé) quand un compte reçoit `roles.manage` ou un droit `finance.*`.
- [x] **S.3.2** Comptes à privilèges — alertes sur l'écran du super-admin *(P0, S à M)* — la console reçoit des notifications push : service worker de la console (réception et clic seulement, aucun cache), abonnement de l'appareil (bouton « Recevoir les alertes sur cet appareil », écran « Journal »), envoi à chaque entrée `access.*` du journal de la plateforme et à chaque ouverture « en tant qu'école », à tous les super-admin abonnés. Pas de centre de notifications à part : l'écran « Journal » de la console en tient lieu. Au passage : adresse d'abonnement en `https` seulement (Gestion et Portail aussi), filtres « Annonces » et « Accès du super-admin » du journal.
- [x] **S.4** Fichiers envoyés *(P0, S)* — un filtre par liste noire finit toujours par laisser passer quelque chose : le logo d'une école n'accepte plus le SVG (PNG et JPEG seulement ; les SVG déjà enregistrés restent servis en `sandbox`) ; SVG gardé pour le logo de la plateforme (super-admin). Toutes les images (logos, photo d'élève, icône) : 1 Mo et 2 048 px de côté au plus, **ré-encodées à l'envoi** (`core/images.py`, Pillow : métadonnées et position GPS retirées, orientation gardée). Pièces jointes : PDF seulement, 5 Mo, téléchargées en `attachment`. Caddy refuse tout envoi de plus de 10 Mo avant Django. Imports Excel : déjà limités (5 Mo, 5 000 lignes, lecture en flux), inchangés.
- [x] **S.5** Base de données *(P0, S)* — **vérifié** : le journal d'audit est déjà protégé par un déclencheur PostgreSQL (`UPDATE` et `DELETE` refusés même en SQL direct, `03` § 8). Reste : Django se connecte avec un compte PostgreSQL qui n'est ni superutilisateur ni propriétaire des tables (les migrations passent par un autre compte) ; même déclencheur pour les paiements et les annulations : `DELETE` refusé (et `UPDATE` des champs qui ne changent jamais, à vérifier). Seule exception : la suppression d'un espace d'essai ou de démonstration (4.16), par un chemin réservé à cette tâche. Prépare S.6. **Fait** : en production, Django et Celery se connectent avec le compte `mwangaza_app` (lignes seulement), créé et tenu à jour par `manage.py setup_app_role` ; les migrations tournent dans un conteneur `migrate` à part, seul à avoir le compte propriétaire. Déclencheurs : **vérifié, déjà en place** sur les 8 tables immuables (`UPDATE` et `DELETE` refusés depuis 3.1.1), rien à ajouter ; le compte réduit ne peut plus les désactiver, ni vider une table (`TRUNCATE`). Développement et tests gardent un seul compte.

**Décision (prise)** : remettre Cloudflare en mode proxy (nuage orange) devant le serveur ? Gain : adresse du serveur cachée, protection contre les attaques par saturation et pare-feu applicatif gratuits ; pare-feu du serveur limité aux adresses de Cloudflare. Coût : reprendre `trusted_proxies` et `CF-Connecting-IP` (déjà écrits dans `infra/Caddyfile`), et le joker `*.mwangazaschool.com` doit rester en proxy. **Décidé le 2026-10-13 : oui**, avant le premier espace réel (à faire avec S.1).

**P1 — avec les premières écoles réelles**

- [x] **S.6.1** Row Level Security PostgreSQL : socle et tables de finance *(P1, M)* — ex-9.15, avancée de la V2 : chaque table d'une école refuse, dans la base elle-même, toute ligne d'une autre école. Deuxième barrière si un jour un `filter` est oublié. S.6 coupée en deux (S.6.1, S.6.2). **Fait** : portée de la connexion posée par `use_school`, `use_schools` (Portail : écoles des familles du parent) et `use_all_schools` (console et administration du super-admin, tâches de la plateforme), sans portée aucune ligne ; règle sur les 15 tables de finance, posée après chaque `migrate` ; toute la suite de tests tourne avec un compte soumis aux règles. **Simplifié** : pas de second compte PostgreSQL pour la console et la sauvegarde (`pg_dump` passe par le propriétaire, que les règles ne visent pas ; raison : `03`, journal du 2026-10-14).
- [x] **S.6.2** Row Level Security : toutes les autres tables d'une école *(P1, M)* — `row_security.APPS` étendu à toutes les applications (élèves, familles, années et classes, rôles, notifications, synchronisation, journal d'audit) ; chemins qui lisent ces tables hors d'une école à mettre dans leur portée (envoi des notifications et leur purge, purge de la synchronisation, activation du Portail par code famille, console : comptes et journaux) ; la suite de tests sous le compte des tests les trouve. **Fait** : règle sur toute table `TenantModel` (plus de liste `APPS`) ; lectures de toute la plateforme dans `use_all_schools()` (code famille, identifiant déjà pris, famille par code au Portail, rôles d'un compte dans toutes ses écoles pour `/me` et la double authentification, planificateur, purges, envoi des notifications, import d'élèves, `make demo`) ; contrôle « rôle d'une autre école » qui ne dépend plus de leur visibilité. En test, chaque requête et chaque tâche Celery partent d'un contexte vide, comme sur le serveur.
- [ ] **S.7** Protection des données *(P1, M)* — politique de confidentialité et registre des traitements (quelles données, pourquoi, combien de temps) publiés dans le Portail et le site de la plateforme ; durées de conservation appliquées (élève parti depuis N années : données réduites au minimum légal) ; export des données d'une famille sur demande ; règles des données envoyées à l'IA (§ 6, IA.1). 👤 faire relire par un juriste au fait du droit congolais.
- [ ] **S.8** Détection *(P1, S)* — alertes au super-admin : rafale de connexions ratées, export inhabituel (beaucoup de données d'un coup), nombre d'annulations hors norme, appareil révoqué qui insiste ; carte « Sécurité » dans la santé de la plateforme (4.25). Pas de nouvel outil : Sentry et le journal suffisent.
- [ ] **S.9** Revue complète *(P1, M)* — revue des trois applications selon OWASP ASVS niveau 2 (accès, sessions, entrées, erreurs, journal), tests automatiques ajoutés pour chaque défaut trouvé ; 👤 test d'intrusion par une personne extérieure quand les revenus le permettent.

**Pour toutes les tâches** : la définition de « fini » (§ 8.2) gagne une ligne sécurité (aucune donnée d'une autre école, permission vérifiée côté serveur, entrée de l'utilisateur jamais affichée comme du HTML, envoi de fichier contrôlé, point public limité en nombre d'essais).

---

## 5. Améliorations des modules existants

Trouvées à la relecture. Chacune est marquée « à vérifier » quand elle repose sur une supposition sur le code : la vérifier d'abord, la retirer si elle est déjà faite.

| # | Amélioration | Prio | Taille | Quand |
|---|---|---|---|---|
| ~~A.1~~ | ~~Mémoire du serveur~~ : **vérifié, déjà fait** après la panne du 2026-10-13 (swap de 2 Go, limites de mémoire par conteneur dans `docker-compose.production.yml`, construction en série). Rien à ajouter. | — | — | — |
| **A.2** | **Tables qui grossissent sans fin.** **Vérifié** : les notifications sont purgées à 90 jours et les sessions chaque nuit, mais `ChangeLog` et `SyncOperation` n'ont **aucune purge**. **Fait (2026-10-14)** : chaque nuit, les `SyncOperation` appliquées de plus de 90 jours sont effacées (une ligne par opération envoyée, avec son contenu) ; les refusées restent (vérification d'un reçu). `ChangeLog` n'est pas purgé : une ligne par inscription, pas par paiement, il grossit comme `Enrollment`. Le journal d'audit est gardé. | P1 | S | après le lancement, avant la fin du premier trimestre réel |
| **A.3** | **Dépendances serveur et front à jour** : une passe par version (Django 5.2 LTS, paquets du front), sans en ajouter. | P2 | S | fin de chaque version |
| **A.4** | **Export des données d'une école** (aujourd'hui « à la main par le support » ; **vérifié** : aucune commande `make` ne le fait) : une commande `make export-ecole CODE=…` (Excel + fichiers), pas d'écran. Utile le jour où une école part ou demande ses données. | P2 | S | quand une école le demande, au plus tard V2 |
| **A.5** | **Sélection de plusieurs élèves pour une impression** (2.4) | P3 | S | V1.5, avec la planche de cartes (6.1 : même sélection) |

---

## 6. Nouveaux modules (demandés le 2026-10-13)

Chaque nouveau module suit la même règle, pour aller vite sans rien faire à moitié :

1. Entrée dans le catalogue des modules (M.2), avec ses dépendances et ses permissions ; vendable seul (ABO).
2. Modèles en `TenantModel`, logique dans `services.py`, permissions vérifiées côté serveur, audit si argent, notes, paie ou rôles ; tout montant passe par les règles de l'argent (`/argent`).
3. Menu piloté par `/me` ; textes fr / en ; données de démonstration dans `core.demo.fill`.
4. Si hors ligne : opérations idempotentes (UUID v7) dans la file existante.
5. Section ajoutée au guide de la version.

### 6.1 Finances de l'école (FIN) — P1, V1.2

Ce qui manque aujourd'hui : l'argent qui **sort**. La caisse ne connaît que les entrées.

- [ ] **FIN.1** Dépenses (ex-7.1) *(M)* : catégories réglées par l'école, bénéficiaire, devise, justificatif (photo ou PDF), validation au-delà d'un seuil (permission `finance.approve_expense`), annulation comme un paiement (jamais effacée) ; audit.
- [ ] **FIN.2** Sorties de caisse *(M)* : une dépense payée en espèces sort d'une session de caisse, en ligne et hors ligne ; le bordereau et les écarts de la clôture (3.8.2, M16) en tiennent compte ; bon de sortie imprimé.
- [ ] **FIN.3** Budget et rapports *(M)* : budget prévu par catégorie et par année, réalisé contre prévu, entrées / sorties par mois et par devise, trésorerie (caisse, banque, Mobile Money comme « comptes » de l'école), export Excel. La comptabilité SYSCOHADA complète reste en V2 (9.7) ; la paie (7.3) alimentera les dépenses.

### 6.2 Abonnements par module (ABO) — P1, V1.3

L'argent de la plateforme. M.1 et M.2 donnent déjà les modules ; il manque le contrat et la facture. Remplace la 9.2.

- [ ] **ABO.1** Offres et contrats *(M)* : prix par module, par élève inscrit et par période (trimestre ou année scolaire), devise ; offres groupées (ex. « Essentiel » = élèves + frais + caisse) ; contrat d'une école = modules + prix + période + essai ; les modules actifs suivent le contrat ; **allocation IA** de l'offre : usages IA compris et crédits par mois (§ 6.5), une recharge de crédits = une ligne de facture (ABO.2). Console seulement.
- [ ] **ABO.2** Factures et paiements de l'école à la plateforme *(M)* : facture PDF numérotée, immuable (annulation = avoir), paiement enregistré par le super-admin (espèces, banque, Mobile Money à la main ; en ligne avec 9.3) ; l'école voit ses factures dans ses paramètres ; audit de la plateforme.
- [ ] **ABO.3** Échéances *(S)* : rappels avant échéance (planificateur existant) ; après le délai de grâce, **lecture seule** plutôt que coupure (l'école garde ses reçus et ses données, la caisse se ferme) — **décidé le 2026-10-13** ; chiffre d'affaires dans le tableau de bord de la console.

### 6.3 Sites web (WEB) — P1 pour la plateforme, P2 pour les écoles

- [ ] **WEB.1** Site de la plateforme *(S, V1.3)* : `mwangazaschool.com` (depuis le 2026-10-14 : page de présentation fr/en, données structurées, `robots.txt`, `sitemap.xml`, `llms.txt` — `apps/core/site.py` ; reste ci-dessous) : présentation, modules et prix (lus dans le catalogue et les offres, rien en dur), demande de démonstration (formulaire → console, limité contre le spam sans dépendance), mentions légales et confidentialité (S.7), français et anglais. Pages rendues par Django, mises en cache, sans JavaScript obligatoire. **Design (demande du 2026-10-14)** : la page actuelle n'est qu'un socle technique pour Google et les IA ; la tâche commence par regarder les sites des grands logiciels (SaaS, logiciels scolaires), puis une **maquette** de chaque page (390, 820, 1440 px) avant tout code ; **constaté le 2026-10-15** : sur `mwangazaschool.com`, beaucoup d'éléments débordent au téléphone — la nouvelle version est vérifiée avec `make apercu` aux trois largeurs : vrai design marketing aux normes actuelles — photos (écoles, salles, ateliers ; libres de droits ou fournies), animations sobres (désactivées par `prefers-reduced-motion`), sections claires, **pied de page complet** (liens, contact, langues, mentions, « © DTMS. Tous droits réservés. » ; l'auteur seulement en `<meta name="author">`), identité de la refonte (bleu Kivu, nuit, lumière, lignes de relief).
- [ ] **WEB.2** Site de chaque école *(L, V1.7)* : à la racine de `{code}.mwangazaschool.com/` (la Gestion reste à `/app/`). L'école remplit elle-même son contenu depuis la Gestion : présentation, options et sections, admissions, actualités (annonces marquées « publiques »), galerie, contact, frais affichés seulement si elle le choisit ; publié ou non. **Sécurité** : modèles de pages fixes, texte en Markdown limité et nettoyé, aucun HTML ni script fourni par l'école, images ré-encodées (S.4), formulaire de contact limité. Domaine propre à une école : P3 (certificats à la demande, risque d'abus). Design : comme WEB.1 (références, maquette aux trois tailles, photos de l'école, pied de page complet), les couleurs et le logo de chaque école.

### 6.4 Emploi du temps (EDT) — P1, V1.4

Faisable, et utile à toutes les écoles. **Avis de développeur senior** : un emploi du temps sans conflit est un problème de contraintes ; une IA seule ne garantit pas zéro conflit (elle peut placer un enseignant dans deux classes à la même heure sans le voir). Donc : un **solveur** calcule, et l'**IA aide** autour (IA.2). Solveur proposé : OR-Tools CP-SAT (Google, licence Apache 2.0, utilisé partout pour ce problème) — **dépendance acceptée le 2026-10-13**.

- [ ] **EDT.1** Données *(M)* — après la 8.1 : grille horaire de l'école (jours, heures, récréations, demi-journées), salles et ateliers (type, capacité), volume horaire hebdomadaire de chaque cours par classe, enseignants (charge maximale, jours et heures où ils sont disponibles, cours qu'ils peuvent donner, enseignant partagé avec une autre école), contraintes (au plus N heures du même cours par jour, heures doubles pour les travaux pratiques d'atelier, cours à ne pas mettre en dernière heure…).
- [ ] **EDT.2** Éditeur et contrôle des conflits *(M)* : grille par classe, par enseignant et par salle ; déplacer une heure à la main ; chaque conflit montré tout de suite (enseignant, salle, classe, charge dépassée) ; versions (brouillon, publiée), l'ancienne gardée.
- [ ] **EDT.3** Génération automatique *(L)* : le solveur place tout en respectant les contraintes obligatoires et au mieux les souhaits ; en tâche de fond, une à la fois, temps limité (le serveur est partagé) ; s'il n'y a pas de solution, il dit **quelle contrainte bloque** ; on peut verrouiller des heures avant de relancer.
- [ ] **EDT.4** Publication *(S)* : PDF par classe, par enseignant, par salle ; emploi du temps dans le Portail (parents) et pour chaque enseignant ; changement après publication notifié (5.6). Plus tard : heures prestées pour la paie (7.3), appel en classe (V1.5).

### 6.5 Intelligence artificielle dans l'application (IA) — P1 / P2, V1.4

Intégration de **Claude** (API d'Anthropic) côté serveur. « Comme Claude Code » : l'IA lit, explique, prépare ; **la personne valide**. Elle n'écrit jamais seule dans l'argent, les notes ou les rôles.

**Révisé le 2026-10-13 (demande de l'utilisateur) : l'IA se vend avec l'abonnement et se pilote depuis la console.** La plateforme paie l'API : sans compteur, une seule école peut manger la marge. Le mécanisme tient en quatre règles.

1. **Des usages déclarés, pas une IA « libre ».** Catalogue `ai/uses.py`, sur le modèle de celui des modules : chaque usage (`course_grid_from_pdf`, `timetable_constraints`, `assistant`, `drafting`…) déclare son module hôte, la permission exigée dans l'école, son modèle, la taille maximale de l'entrée et de la réponse. Un usage ne marche que si l'école a aussi le module hôte.
2. **La console décide, l'école utilise.** Seul le super-admin (double authentification, journal de la plateforme) règle : les usages affectés à une école d'après son contrat (ABO.1), ses crédits du mois, une recharge, la pause d'une école, le modèle et les limites d'un usage, les prix par modèle, le plafond mensuel de la plateforme, l'interrupteur général. L'école ne règle rien : elle donne la permission `ai.use` à ses rôles (`roles.manage`, déjà au journal) et voit ses crédits restants en lecture seule.
3. **Cinq verrous avant chaque appel**, dans un seul service (`ai.services.authorize`), et un seul fichier qui parle à l'API (`ai/client.py`) : interrupteur et plafond de la plateforme → module `ai` et usage affecté à l'école → `ai.use` **et** permission de l'écran hôte → crédits restants ≥ coût maximal de l'appel → limite par personne (appels par heure). Un refus ne coûte rien et dit pourquoi.
4. **Compté en crédits, pas en jetons bruts.** Un jeton n'a pas le même prix selon le modèle ni le sens (entrée, sortie, cache). Chaque réponse de l'API donne ses jetons ; le serveur les note et calcule le coût en **entiers** (micro-dollars : un appel coûte moins d'un centime) avec la table des prix de la console. 1 crédit = un millième de dollar de coût d'API ; le prix de vente du crédit, donc la marge, se règle dans l'offre (ABO.1). L'école voit ses crédits restants ; la console voit jetons, coût et marge.

**Rien dépensé pour rien** : jamais d'appel automatique ni planifié (toujours le clic d'une personne) ; le travail exact reste au code (le solveur calcule l'emploi du temps, WeasyPrint dessine le bulletin : zéro jeton par bulletin) ; un résultat gardé devient une donnée normale, jamais régénérée à l'affichage ; une même demande envoyée deux fois = un seul appel (identifiant de demande, UUID v7) ; consignes fixes mises en cache ; chaque appel finit « gardé » ou « abandonné » selon ce que la personne en fait : la console montre, par usage, les crédits dépensés et la part des résultats gardés (un usage qui coûte sans servir se voit et se coupe).

**Coût pour le serveur** (§ 8.5) : un appel dure de quelques secondes à une minute, donc jamais dans une requête web : tâche Celery dans une file `ai` limitée à 2 appels à la fois, l'écran attend le résultat. Une ligne par appel (`AiCall`, purgée à 90 jours) et un cumul par école, mois et usage (`AiUsageMonth`, gardé pour la facturation) : le contrôle des crédits lit une ligne, pas une somme.

- [ ] **IA.1.1** Socle serveur *(M, P1)* — tout le reste en dépend :
   - module `ai` du catalogue ; catalogue des usages ; `authorize` (les cinq verrous) ; `client.py` ; `AiCall` [T] immuable (qui, usage, modèle, jetons d'entrée, de sortie et de cache, coût, état : fait, refusé, erreur, gardé, abandonné ; **jamais le texte** de la demande ni de la réponse) ; `AiUsageMonth` [T] ; réglages de la plateforme ; alerte au super-admin à 80 % et 100 % du plafond, à l'école à 80 % de ses crédits (notifications existantes) ; purge dans le planificateur ;
   - session support « en tant qu'école » : l'appel est compté sur le compte de la plateforme, pas sur les crédits de l'école (mise en route faite par le support) ;
   - clé de l'API seulement sur le serveur (`serveur.env`), jamais dans une application ;
   - l'IA ne reçoit que ce que la personne a le droit de voir : ses « outils » appellent les services existants **avec les permissions de la personne**, jamais une requête directe à la base ; aucune donnée d'une autre école ;
   - **minimisation** : pas de téléphones, pas de photos, pas d'adresses ; élèves désignés par un identifiant interne quand le nom n'est pas utile ;
   - **injection de consignes** : un texte écrit par un parent, une annonce ou un PDF peut contenir « ignore tes règles… » ; donc outils en lecture seule, et toute action proposée passe par l'écran normal, avec confirmation et audit ;
   - modèle par défaut : `claude-opus-5-5`, réglable par usage dans la console ; un modèle moins cher (`claude-sonnet-5-5`, `claude-haiku-5-5`) pour certaines tâches seulement si le coût mesuré l'exige (**décidé le 2026-10-13**) ; prix, limites et champs de l'API à relire au début de la tâche (skill `claude-api`) ;
   - 👤 conditions de conservation des données chez Anthropic à vérifier (rétention, zéro rétention sur demande) et à écrire dans la politique de confidentialité (S.7) ;
   - nouvelle dépendance `anthropic` (SDK officiel) : **acceptée le 2026-10-13** ;
   - tests : crédits et appels d'une autre école jamais lus ni débités ; 403 sans `ai.use` ou sans la permission hôte ; crédits épuisés ou plafond atteint → refus **sans appel à l'API** ; cumul exact en entiers ; même demande deux fois = un appel ; usage refusé sans son module hôte.
- [ ] **IA.1.2** Console et crédits *(M, P1)* : page « IA » de la console (interrupteur, plafond et dépense du mois, par école et par usage, part des résultats gardés, alertes) ; carte « IA » de la fiche d'une école (usages affectés, rangés par module ; crédits du mois, consommés, restants ; derniers appels ; pause ; recharge) ; réglages (modèle, limites, prix) ; chaque changement au journal de la plateforme. Gestion : carte « Crédits IA » en lecture seule dans les paramètres ; bouton IA caché sans droit, grisé avec la raison sans crédit.
- [ ] **IA.5** Grille de cours d'une section à partir d'un bulletin en PDF *(M, P1)* — exemple donné le 2026-10-13 : l'école envoie le PDF ou la photo d'un bulletin (fichier contrôlé comme en S.4, 3 pages au plus) → l'IA propose les cours, domaines et maxima de la section (données de 8.1) et les options du bulletin (8.3) → la personne corrige dans l'écran normal et enregistre. **L'IA produit des données vérifiées par un schéma, jamais du HTML ni un modèle exécuté** : le bulletin reste dessiné par notre code (document officiel, mise en page EPST, aucune injection possible). Un appel par section, puis plus aucun jeton. Dépend de 8.1 et 8.3.
- [ ] **IA.2** Aide à l'emploi du temps *(M, P1)* : la direction décrit ses contraintes en phrases (« M. Kambale ne vient pas le vendredi, la 4e mécanique a l'atelier le mardi matin ») → l'IA les traduit en contraintes que la personne relit et valide → le solveur (EDT.3) calcule → l'IA explique les conflits et propose des assouplissements.
- [ ] **IA.3** Assistant de questions *(M, P2)* : « combien d'élèves de 5e A sont en retard de paiement ? », « quelles classes ont le plus d'absents ce mois ? » ; réponses tirées des données, avec le lien vers l'écran d'où elles viennent ; lecture seule. Usage le plus cher (conversation ouverte) : longueur d'une conversation et questions par jour limitées, réglées dans la console.
- [ ] **IA.4** Aide à la rédaction *(S, P2)* : brouillons d'annonces, de convocations, de lettres de relance, d'appréciations de bulletin ; toujours un brouillon que la personne modifie et publie elle-même.

**Pas maintenant** : un assistant général dans la console pour l'équipe de la plateforme — aucun besoin précis, donc aucun retour mesurable ; il se déclarera comme un usage de plus le jour où ce besoin existe.

**À décider par toi (👤) avec ABO.1** : usages et crédits compris dans chaque offre ; prix d'une recharge ; crédits non utilisés perdus en fin de mois (recommandé : oui, plus simple à expliquer et à facturer).

### 6.6 Bibliothèque et ateliers (INV, BIB, ATL) — P2, V1.6

Les deux reposent sur la même mécanique : des **objets** (livres, outils, matières), des **exemplaires** étiquetés, des **mouvements** (prêt, retour, entrée, sortie, perte) et des **personnes** (élève ou personnel). On la construit une fois.

- [ ] **INV.1** Moteur commun *(M)* : articles, exemplaires avec étiquette QR (lue par la caméra comme la carte, V1.5), stock par lieu (bibliothèque, chaque atelier), mouvements immuables (une erreur se corrige par un mouvement inverse), inventaire annuel avec écarts ; audit.
- [ ] **BIB.1** Catalogue *(S)* : titre, auteur, ISBN, catégorie, niveau ; exemplaires et état ; import Excel ; étiquettes imprimables.
- [ ] **BIB.2** Prêts et retours *(M)* : prêt à un élève ou un membre du personnel avec date de retour prévue ; **bon de prêt** PDF signé ; **parent prévenu** dans le Portail et par notification (5.6), avec la date de retour ; retour avec l'état du livre ; prolongation ; nombre maximal de livres par élève.
- [ ] **BIB.3** Retards et pertes *(M)* : rappels automatiques (planificateur existant) à l'élève, au parent et au bibliothécaire ; pénalité de retard facultative ; **livre perdu ou abîmé** : constat, puis frais de remplacement **ajoutés à ce que doit l'élève** (un `StudentCharge`, payé à la caisse avec un reçu normal, règles de l'argent) ; le livre est retiré du catalogue ; rapports (livres les plus lus, retards).
- [ ] **ATL.1** Stock des ateliers *(M)* : matières d'œuvre et outillage par atelier, seuil d'alerte de stock bas.
- [ ] **ATL.2** Commandes de matériel *(M)* : le chef d'atelier ou l'enseignant **demande** → la direction **valide** → l'achat devient une dépense (FIN.1) → la **réception** fait l'entrée en stock → l'enseignant **retire** le matériel à l'atelier (bon de sortie signé, lié à la classe et au travail pratique).
- [ ] **ATL.3** Outils prêtés aux élèves *(S)* : même prêt que la bibliothèque ; casse ou perte → frais à l'élève comme BIB.3.

Les évaluations d'atelier (9.9) restent en V2.

---

## 7. Versions (validées le 2026-10-13)

Les numéros des tâches existantes restent les mêmes. Chaque tâche **L** est redécoupée au moment de la commencer.

**Décidé le 2026-10-13** : les tâches P3 seront développées (elles sont dans la V1.5, la V1.7 et la V2) ; P3 fixe l'ordre, pas l'abandon. Chacune est un module que l'école active ou non, donc sans poids pour celles qui ne s'en servent pas. Seule réserve : 9.11 (supérieur LMD) demande les règles d'un vrai institut avant d'être découpée.

### V1.2 — Notes, bulletins et finances de l'école

- [x] **A.2** Purge des opérations de synchronisation : `SyncOperation` appliquées de plus de 90 jours, chaque nuit ; `ChangeLog` gardé (une ligne par inscription) *(P1, S)*
- [x] **S.6.1** Row Level Security : socle et tables de finance *(P1, M)*
- [x] **S.6.2** Row Level Security : toutes les autres tables d'une école *(P1, M)*
- [x] **8.1** Cours, maxima, domaines, attribution des enseignants **avec leur charge horaire** (servira à l'emploi du temps) ; la grille de cours d'une section s'enregistre d'un seul bloc par un service (IA.5 la proposera depuis un PDF) *(P1, M)*
- **8.2** Saisie des notes (y compris hors ligne), verrouillage, validation, historique *(P1, L)* — découpée le 2026-10-15 :
  - [x] **8.2.1** Saisie en ligne : évaluations libres (nom, maximum), notes à une décimale, note de la période ramenée au maximum (règle de trois), droits `grades.enter` (ses cours, sa classe de titulaire) et `grades.enter_any`, journal par enregistrement, écran (tableau, carte par élève au téléphone), démo *(M)*
  - [x] **8.2.2** Contrôle : date limite de saisie par période, envoi pour validation, validation par le directeur des études (`grades.validate`, double authentification), modification après envoi avec motif et historique, maximum d'un cours noté changé seulement avec validation, écran de validation *(M)*
  - [x] **8.2.3** Hors ligne : feuilles gardées sur l'appareil (Dexie), file d'envoi, opération de synchronisation idempotente, test Playwright réseau coupé *(M)*
- **8.3** Bulletin EPST PDF avec QR d'authenticité, totaux, places, mentions ; bulletin complet ou notes seules sur le formulaire pré-imprimé (Q11) ; régime et code EPST de l'école (M5) *(P1, L)* — vrais bulletins 3e et 4e HT reçus le 2026-10-15 (`docs/ecole-pilote/prive/builtin/`, hors Git) : ils servent de modèle (8.3.3). Découpée le 2026-10-15 :
  - [x] **8.3.1** Calcul : totaux par période et par domaine, pourcentage, places, mentions ; paramètres EPST de l'école (code, régime, M5) ; service testé *(M)*
  - [x] **8.3.2** Bulletin PDF (humanités techniques et 7e–8e), QR d'authenticité, signature et cachet (DOC.1), aperçu à l'écran *(M)*
  - [ ] **8.3.3** Bulletin **fidèle au formulaire officiel**, d'après deux vrais bulletins reçus le 2026-10-15 (3e HT, IGE/P.S/137 ; 4e HT, IGE/P.S/096 ; scans dans `docs/ecole-pilote/prive/builtin/`, hors Git) : le 3e HT sert de **modèle par défaut à toute classe et option** ; la dernière année (`Level.has_state_exam`) remplace « Examen de repêchage » par le bloc « Examen d'État » (points obtenus et maximum, %, code du centre, résultat final, témoignage). Mesures (largeurs de colonnes, hauteurs de lignes, cadres) relevées sur les scans, mises à l'échelle de la zone imprimable ; police serif de type Times (Liberation Serif embarquée, comme Atkinson) ; cases noires (examen des cours sans examen, Application et Conduite hors périodes), lignes MAXIMA par groupe, MAXIMA GÉNÉRAUX, place et effectif, Application et Conduite par période, N° ID, province, ville, commune, N° permanent (champs de l'école et de l'élève, saisis par l'école, repris à l'import). Contrôle : superposition du PDF sur le scan à 150 ppp, écart de 1 mm au plus *(M)*
  - [ ] **8.3.4** **Options d'impression au choix de la personne qui imprime** (IMP.1) : sur tout document imprimable (liste de classe, impayés, fiches de cotes, bulletins, reçus) un panneau « Imprimer » où elle choisit les colonnes à garder (moins de papier), le nombre d'exemplaires par feuille (1, 2, 3), le papier (A4, A5) et le sens, mémorisés par personne et par document ; le serveur applique ces choix (`columns`, `per_sheet`, `paper`, `orientation`), sans réglage de l'école sauf les valeurs de départ *(M)*
  - [ ] **8.3.5** Notes seules sur le formulaire pré-imprimé (Q11 : texte placé au millimètre sur les cases du formulaire de l'école), impression de toute la classe en lot, démo *(M)*
  - [ ] **8.3.6** **Fiches de cotes** : fiche d'un cours (élèves × périodes et examens, total du semestre, moyenne, plus haute et plus basse note, nombre sous la moitié, signature de l'enseignant), fiche vierge à remplir à la main, tableau de toute la classe (cours × élèves, servira à la délibération 8.4) ; droits `grades.enter` (ses cours) ou `grades.enter_any` ; options d'impression de 8.3.4 *(M)*
- [ ] **8.5.1** **Conduite et discipline** *(P1, L, à découper : barème et incidents, puis parents et bulletin)* — le directeur de discipline (DD, droit `discipline.configure`) tient la **liste des infractions avec leurs points** (modèle de départ proposé, modifiable) et le barème qui en tire la cote de conduite d'une période (TB, B, AB, ME, MA ; seuils à régler par l'école) ; tout enseignant (`discipline.record`) attribue une infraction à un élève (date, motif, note) ; le **parent est prévenu** (notification et Portail) ; la cote de conduite de chaque période se calcule d'après les points et alimente la ligne Conduite du bulletin ; le DD ou la délibération (8.4) peut la corriger avec un motif (journal) ; Application : proposée d'après le pourcentage de la période, corrigée par le titulaire *(avant 8.4)*
- [ ] **8.4** Délibération (revoit la conduite), décisions, palmarès, passage de classe *(P1, M)*
- [ ] **8.8** Portail parents : notes, bulletins PDF ; tableau de bord : résultats *(P1, M)*
- [ ] **FIN.1 → FIN.3** Dépenses, sorties de caisse, budget (§ 6.1) *(P1)*

### V1.3 — Plateforme commerciale

- [ ] **ABO.1 → ABO.3** Abonnements par module (§ 6.2) *(P1)*
- [ ] **WEB.1** Site de la plateforme (§ 6.3) *(P1)*
- [ ] **S.7 → S.9** Protection des données, détection, revue ASVS (§ 4 bis) *(P1)*

### V1.4 — Emploi du temps et IA

- [ ] **EDT.1 → EDT.4** (§ 6.4) *(P1)*
- [ ] **IA.1.1, IA.1.2, IA.5, IA.2** (§ 6.5) *(P1)* ; **IA.3, IA.4** *(P2)*

### V1.5 — Carte et présences (QR d'abord, NFC en option)

- [ ] **6.1** Carte de l'élève et du personnel : modèle réglé par l'école, PDF carte et planche A4, jeton secret dans le QR, révocable, carte perdue remplacée *(P1, M)*
- [ ] **6.3** Pointage par téléphone ou tablette enregistrés, caméra QR, mode borne, hors ligne *(P1, M)*
- [ ] **6.5** Suivi des présences, corrections au journal, rapports, taux au tableau de bord *(P1, M)*
- [ ] **6.6** Présences et parents : notifications, justification dans le Portail, alerte après X absences *(P1, M)*
- [ ] **6.2** Liaison des cartes NFC (NTAG215 / 216) *(P2, M)* — 👤 commander quelques cartes d'essai
- [ ] **6.4** Lecteurs ESP32 (`firmware/`) *(P2, L)* — 👤 matériel
- [ ] **A.5** Sélection de plusieurs élèves pour une impression (§ 5) *(P3, S)* — avec 6.1

### V1.6 — Bibliothèque et ateliers

- [ ] **INV.1**, **BIB.1 → BIB.3**, **ATL.1 → ATL.3** (§ 6.6) *(P2)*

### V1.7 — Sites des écoles, personnel, paie, vie scolaire

- [ ] **WEB.2** Site de chaque école (§ 6.3) *(P2, L)*
- [ ] **7.2** RH : dossier employé, contrats, qualifications, statut SECOPE *(P2, M)*
- [ ] **7.3** Paie : périodes, primes, motivation liée aux frais, avances, retenues, fiche de paie PDF ; la paie devient une dépense (FIN.1) *(P2, L)*
- [ ] **7.4** Espace enseignant : fiche de paie, emploi du temps (EDT.4), congés *(P2, M)*
- [ ] **7.5** Pénalités de retard des frais, inscription validée par le paiement, documents téléversés *(P2, M)*
- [ ] **8.5.2** Messagerie parent ↔ titulaire / administration ; rendez-vous ; mérites et récompenses ; renvoi temporaire et exclusion *(P2, L)* — la conduite est faite en 8.5.1 (P1)
- [ ] **8.6** Portail élèves ; espace titulaire *(P2, L)*
- [ ] **8.7** Transfert d'élève entre écoles de la plateforme ; attestations *(P2, M)*
- [ ] **8.9** Sondages ; blocage des bulletins en cas de dette (désactivé par défaut) *(P2, S)*
- [ ] **7.6** Connexion Google, champs complémentaires de la fiche élève *(P3, S)*

### V2 — après la V1.7 (ordre à valider avant de commencer)

**À préparer par toi dès maintenant (👤)** : 9.3 et 9.4 dépendent de contrats longs à obtenir (agrégateur Mobile Money : M-Pesa, Airtel Money, Orange Money ; fournisseur SMS / WhatsApp).

| # | Tâche | Prio |
|---|---|---|
| 9.3 | Paiement Mobile Money via agrégateur (frais des parents vers l'école ; abonnements des écoles vers la plateforme) | P1 de la V2 |
| 9.4 | SMS et WhatsApp avec crédits achetés par l'école ; relances par SMS | P1 de la V2 |
| 9.10 | Rapports officiels EPST : statistiques, listes ENAFEP / Exetat, palmarès officiel | P1 de la V2 |
| 9.1 | Réseau : tableau consolidé promoteur / coordination, comparaison entre années | P2 |
| 9.6 | Pré-inscription en ligne (depuis le site de l'école, WEB.2), test d'admission, liste d'attente | P2 |
| 9.5 | Applications Android et iPhone (Capacitor) ; puce de la carte sur iPhone | P2 |
| 9.7 | Comptabilité SYSCOHADA complète (sur FIN) | P2 |
| 9.8 | Devoirs et cours publiés (l'emploi du temps est passé en V1.4) | P2 |
| 9.9 | Évaluations d'atelier ; évaluation des enseignants | P2 |
| 9.11 | Enseignement supérieur LMD | P3 |
| 9.12 | Cantine, transport, internat (la bibliothèque est passée en V1.6) | P3 |
| 9.13 | Boutique (uniformes, fournitures) (inventaire et ateliers passés en V1.6) | P3 |
| 9.14 | Orientation, anciens élèves (le site des écoles est passé en V1.7) | P3 |
| ~~9.2~~ | ~~Abonnements~~ → ABO (V1.3) | — |
| ~~9.15~~ | ~~Row Level Security~~ → S.6 (V1.2) | — |

### Plus tard (non planifié)

Migration depuis d'autres logiciels ; rapports transmis aux sous-divisions EPST ; maternelle ; domaine propre à une école.

---

## 8. Méthode de travail (pour aller vite sans rien bâcler)

### 8.1 Une tâche, du début à la fin

1. **Lire l'état** : `docs/06-suivi.md`, puis **seulement** la section de ce plan et les passages utiles de `01` à `04`. Ne pas relire l'archive du plan.
2. **Regard de développeur senior** : utile ? faisable ? coût pour le serveur (écritures par requête, tâches de fond, taille des tables) ? Retirer ou simplifier ce qui ne sert pas, et le dire. Taille L → proposer le découpage avant de coder.
3. **Fiche de la tâche** dans `docs/claude/plans/tache-X.Y.md`, 20 lignes au plus, toujours avec ces rubriques :
   - **But** (une phrase, pour l'école) · **Hors périmètre** · **Critères d'acceptation** (vérifiables) · **Tests obligatoires** · **Documents à mettre à jour** · **Risques / à vérifier dans le code**.
4. **Démarrer** : issue « X.Y — titre », branche `tache/X.Y-mot-clé` depuis `main` à jour.
5. **Construire** : tests utiles d'abord (isolation entre écoles, permissions, argent, audit, vraies règles métier), puis le code (logique dans `services.py`, pas de N+1, listes paginées, textes i18n, rien en dur). Lancer seulement les tests du module touché ; la suite complète tourne dans la CI.
6. **Vérifier** : `make lint` + la **définition de « fini »** (§ 8.2).
7. **Clôturer** : cocher la tâche ici, mettre à jour `06-suivi.md` et tous les `.md` que le changement rend faux. Un seul push, une seule PR (base `main`), jamais fusionnée par Claude.
8. **PR** en français simple : ce qui change, tests, « À valider », « À tester toi-même », « Après la fusion », `Closes #n`. Surveiller la CI et corriger dans la même PR. Finir par : « Fusionne la PR, puis /clear et /tache <suivante de la file> ».

### 8.2 Définition de « fini » (rien de superficiel)

Une tâche n'est cochée que si **tout** est vrai :

- [ ] Les critères d'acceptation de la fiche sont tous vérifiés.
- [ ] Les 9 règles non négociables (§ 8.4) sont respectées ; un test d'isolation entre écoles existe pour chaque nouveau modèle.
- [ ] Les permissions sont vérifiées côté serveur et le module est déclaré dans le catalogue (depuis M.2).
- [ ] Les écrans ont un état vide qui dit quoi faire, un état d'erreur, et marchent à 390 px en français et en anglais.
- [ ] Les données de démonstration couvrent la nouveauté (`core.demo.fill`).
- [ ] Aucune écriture en base ajoutée à chaque requête ; tout ce qui est lourd en tâche de fond, par paquets.
- [ ] Les documents rendus faux sont corrigés dans la même PR.
- [ ] Sécurité : aucune donnée d'une autre école, permission vérifiée côté serveur, entrée de l'utilisateur jamais affichée comme du HTML, envoi de fichier contrôlé (S.4), point public limité en nombre d'essais.
- [ ] La CI est verte.

### 8.3 Pour aller plus vite

- **Ce plan reste court** : une tâche faite devient une ligne dans l'annexe ; le détail et l'historique vont dans `06-suivi.md` (journal) et dans l'archive. Plus de mentions « ajouté le… » dans le texte des tâches à faire : Claude Code relit moins et se trompe moins.
- **Découper tôt, pas tard** : une PR = une chose qu'on peut tester seule.
- **Regrouper les petites corrections** (moins d'une heure chacune, même module) dans une seule tâche « X.Y — corrections », au lieu d'une PR chacune.
- **Une seule source par décision** : les décisions vont dans `docs/03` § décisions, le plan y renvoie.
- **Mesurer avant d'optimiser** (comme la 4.23) : pas d'optimisation sans chiffre.

### 8.4 Règles non négociables

Isolation des écoles (TenantModel + test) · argent en entiers + devise + taux · paiements immuables (annulation = nouvel enregistrement ; seule exception : suppression d'un espace d'essai ou de démonstration) · UUID v7 client + écritures idempotentes · audit des finances / notes / paie / rôles · permissions vérifiées côté serveur · i18n fr / en · pas de dépendance sans accord · rien en dur pour une école ni pour la plateforme.

### 8.5 Garde-fous de performance (serveur de 2 cœurs, 2 Go, partagé)

Aucune écriture en base ajoutée à chaque requête · tout ce qui est lourd en tâche de fond, par paquets, une à la fois · rien d'ajouté à la première synchronisation des appareils · pas de nouveau processus sans raison mesurée · temps de réponse mesurés sur le vrai serveur pour tout écran qui parcourt tous les élèves (seuil : 2 s pour 1 200 élèves).

---

## 9. Installation de ce plan (L.0, faite)

L.0 a mis à jour, dans la même PR : `06-suivi.md`, `07-a-fournir.md`, `01`, `02`, `03` (journal des décisions et sécurité), `04`, `A-FAIRE.md`, `CLAUDE.md`, `README.md`, `maquettes/README.md`, `firmware/README.md` et les skills `tache`, `etat`, `ecran`, `design` et `document-ecole` (numéros de version). Domaine dans le code : en production il vient de `MWANGAZA_DOMAIN` ; seuls des défauts de `backend/config/settings/base.py` et des commentaires gardent `mwangaza.school` (décidé le 2026-10-13, sans effet).

**Incohérences de l'ancien plan corrigées ici** : la 4.7 restait non cochée alors que 4.7.1 et 4.7.2 sont faites (le reste est une action de ta part : L.1) ; la 4.6.3 décrivait encore `mwangaza.school`, le certificat d'origine et le pare-feu Cloudflare, abandonnés ; la 4.21 et la 4.22 citaient `make reseau` / DuckDNS, retirés avec la 4.11 (**vérifié** : ces cibles n'existent plus dans le `Makefile`) ; la 9.14 citait l'ancien domaine ; « Créer les comptes » restait ouvert alors que seul le stockage objet manquait (désormais L.1).

---

## Annexe — Fait (une ligne par tâche ; détail dans l'archive et `06-suivi.md`)

**Socle** : 0.1 monorepo et Docker · 0.2 qualité et CI · 1.1 `core` (TenantModel, UUID v7, Money) · 1.2 comptes, rôles, permissions · 1.3 connexion, TOTP, Mon compte · 1.4 audit · 1.5 super-admin et paramètres de l'école · 1.6 front Gestion · 1.7 organisation scolaire et écrans d'administration.

**Élèves et frais** : 2.1 élèves, familles, inscriptions, matricule · 2.2 écrans élèves · 2.3 import Excel · 2.4 impressions · 2.5 frais, barèmes, réductions · 2.6 frais dus, échéancier particulier · 2.7 solde et retards.

**Caisse et hors ligne** : 3.1 caisses et paiements · 3.2 reçus et vérification `/v/` · 3.3 appareils et synchronisation serveur · 3.4 base locale et file · 3.5 caisse hors ligne · 3.6 crédit élève · 3.7 PIN et appareils · 3.8 annulation et clôtures.

**Rapports, portail, production** : 4.1 impayés et situation financière · 4.2 tableau de bord directeur · 4.3 annonces · 4.4 Portail parents · 4.5 guides et traductions · 4.6 production (4.6.1, 4.6.3 : `mwangazaschool.com`, Lightsail Paris) · 4.7 sauvegardes (4.7.1, 4.7.2 : B2, Healthchecks, Sentry ; clés : L.1) · 4.9 invitations des familles · 4.10 guide PDF · 4.12 connexion fiable du Portail · 4.13 matricule facultatif · 4.14 annuler un import · 4.15–4.18 espaces réel / essai / démonstration · 4.19 reprise en cours d'année · 4.20 mise en route d'une école neuve · 4.21 recette · 4.22 `make demo` sans danger · 4.23 mesure sur le vrai serveur (0,6–0,75 s) · 4.24 installation obligatoire de la Gestion · 4.25 santé de la plateforme.

**V1.1** : 5.1 identité de la plateforme · 5.2 console · 5.3 console écoles · 5.4 comptes, appareils, journal, annonces de la plateforme · 5.5 notifications (Gestion, Portail) · 5.6 événements immédiats et à heure fixe · 5.7 communication (annonces au personnel, calendrier, convocations, circulaires).

**Modules** : M.1 catalogue et droits côté serveur.

**Retirées** : ~~4.6.2~~ serveur gratuit Oracle / DuckDNS · ~~4.8~~ mise en place à l'ITIG · ~~4.11~~ essai sur le même réseau · récupération des documents de l'ITIG et modèle d'imprimante (plus des préalables).

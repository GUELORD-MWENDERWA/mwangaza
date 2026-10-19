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
| 12 bis | ~~**PERF.1 → PERF.4**~~ ✓ Impression en tâche de fond, PDF gardés, bulletin plus léger, mesure et surveillance (§ 4 ter) | P0 | M à L | 🤖 |
| 12 ter | ~~**PERF.5a → PERF.5c**~~ ✓ Stabilité du serveur de 2 Go : réglages mémoire et tâches de fond, tableau de santé compréhensible, images construites hors du serveur et passage du dépôt en privé (§ 4 ter ; demandé le 2026-10-16, nommé PERF.5 car PERF.2 existe) | P0 | M + M + M | 🤖 |
| 13 | ~~**L.4** Essai sur de vrais téléphones et imprimantes~~ (fait 2026-10-15) | P0 | S | 👤 |
| 14 | ~~**L.5**~~ ✓ Guide régénéré, version déclarée prête | P0 | S | 🤖 |
| 14 bis | **OPS.1** Compte AWS sans piège : budget et alertes, double authentification, adresse, crédits suivis (§ 4 quater) | P0 | S | 👤 |
| 14 ter | ~~**OPS.2**~~ ✓ Instantanés automatiques et alarmes Lightsail, retour d'un serveur entier essayé une fois | P0 | S | 🤖 + 👤 |
| 14 quater | ~~**OPS.3**~~ ✓ Domaine et comptes de la plateforme protégés (LWS, Cloudflare, AWS, B2, GitHub) ; ta part : `A-FAIRE.md` 5 ter | P0 | S | 👤 + 🤖 |
| 14 quinquies | ~~**OPS.4**~~ ✓ E-mail professionnel `@mwangazaschool.com` et domaine protégé contre l'usurpation (SPF, DKIM, DMARC) ; ta part : `A-FAIRE.md` § 9 nonies 3 c, 4 b-c | P0 | S | 👤 + 🤖 |
| 14 sexies | ~~**L.6**~~ ✓ Travailler sans internet : code PIN proposé après la connexion (constaté le 2026-10-17) | P0 | S | 🤖 |
| 14 septies | ~~**WEB.1a**~~ ✓ Site public : étude des grands sites, puis maquettes de chaque page (§ 6.3) — *avancé le 2026-10-17 à ta demande* | P0 | M | 🤖 |
| 14 octies | ~~**WEB.1b**~~ ✓ Site public : pages pour les écoles et les parents, captures du produit, animations, « Trouver mon école » (§ 6.3) | P0 | M | 🤖 |
| 14 nonies | ~~**WEB.1c**~~ ✓ Visibilité : images de partage, données structurées (DTMS, auteur), recherches courtes, Search Console (§ 6.3) | P0 | S | 🤖 + 👤 |
| 14 decies | ~~**WEB.1d**~~ ✓ Site public : demande de démonstration rangée dans la console, alerte au super-admin, adresse et réseaux sociaux de la plateforme dans son identité (§ 6.3) — *découpée de WEB.1b le 2026-10-18* | P0 | M | 🤖 |
| 15 | **🚀 Premier espace réel** (`A-FAIRE.md`, « Le jour du lancement ») | — | — | 👤 |
| 15 a | ~~**NB.1 → NB.6**~~ ✓ (bloc fini le 2026-10-19) Notes et bulletins comme à l'école : carnet de l'enseignant privé, fiche de cotes envoyée au directeur des études et au titulaire, tableau du DE, espace du titulaire, règles de délibération du règlement de l'école, conseil par période et PV, seconde session (§ 5 ter) — *demandé le 2026-10-18, avant 8.4.6* | P1 | L | 🤖 |
| 15 bis | ~~**EQ.1 → EQ.2**~~ ✓ (bloc fini le 2026-10-19) Équipe de la plateforme : membres, rôles fixes (propriétaire, technique, support, commercial, communication, finance), droits vérifiés par le serveur sur chaque point de la console (§ 6.3 bis) — *demandée le 2026-10-18* | P1 | M | 🤖 |
| 15 ter | **SITE.1 → SITE.3** Site public géré depuis la console par la communication : questions, témoignages avec accord écrit, écoles de référence, bandeau, actualités, photos (§ 6.3 ter) ; SITE.4 (offres) avec ABO — *demandée le 2026-10-18* ; SITE.1a faite le 2026-10-19 | P1 | L | 🤖 |
| 15 quater | **HL.1 → HL.3** Hors ligne là où le réseau manque : inscriptions de la rentrée, conduite, dernières données du Portail ; règle « hors ligne décidé dans chaque plan » (§ 5 bis) — *demandée le 2026-10-18* | P1 | M | 🤖 |
| | **V1.2 — Notes, bulletins et finances de l'école** (§ 7) | | | |
| 16 | ~~**A.2**~~ ✓ Purge des opérations de synchronisation (`SyncOperation` ; `ChangeLog` gardé) | P1 | S | 🤖 |
| 17 | ~~**S.6.1**~~ ✓ Row Level Security PostgreSQL : socle et tables de finance (ex-9.15, avancée) | P1 | M | 🤖 |
| 17 bis | ~~**S.6.2**~~ ✓ Row Level Security : toutes les autres tables d'une école | P1 | M | 🤖 |
| 18 | ~~**8.1**~~ ✓ Cours, volumes horaires et charges des enseignants | P1 | M | 🤖 |
| 19 | ~~**8.2.1**~~ ✓ Saisie des notes en ligne (évaluations, notes, droits, journal) | P1 | M | 🤖 |
| 19 a | ~~**DOC.1** Signature et cachet de l'école sur tous les documents (§ 3)~~ | P0 | M | 🤖 |
| 19 b | ~~**DOC.2** Reçu sur demi ou tiers de feuille A4 (§ 3)~~ | P0 | M | 🤖 |
| 19 c | ~~**DOC.3** Registre des reçus : PDF et Excel par période et par caisse (§ 3)~~ | P0 | M | 🤖 |
| 19 bis | ~~**8.2.2**~~ ✓ Contrôle des notes (date limite, envoi, validation) ; ~~**8.2.3**~~ ✓ notes hors ligne ; **~~8.3.1~~ ✓, ~~8.3.2~~ ✓, ~~8.3.3~~ ✓, ~~8.3.4~~ ✓, ~~8.3.5~~ ✓, ~~8.3.6~~ ✓, ~~8.5.1a~~ ✓, ~~8.5.1b~~ ✓, ~~8.5.1c~~ ✓, ~~8.4.0~~ ✓, ~~8.4.1~~ ✓, ~~8.4.2~~ ✓, ~~8.4.3~~ ✓, ~~8.4.4~~ ✓, ~~8.4.7~~ ✓, ~~8.4.5~~ ✓, 8.4.6, 8.8, PERF.6, S.10** bulletin fidèle, impression au choix, fiches de cotes, conduite, délibération, Portail | P1 | L | 🤖 |
| 20 | **FIN.1 → FIN.3** Dépenses, sorties de caisse, budget | P1 | M | 🤖 |
| 20 bis | **PERF.7** Écrans « Impayés » et tableau de bord plus légers ; **OPS.5** passage à 4 Go préparé (§ 4 quater) | P1 | S à M | 🤖 + 👤 |
| | **V1.3 — Plateforme commerciale** | | | |
| 21 | **ABO.1 → ABO.3** Abonnements par module, factures, échéances | P1 | L | 🤖 |
| 22 | ~~**WEB.1**~~ avancée en WEB.1a → WEB.1c (lignes 14 septies à 14 nonies) ; ici : page des **prix** quand ABO et le tarif (T6) existent | P1 | S | 🤖 |
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
- [x] **L.6** Travailler sans internet *(P0, S, 🤖 ; fait le 2026-10-17, constaté par l'utilisateur : la Gestion installée affichait « Pas de connexion au serveur » sans réseau)* — le démarrage sans réseau (B5, 3.7.1) exige un appareil mémorisé **et** un code PIN, que rien ne proposait (carte cachée dans « Mon compte »). Bandeau « Travailler sans internet sur cet appareil » sur un appareil mémorisé sans PIN (ni en session support, ni sur « Mon compte » ; « Plus tard » jusqu'à la prochaine ouverture), qui ouvre la carte PIN prête à la saisie ; la page hors ligne dit comment préparer l'appareil quand aucun compte n'a de PIN. Maquette `gestion/hors-ligne-preparer`.

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

## 4 ter. Performance et capacité (bloc PERF) — P0 avant la première école réelle

Mesures du 2026-10-16 : `docs/claude/recherches/perf-impression-capacite-2026-10-16.md` (un bulletin ≈ 1,9 s et 13 Mo ; 35 bulletins ≈ 1 à 3 min et 700 Mo, dans une requête web ; conteneur Django à 98 % de sa mémoire ; une classe de 45 dépasse le délai de 120 s). Estimation : le serveur actuel (2 Go) tient ≈ 10 à 15 écoles en usage courant mais **2 écoles qui impriment ensemble le saturent**. Rien à acheter tant qu'aucune école réelle : d'abord le logiciel.

- [x] **PERF.1** Impression en tâche de fond *(P0, M ; faite le 2026-10-16)* — tout document lourd (bulletins d'une classe, fiches de cotes, registre des reçus) devient une tâche Celery à part (file `print`, un seul travail à la fois sur le serveur, par paquets de 10 pages réunies sans nouvelle dépendance par `Document.copy`) : l'écran affiche l'avancement puis le lien du PDF ; plus de PDF de classe dans une requête web. Gunicorn : `--max-requests 300 --max-requests-jitter 60` (le travailleur qui garde 593 Mo est recyclé). Test : classe de 45 sans 502, mémoire du conteneur sous 70 %. **Fait** : `PrintJob` + `apps/core/printing.py` (au-delà de 3 pages ou 600 Ko de HTML : un travail, une page d'attente qui se recharge seule puis le PDF à la même adresse, aucun changement d'écran) ; travailleur `celery-print` (file `print`, un travail à la fois, 450 Mo max, renouvelé tous les 5 travaux, délai 7 min) ; paquets de 8 pages réunis par **pypdf** (35 bulletins : 351 Mo au lieu de 700, 68 s hors du site) ; au plus 3 travaux en attente par école et 20 en tout ; gunicorn recyclé tous les ~400 requêtes, délai 60 s ; base : requête coupée à 25 s, transaction oisive à 30 s ; mémoire des conteneurs revue ; fichiers effacés au bout d'un jour
- [x] **PERF.2** PDF gardés *(P0, M ; faite le 2026-10-16)* — un bulletin se produit une fois, est gardé dans le stockage de fichiers (clé = empreinte des notes, de l'élève et du gabarit), servi comme un simple fichier : réimpression et **Portail des parents** sans calcul ; effacé ou refait quand une note ou le gabarit change ; nettoyage des anciens. Isolation entre écoles prouvée par test **Fait** : `KeptDocument` + `apps/core/kept.py` ; clé = empreinte du HTML du bulletin (école comprise) sans QR ni date ; réimpression = fichiers lus (aucune mise en page), classe partielle = seules les pages manquantes refaites (dans la requête si ≤ 3, sinon par la tâche de fond), ancien fichier de la même inscription et du même mode effacé, purge à 60 jours sans lecture ; l'audit reste écrit à chaque impression. **Écran du Portail pour les parents : pas dans cette tâche** (aucun écran de bulletin au Portail aujourd'hui ; le service `kept` est prêt pour 8.5.1b)
- [x] **PERF.3** Bulletin plus léger *(P1, S à M ; faite le 2026-10-16)* — profiler la mise en page (le tableau compte pour ≈ 80 %), essayer `table-layout: fixed` et un CSS plus simple ; cible ≤ 1 s par page et ≤ 5 Mo par page ; même contrôle pour les autres documents **Fait** : 2,1 s → 0,8 s par page (PDF 92 à 115 Ko) ; feuille en bloc au lieu d'une colonne flex et polices lues une fois par processus ; mémoire ≈ 10 Mo par page, bornée par les paquets de 10 (cible de 5 Mo non atteinte, sans effet : pas de cumul).
- [x] **PERF.4** Mesure et surveillance *(P0, S à M ; faite le 2026-10-16)* — `make perf` : temps de l'impression et des écrans lourds sur `make prod-local`, plusieurs utilisateurs à la fois (résultats dans `docs/claude/recherches/`) ; carte « Santé » de la console : mémoire par conteneur, longueur de la file d'impression, plus longue attente, nombre d'écoles et d'élèves ; alerte au-dessus de 85 % de mémoire ou 60 % de swap ; tableau de capacité à jour dans `03` § 9 à chaque version. Règle : toute fonction lourde annonce son coût (secondes de processeur, Mo) dans son plan **Fait** : `scripts/perf.py` (`make perf`, `n=` utilisateurs ; connexion du promoteur de la démo, requêtes en parallèle + impression de la plus grande classe) ; carte « Plateforme » de la console : mémoire de chaque conteneur (`conteneurs.sh`, cron 5 min posé par `make deploy`), file et attente d'impression ; seuil de swap passé de 50 à 60 % ; tableau de capacité dans `03` § 9. La mesure chiffrée attend le vrai serveur (`make perf` n'a pas été lancé sur la machine de 8 Go, déjà chargée)

**Chantier PERF.5 — Stabilité du serveur de 2 Go, tableau de bord compréhensible, coût zéro** (constat du 2026-10-16 sur le vrai serveur : AWS Lightsail, 2 Go de RAM, 2 vCPU, 60 Go de SSD, 2 Go de swap, une école de test ; `mwangaza-celery-1` grossit tout seul, 256 Mo à 13 h 54 puis 263 Mo à 14 h 15 sur 320 Mo, sans activité ; django 317/640, celery-print 128/512, caddy 26/192, db 40/512, redis 4/96 ; hôte 30 % libre, swap 9 % ; la section « Dernière synchronisation » s'affiche vide sans explication). **Contraintes** : aucun coût supplémentaire (ni service payant, ni abonnement, ni plus gros serveur) ; le dépôt GitHub est **public** pendant le développement (Actions gratuit et illimité) puis repassera en **privé** (plan gratuit : 2 000 minutes d'Actions par mois, 500 Mo de Packages, beaucoup moins d'activité : quelques corrections et déploiements par mois) : tout doit marcher dans les deux cas sans rien payer ; connexion lente et parfois coupée (RDC) : pas de gros fichiers envoyés à chaque déploiement ; toutes les règles de `CLAUDE.md` (pas de dépendance nouvelle sans demander). Trois tâches, dans cet ordre :

- [x] **PERF.5a** Réglages mémoire et tâches de fond *(P0, M ; faite le 2026-10-16 ; mesures : `docs/claude/recherches/perf-5a-memoire-2026-10-16.md`)* — infra + réglages Celery, Gunicorn, Redis, PostgreSQL. Avant de coder, lire `06`, `03` § 9 et Journal, `infra/docker-compose*.yml`, `Dockerfile`, `infra/serveur/`, `infra/backup/`, `config/settings/`, toutes les tâches Celery, le code de la carte « Santé » de la console ; ne changer que ce qui manque ou est faux, dire dans la PR ce qui existait déjà. **Constats** : (1) `celery` : `--max-memory-per-child=300000` (≈ 300 Mo par travailleur, 2 travailleurs + processus principal + planificateur `-B`) pour `mem_limit` 320m : Docker tue le conteneur avant que Celery recycle, la tâche en cours est perdue et le planificateur avec ; même erreur sur `celery-print` (450000 pour 512m). Règle : seuil par travailleur < (limite du conteneur − processus principal) / concurrence, avec de la marge. (2) Pas de `memswap_limit` : un conteneur qui déborde prend du swap au lieu de s'arrêter, tout le serveur ralentit → `memswap_limit` = `mem_limit` partout. (3) Somme des limites ≈ 2,3 Go (+ `migrate` 512m pendant un déploiement) pour 2 Go : viser ≈ 1,7 Go, ≈ 300 Mo pour le système ; départ à valider avec `make perf` : django 448m, celery 320m, celery-print 384m, planificateur 96m, db 320m, redis 64m, caddy 64m, migrate 384m. (4) Redis sans `maxmemory` : ≈ 48mb, `maxmemory-policy noeviction` (c'est la file des tâches, jamais d'éviction) ; vérifier la persistance (une sauvegarde RDB copie le processus : prévoir la marge ou la désactiver si Redis ne sert que de file et de cache) ; `result_expires` si des résultats sont stockés. (5) Gunicorn : 3 workers sync sans `--preload` → `--preload` + workers `gthread` (ex. 2 × 4 threads, réglables par variables d'environnement), en gardant timeout, max-requests et jitter ; vérifier que rien n'ouvre de connexion (base, Redis, sockets) à l'import, sinon `--preload` pose problème. (6) PostgreSQL par défaut → réglé pour 320 Mo (`shared_buffers` ≈ 96MB, `work_mem` ≈ 4MB, `maintenance_work_mem` ≈ 32MB, `effective_cache_size` ≈ 512MB, `max_connections` ≈ 40) ; activer `pg_stat_statements` (extension PostgreSQL, pas une dépendance Python). **Changements** : A. **Deux files Celery** séparées : file rapide (notifications, synchronisation, tout ce qui est court ; 2 travailleurs légers) et file lourde (l'actuelle « print » : PDF, import Excel, exports, création d'espaces de démonstration, tout ce qui est long ou gourmand ; 1 seul travailleur, un travail à la fois, `acks_late`, prefetch 1) ; chaque tâche routée explicitement (`task_routes`) ; aucune tâche lourde ne peut retarder une synchronisation de caisse. B. Tous les travailleurs : `worker_prefetch_multiplier=1` ; `soft_time_limit` et `time_limit` sur chaque tâche (valeurs réalistes, documentées) ; `task_reject_on_worker_lost` seulement pour les tâches idempotentes (règle 4). C. **Planificateur (`-B`) sorti** dans un petit service à part : il ne meurt plus avec un travailleur. D. **Découper les tâches lourdes** quand c'est possible (impression classe par classe plutôt que toute l'école d'un coup) sans changer le résultat pour l'utilisateur ; dépendance nouvelle : expliquer et demander. E. **Throttling DRF** sur connexion, recherche, exports et impression s'il n'existe pas déjà ; taille maximale des requêtes dans Caddy cohérente avec imports et pièces jointes. F. Hôte (`preparer.sh`) : `vm.swappiness=10` ; swap de 2 Go présent et qui survit au redémarrage. G. **Noms des services** : évaluer un renommage parlant (`celery-print` → `worker-heavy`, `celery` → `worker`, nouveau `scheduler`), seulement si TOUS les usages sont mis à jour dans la même PR (Makefile, `deployer.sh`, sauvegardes, carte « Santé », docs, skills) ; sinon garder les noms et laisser PERF.5b afficher des noms clairs ; dire le choix et la raison dans « À valider ». Mesurer avant/après avec `make perf` sur `make prod-local`, chiffres dans `docs/claude/recherches/`. Tests utiles seulement : chaque tâche va dans la bonne file, chaque tâche a ses limites de temps, le throttling est actif.
- [x] **PERF.5b** Tableau de bord de santé compréhensible et guide d'exploitation *(P0, M, après PERF.5a ; faite le 2026-10-16)* — un administrateur qui n'est pas développeur, nommé plus tard, comprend l'écran et sait quoi faire. **Maquette d'abord** (`CLAUDE.md`), vérifiée à 390 et 1440 px. 1. Chaque conteneur affiché avec un **nom clair en français** (i18n, jamais en dur), **une phrase sur son rôle** et le nom technique en petit (pour les commandes) ; exemples à adapter : `django` → « Application web (ce que voient les écoles et les parents) » ; `celery` → « Tâches de fond rapides (notifications, synchronisation) » ; `celery-print` → « Tâches lourdes (impressions PDF, imports, exports) » ; planificateur → « Planificateur (relances et tâches à heure fixe) » ; `db` → « Base de données (toutes les informations des écoles) » ; `redis` → « File d'attente des tâches » ; `caddy` → « Porte d'entrée sécurisée (HTTPS) » (noms techniques selon le choix de PERF.5a). 2. **Couleurs simples** : normal < 70 %, attention 70–85 %, alerte > 85 % ; afficher aussi « arrêté pour manque de mémoire » (OOMKilled ou redémarrage récent, avec l'heure), sans requête lourde à chaque affichage. 3. Pour chaque indicateur (mémoire de l'hôte, swap, disque, base, file des tâches, sauvegardes, planificateur, impression) : info-bulle ou ligne « Ce que ça veut dire / Que faire si c'est orange ou rouge ». 4. Section « Dernière synchronisation » : message clair quand elle est vide (« Aucune école n'a encore synchronisé ») et explication de « les plus silencieuses d'abord ». 5. **Guide d'exploitation** `docs/exploitation.md`, en français simple, pour un futur administrateur : ce que fait chaque partie du serveur, valeurs normales, que faire en cas d'alerte (commandes `make` exactes : `deploy-logs`, `deploy-check`, `deploy-backup`…), comment redémarrer un service, qui prévenir ; lien depuis le tableau de bord ; `A-FAIRE.md` à jour.
- [x] **PERF.5c** Images construites hors du serveur et passage du dépôt en privé *(P0, M, après PERF.5a ; faite le 2026-10-16 ; chiffres : `docs/claude/recherches/perf-5c-images-et-minutes-2026-10-16.md`)* — 1. **Construction des images** : aujourd'hui sur le serveur (Node 1 Go + Go 700 Mo), elle a déjà figé la machine le 2026-10-13 ; la faire dans **GitHub Actions** et publier sur **GitHub Container Registry** (gratuit tant que le dépôt est public) ; le serveur ne fait plus que `docker compose pull` + `up`, et ne télécharge que les couches modifiées. 2. **Préparer dès maintenant le passage en privé** : images du registre privées, lecture par le serveur avec un **jeton à droits minimaux** (documenté) ; **nettoyage automatique** du registre (garder les 3 dernières images) pour rester sous 500 Mo, taille réelle des images mesurée et notée ; image backend réduite si possible (couches, fichiers inutiles) ; **économiser les minutes** : `concurrency` avec `cancel-in-progress`, caches (uv, pnpm, navigateurs Playwright), `timeout-minutes` sur chaque job, images construites seulement au déploiement et seulement si le code concerné a changé ; consommation mensuelle en privé estimée (quelques déploiements et corrections par mois) et notée ; **solution de secours** documentée (construire sur le serveur, priorité basse) si le quota est un jour épuisé. 3. `A-FAIRE.md` : section **« Le jour où le dépôt repasse en privé »** : étapes exactes (visibilité du dépôt, des images, jeton du serveur, vérification avec `make deploy-check`), et où voir la consommation de minutes et de stockage dans GitHub.
- **Fin de chaque tâche PERF.5** : cocher ici, journal dans `06`, décisions dans le Journal de `03`, `infra/README.md`, `A-FAIRE.md` (ce que l'utilisateur fait sur le serveur après la fusion, commandes exactes) et tout `.md` devenu faux.

## 4 quater. Exploitation : AWS, domaine et e-mail (bloc OPS)

Constat du 2026-10-17 dans la console AWS (détail et sources : `docs/claude/recherches/serveur-et-credits-aws-2026-10-17.md`) : compte ouvert le 12/10/2026, **plan payant** (aucune page « Mettre à niveau »), **100 $ de crédits** « AWS Free Tier » valables jusqu'au **12/10/2027**, 0,11 $ consommés en 5 jours (l'instance semble en essai gratuit Lightsail : sa date de fin se lit dans *Factures*). Les crédits paient les factures AWS (pas le domaine, ni Cloudflare, ni B2) jusqu'à leur fin ; ensuite ≈ 12 à 13 $ / mois sur la carte. 4 activités sûres (Budgets, Bedrock, Lambda, EC2 résiliée tout de suite ; **pas** RDS / Aurora) en ajoutent 80 $ : la première année est alors couverte. Règle : **pas de nouveau service AWS** (RDS, S3, SES, CloudFront…) sans le dire dans le plan de la tâche avec son coût après les crédits.

- [ ] **OPS.1** Compte AWS sans piège *(P0, S, 👤 ; Claude a écrit la marche à suivre : `A-FAIRE.md` § 9 octies)* — budget mensuel de 15 $ (alertes : prévision à 100 %, réel à 80 %, e-mail) ; double authentification (MFA) du compte racine ; adresse du compte corrigée (pays RDC, pas « TZ ») ; activités sûres pour les crédits ; le service **Secrets Manager** vu sur la facture (Mwangaza ne l'utilise pas) regardé avant toute suppression ; date de fin de l'essai Lightsail et solde des crédits notés dans `A-FAIRE.md`.
- [x] **OPS.2** Instantanés et alarmes Lightsail *(P0, S, 🤖 + 👤 ; fait le 2026-10-17 : instantanés à 2:00 et alarmes actifs, `make deploy-check ip=`, essai réel vert, copie supprimée)* — toi : instantanés automatiques (un par jour, 7 gardés, ≈ 0,5 à 1 $ / mois) et alarmes « contrôle d'état en échec » et « processeur > 90 % pendant 15 min » vers ton e-mail. Claude : procédure « serveur perdu ou cassé » en deux chemins dans `A-FAIRE.md` § 9 ter et la skill `/deployer` : (a) depuis un instantané (nouvelle instance, IP statique déplacée, `make deploy-check`) ; (b) depuis B2 (déjà écrit). Essai réel une fois : instance créée depuis l'instantané de la nuit, santé vérifiée sur son IP provisoire, **supprimée le jour même** (quelques centimes) ; ligne dans `infra/README.md`.
- [x] **OPS.3** Domaine et comptes protégés *(P0, S, 👤 + 🤖 ; part de Claude faite le 2026-10-17 : tableau « Comptes de la plateforme », ligne « domaine » de `make deploy-check` ; constat : expire le 12/10/2027, verrou de transfert absent ; ta part reste dans `A-FAIRE.md` « Maintenant » 5 ter et § 9 octies, lignes 8 et 9)* — `mwangazaschool.com` acheté chez **LWS**, DNS chez Cloudflare : un domaine expiré ou volé coupe toutes les écoles. Toi : chez LWS, renouvellement automatique avec une carte valide, date d'expiration notée, verrou de transfert actif, protection des données du titulaire, double authentification ; double authentification aussi sur Cloudflare, Backblaze, GitHub, Sentry, Healthchecks, UptimeRobot ; e-mail de secours de chaque compte = l'adresse pro d'OPS.4 ou ta boîte personnelle, jamais une boîte que personne ne lit. Claude : tableau « Comptes de la plateforme » dans `A-FAIRE.md` (service, à quoi il sert, qui y accède, renouvellement ; **aucun mot de passe**).
- [x] **OPS.4** E-mail professionnel *(P0, S, 👤 + 🤖 ; part de Claude faite le 2026-10-17 : MX, SPF strict, DKIM et DMARC `quarantine` déjà copiés de LWS dans Cloudflare, relevés dans `infra/README.md` « E-mail du domaine », ligne « e-mail » de `make deploy-check` ; 2 boîtes comprises chez LWS, pas d'offre à comparer ; rapports DMARC par la gestion gratuite de Cloudflare, pas dans `contact@` ; ta part : créer les boîtes, essai d'envoi, rapports, puis `p=reject` vers le 2026-10-31, `A-FAIRE.md` § 9 nonies 3 c, 4 b-c)* — adresses `contact@` et `support@mwangazaschool.com` (celle du support est affichée par la console › Identité et la page publique). Choix, dans l'ordre : (1) boîte e-mail comprise dans l'offre LWS du domaine, si elle existe ; (2) sinon une offre gratuite ou peu chère (à comparer le jour de la tâche, prix vérifiés) ; (3) à défaut, *Email Routing* de Cloudflare (gratuit, réception seulement, renvoi vers ta boîte). Enregistrements MX, SPF, DKIM et DMARC posés **dans Cloudflare** (c'est lui qui tient le DNS, pas LWS) ; Claude les vérifie (`dig`) et les note dans `infra/README.md`. Les comptes de la plateforme et leurs alertes **gardent ta boîte personnelle** (décidé le 2026-10-17, OPS.3) : `contact@` dépend du domaine et se tait s'il tombe ; elle s'ajoute en seconde adresse, jamais sur LWS ni Cloudflare. L'application n'envoie pas d'e-mail aujourd'hui (notifications dans l'app et push) : pas d'Amazon SES tant qu'aucune tâche n'en a besoin.
- [ ] **OPS.5** Passage à 4 Go préparé *(P1, S, 🤖 + 👤, avec PERF.6)* — `docs/03` tableau « Capacité » aux prix du jour (2 Go = 12 $, 4 Go = 24 $) ; procédure pas à pas dans `/deployer` et `A-FAIRE.md` (instantané manuel, nouvelle instance plus grande, IP statique déplacée, `make deploy-setup`, `make deploy-check`, ancienne supprimée après 48 h) ; seuils de la carte Santé reliés à ce tableau. Toi : répétition sur une copie supprimée dans l'heure. **On reste sur 2 Go** (décidé le 2026-10-17 : il suffit aujourd'hui) : OPS.5 prépare seulement ; grossir le serveur à 2 écoles réelles ou sur alerte de la carte Santé, pas avant.
- [ ] **PERF.7** Écrans « Impayés » et tableau de bord plus légers *(P1, S à M, 🤖, après PERF.6)* — aujourd'hui ≈ 90 Mo et ≈ 57 Mo par requête (`docs/03` § 9) : calcul en SQL (agrégats, pas d'objets Python par frais), `assertNumQueries`, mémoire du conteneur Django mesurée avant et après (`make perf`), limite du conteneur revue si le gain le permet ; résultat dans `docs/claude/recherches/`. Chaque Mo gagné repousse le passage à 4 Go.

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

## 5 ter. Notes et bulletins comme à l'école (bloc NB, demandé le 2026-10-18)

But : que chacun ne voie et ne fasse que ce qui le concerne, comme dans une école congolaise : l'enseignant garde ses interrogations pour lui et envoie une **fiche de cotes** ; le **directeur des études** contrôle les fiches, voit qui n'a pas encore envoyé, et reçoit les bulletins finalisés ; le **titulaire** prépare les bulletins de sa classe ; le **conseil de délibération** décide à chaque période et en fin d'année ; le repêchage est une vraie **seconde session**. Recherche : `docs/claude/recherches/2026-10-18-notes-deliberation-rdc.md` (aucune règle nationale de passage en ligne : chaque école applique son règlement des études).

**Regard senior** : on garde ce qui marche (saisie, feuilles, bulletin fidèle, versions figées de la délibération, situations, passage) et on corrige le circuit, la visibilité et les règles ; pas de seconde base de notes : la fiche de cotes est une **vue des totaux** de la feuille existante (`GradeSheet`), pas une copie. Les règles restent **réglables par école**, avec deux préréglages tirés des sources ; celui par défaut est à confirmer (Q15 de `06`).

- [x] **NB.1** Carnet de l'enseignant et fiche de cotes *(P1, M, 🤖 ; fait le 2026-10-19 : pas de fiche « renvoyée » dans `make demo`, qui n'écrit rien au journal)* — les évaluations (interrogations, devoirs, travaux pratiques) et leurs notes ne sont visibles et modifiables que par l'**enseignant du cours** (serveur : 403 pour tout autre rôle, directeur des études et titulaire compris) ; les autres ne reçoivent que la **fiche de cotes** de la période (un total par élève, au maximum du cours, examens à part) ; l'enseignant **envoie et signe** la fiche, envoyée en même temps au DE et au titulaire ; le DE la **valide** ou la **renvoie avec remarques** (motif, journal) ; un remplaçant passe par la réattribution du cours (charges, 8.1), plus par `grades.enter_any`, qui ne sert plus qu'à saisir des totaux ; mode « sans devoirs » (8.4.0) inchangé. Tests : isolation, 403 sur le détail pour DE, titulaire et préfet, renvoi avec motif au journal.
- [x] **NB.2** Tableau du directeur des études *(P1, S à M, 🤖, après NB.1 ; fait le 2026-10-19 : dans « Suivi des notes », ex-« Validation des notes » ; palmarès dans les fiches de cotes ; « Bulletins » quand toutes les fiches sont validées, puis, depuis NB.3, quand le titulaire les dit prêts)* — **maquette d'abord** : par période, chaque classe et chaque cours : pas commencée, en cours, envoyée, validée, renvoyée ; « Quelles classes n'ont pas encore envoyé » ; rappel en un geste à l'enseignant (notification) ; classes complètes ; **tableau synthétique** de la classe (totaux, pourcentages, places, sans le détail des interrogations) ; **palmarès** imprimable ; bulletins finalisés de chaque classe.
- [x] **NB.3** Espace du titulaire *(P1, M, 🤖, après NB.1 ; fait le 2026-10-19 : « Ma classe », `/homeroom` ; seuils « au moins la moitié » en attendant NB.4 ; conduite corrigée dans « Conduite », pas ici)* — **maquette d'abord** : sa classe : fiches reçues (totaux, lecture seule), ce qui manque, **conduite et application** de la période (8.5.1), vérification, puis « **bulletins prêts** » quand toutes les fiches sont validées (le DE et le préfet les voient finalisés) ; statistiques de la classe ; droits limités à sa classe.
- [x] **NB.4** Règles de délibération du règlement de l'école *(P1, M, 🤖 ; fait le 2026-10-19 : préréglage « courant » par défaut en attendant Q15 ; une colonne « Catégorie » par cours, qui remplace « Repêchage » ; la règle citée apparaît aussi dans « Repêchage » ; l'espace du titulaire compte au seuil de passage)* — remplace les règles de 8.4.1 (fenêtre de repêchage de 45 à 50 %, qui ne correspond à aucune source) : **passe** = total ≥ seuil **et** chaque cours ≥ seuil **et** conduite acceptable ; **repêchage** = échecs partiels avec le total ≥ seuil de repêchage, **nombre de cours au plus**, combinaisons interdites (deux **cours principaux** ensemble, ex. mathématiques et français ; N **branches d'option** ensemble), catégories **sans repêchage** (pratique professionnelle, atelier) ; **double** sinon ; **exclusion** proposée (a déjà doublé la classe, conduite ou application « Mauvaise » N périodes de suite, redoublements au maximum) ; **exception d'âge** (élève jeune, entre deux seuils : double plutôt qu'exclu) ; **seuil plus haut** pour entrer dans la dernière classe ; catégorie de chaque cours (`Course` : générale, option, pratique ; cours principal) ; deux préréglages (« courant » : 50 %, 4 repêchages ; « réseau catholique » : 53 % pour le repêchage, 55 % pour la dernière classe, ni maths et français, ni 3 options, ni pratique) ; la décision proposée cite la règle appliquée. Tests : chaque règle.
- [x] **NB.5** Conseil de délibération, par période et en fin d'année, avec PV *(P1, M, 🤖, après NB.2 et NB.4 ; fait le 2026-10-19 : une `Deliberation` par session, `term` vide = fin d'année ; pas de décision par élève à la période ; conduite toujours calculée, donc jamais « manquante » ; procès-verbal en PDF)* — membres (préfet qui préside, DE, titulaire, enseignants de la classe) : eux seuls voient le tableau avant la proclamation (secret) ; **délibération et proclamation de chaque période et semestre** (bulletin de la période remis aux parents, avec 8.8), en plus de la fin d'année (8.4.2 garde ses versions figées) ; **procès-verbal** imprimable (présents, décisions, écarts, signatures) ; conduite confirmée par le conseil.
- [x] **NB.6** Seconde session (repêchage) *(P1, S à M, 🤖, après NB.5 ; fait le 2026-10-19 : une seconde délibération par classe, `Deliberation.second_session` ; repêchage accordé par le conseil contre la proposition : chaque cours échoué se repasse ; note de repêchage figée à la proclamation ; heure et salle de l'examen écrites à la main ; pas de nouvelle donnée dans `make demo`, proclamer la 3HT Électronique A suffit)* — après la proclamation de fin d'année : liste des élèves et des cours à repasser, **convocation** imprimable avec la date fixée par l'école ; note de l'examen de repêchage par l'enseignant du cours, signée (8.4.1) ; l'élève **garde son pourcentage** ; **délibération de seconde session** (décision finale : passe, double, réorienté) ; bulletin et passage de classe (8.4.5) suivent la nouvelle version.

L'**horaire** (emploi du temps) reste dans EDT et IA : construit par le solveur à partir de la **grille horaire officielle** de chaque classe et des **charges** des enseignants (8.1), expliqué et ajusté avec l'IA (IA.2), validé par le directeur des études ; horaire des interrogations et des examens compris (EDT.4, complété le 2026-10-18).

---

## 5 bis. Hors ligne par module (bloc HL, demandé le 2026-10-18)

But : que l'école continue de travailler là où le réseau manque, sans rendre l'application lourde ni le serveur fragile. **Critères** : l'action se fait-elle là où internet coupe (caisse, classe, file de la rentrée) ? peut-elle attendre le réseau (un parent debout avec l'argent, une classe devant l'enseignant : non) ? risque de conflit (une écriture ajoutée, comme un paiement : faible ; une règle partagée, comme un barème : élevé) ? poids sur l'appareil et sur le serveur (instantané, synchronisation) ?

| Module, action | Aujourd'hui | Sans réseau ? | Pourquoi |
|---|---|---|---|
| Caisse : encaisser, reçu, réimpression, clôture, annulation demandée | ✓ (V1.0) | **indispensable** | parent devant la caisse, coupures fréquentes |
| Élèves : recherche, fiche, solde | ✓ lecture (V1.0) | **indispensable** | la caisse et le secrétariat en ont besoin |
| Notes : saisie | ✓ (8.2.3) | **indispensable** | l'enseignant saisit en classe ou chez lui |
| Inscription d'un nouvel élève | non | **indispensable** (HL.1) | file de parents à la rentrée, réseau saturé ; l'élève doit exister pour payer |
| Conduite (titulaire), faits de discipline | non | utile (HL.2) | même usage que les notes |
| Sorties de caisse (FIN.2) | à faire | **indispensable** | même caisse, même session : prévu hors ligne |
| Présences, carte d'élève (V1.5) | à faire | **indispensable** | appel en classe, contrôle à la porte : à concevoir hors ligne dès le départ |
| Prêts de la bibliothèque et des ateliers (V1.6) | à faire | utile | prêt et retour = écritures ajoutées, sans conflit : à prévoir dans INV.1 |
| Portail des parents | en ligne | lecture seule (HL.3) | forfaits courts : revoir les derniers paiements et reçus sans réseau |
| Calendrier, annonces (lecture) | en ligne | utile, plus tard | se lisent depuis l'instantané quand il les porte |
| Bulletins, documents PDF, délibération | en ligne | **non** | calcul et PDF au serveur ; décisions à plusieurs ; on imprime avant la coupure |
| Configuration : frais, rôles, classes, paramètres | en ligne | **non** | règles partagées : un conflit casserait les comptes |
| Tableau de bord, impayés | en ligne | non | n'a de sens qu'avec les données de tous les appareils |
| Paie, finances de l'école, console | en ligne | non | bureau, peut attendre ; risque d'erreur sur l'argent |

**Regard senior** : chaque fonction hors ligne ajoute des données sur l'appareil, des opérations à synchroniser et des cas de conflit à tester ; on ne la met que là où l'école est bloquée sans elle. Toutes passent par la même file (UUID v7, opérations idempotentes, `ChangeLog`) : jamais un second mécanisme.

- [x] **HL.0** Règle *(fait le 2026-10-18 dans ce plan)* — la définition de « fini » (§ 8.2) demande que le plan de chaque tâche dise si la fonction marche sans réseau, d'après ce tableau ; `03` § 5.1 renvoie ici.
- [ ] **HL.1** Inscription hors ligne *(P1, M, 🤖)* — nouvel élève, sa famille et son inscription créés sur l'appareil (UUID v7), encaissables tout de suite ; code famille et matricule définitifs donnés à la synchronisation (provisoires à l'écran, fiche d'inscription imprimée après) ; doublon possible entre deux appareils (même nom, même date de naissance) signalé au secrétariat, jamais fusionné seul ; test Playwright réseau coupé (inscrire, encaisser, rétablir, aucun doublon de paiement).
- [ ] **HL.2** Conduite et discipline hors ligne *(P2, S, 🤖)* — comme les notes (8.2.3) : cotes de conduite et faits de discipline gardés sur l'appareil, envoyés au retour du réseau.
- [ ] **HL.3** Portail : dernières données sans réseau *(P1, S, 🤖)* — le Portail montre, sans réseau, les derniers paiements, reçus et annonces déjà chargés, avec « vu le … » ; rien n'est modifiable ; données effacées à la déconnexion.

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

- [ ] **WEB.1** Site de la plateforme — **découpée et avancée le 2026-10-17** (demande de l'utilisateur, une fois Google Search Console réglée) en WEB.1a → WEB.1c, ci-dessous. Reste ici, en V1.3 : la page des prix, quand ABO et le tarif (T6) existent.

**Site public et visibilité (WEB.1a → WEB.1c, demandés le 2026-10-17)** — But : qu'on trouve la plateforme, l'espace parents et son école **avec très peu de mots** (« Mwangaza School », « Mwangaza parents », « gestion scolaire Goma »), et qu'elle paraisse aussi sérieuse que les grands logiciels. Socle déjà en ligne depuis le 2026-10-14 (`apps/core/site.py` : page fr/en, données structurées, `robots.txt`, `sitemap.xml`, `llms.txt`) ; Search Console et Bing réglés par toi.

- [x] **WEB.1a** Étude et maquettes *(P0, M, 🤖)* — **d'abord regarder comment font les sites qui existent**, puis faire mieux : au moins 8 sites, dont des SaaS de référence (Stripe, Linear, Notion), des logiciels scolaires (PowerSchool, Toddle, Classe365 ou Fedena, Index Éducation / Pronote, Zeraki au Kenya, Edves au Nigeria) et des services africains grand public (Wave, M-Pesa). Pour chacun : structure, sections, ce qui convainc, animations, vitesse sur un téléphone. Note avec sources dans `docs/claude/recherches/` : ce qu'on reprend, **ce qu'on fait mieux** (vitesse sur une connexion lente, français et anglais, argent en USD et FC, hors ligne, Mobile Money à venir). Puis **maquette de chaque page à 390, 820 et 1440 px** avant tout code : accueil, écoles (directeur, comptable, caissier, enseignant), parents, modules, démonstration et contact, « Trouver mon école », mentions et confidentialité. Identité **propre** : bleu Kivu, nuit, lumière, jaune de la flamme, lignes de relief (lac Kivu, volcans), Atkinson Hyperlegible Next. **Interdit, parce que ça fait « site généré par une IA »** : dégradés violet ou indigo, taches floues en fond, verre dépoli, icônes 3D génériques, illustrations générées, slogans creux. Chaque animation est dessinée dans la maquette avec son rôle (guider l'œil, montrer le produit en action), jamais pour décorer.
- [x] **WEB.1b** Pages *(P0, M, 🤖, après WEB.1a)* — pages Django mises en cache, lisibles sans JavaScript. **Animations là où elles servent** : apparition des sections au défilement, captures du produit qui s'enchaînent, chiffres qui montent, survol des cartes ; en CSS et quelques lignes de JavaScript, sans nouvelle bibliothèque, coupées par `prefers-reduced-motion`. **Images** : vraies captures du produit (données de démonstration, WebP ou AVIF, chargement différé) ; photos d'écoles, de salles et d'ateliers libres de droits, ou fournies par toi, sans visage d'élève reconnaissable sans accord. Pages par public : écoles, **parents** (ce qu'ils voient, lien vers `parents.<domaine>`, installation sur le téléphone), « **Trouver mon école** » (on tape le code et on arrive sur `https://<code>.<domaine>/app/`, sans liste publique des écoles), questions fréquentes, page **Démonstration et contact** (son formulaire : WEB.1d). Pied de page complet : liens, contact WhatsApp, langues, mentions, « © DTMS » qui mène à `https://dtms.site`. Nom, logo, couleurs, contact, modules : lus dans l'identité de la plateforme et le catalogue, rien en dur (règle 9). Vérifié avec `make apercu` aux trois largeurs, et Lighthouse mobile ≥ 90. **Fait le 2026-10-18** : 7 pages × 2 langues (`core/site.py`, `site_content.py`, gabarits `core/site/`), captures par `make captures-site`, pages dans `make apercu ecran=site` ; ajoutés à ta demande : bulletin officiel animé au nom de l'ITIG et carte « École pilote » (citation seulement avec ses vrais mots) ; formulaire de démonstration → WEB.1d ; Lighthouse : voir la PR.
- [x] **WEB.1d** Demande de démonstration *(P0, M, 🤖, après WEB.1b ; découpée de WEB.1b le 2026-10-18 à ta demande, trop grande pour une conversation ; **faite le 2026-10-18** : formulaire, écran console « Demandes » (`/demo-requests`), alerte sur l'écran et e-mail si le serveur a une boîte d'envoi (`DJANGO_EMAIL_*`, ta part : `A-FAIRE.md` 6 quaterdecies), effacement à un an, adresse et réseaux dans l'identité ; ajouté : « Nombre d'élèves » facultatif (maquette) et note interne)* — formulaire Django de la page Démonstration (maquette `maquettes/site/demonstration.html`) : nom, fonction, école, ville et téléphone obligatoires (numéro RDC normalisé, même règle que le Portail), e-mail et message facultatifs, consentement ; CSRF ; **spam** : champ caché + 5 demandes par heure et par adresse IP, sans dépendance. Modèle de plateforme (pas `TenantModel` : aucune école), rangé dans la console (écran « Demandes de démonstration », **maquette d'abord**, à côté des espaces : statut nouveau, rappelé, espace d'essai ouvert, sans suite) ; alerte au super-admin (notification et e-mail), rien envoyé à un service tiers ; effacement au bout d'un an (confidentialité). Même tâche : **adresse postale** et **liens des réseaux sociaux** (WhatsApp, Facebook, Instagram, LinkedIn, YouTube, TikTok ; vides = cachés) ajoutés à l'identité de la plateforme (console), lus par le pied de page, la page Démonstration et les données structurées `sameAs` (WEB.1c) (règle 9 ; texte du site en attendant).
- [x] **WEB.1c** Visibilité *(P0, S, 🤖 + 👤, avec WEB.1b)* — **image de partage** 1200 × 630 par page (WhatsApp, Facebook, LinkedIn), tirée de l'identité de la plateforme ; icônes du site complètes. **Données structurées** : éditeur DTMS (`Organization`, `url` https://dtms.site, `sameAs`), auteur Guelord Mwenderwa (`Person`, `sameAs` : GitHub et les profils que tu donnes), `SoftwareApplication` (application éducative, web, Android, iPhone), questions fréquentes, fil d'Ariane ; liens rangés dans les réglages (`SOFTWARE_*`), pas dans les gabarits. **Recherches courtes** : titre et description de chaque page écrits pour elles ; nom constant « Mwangaza School » en plus de « Mwangaza » (mot swahili très répandu : seul, il se perd dans les résultats) ; `hreflang` fr/en ; images dans le `sitemap.xml`. **Espace parents trouvable** : la page de connexion du Portail devient indexable (titre « Espace parents »), le reste du Portail, la Gestion et la console restent `noindex`. Toi : liens vers `mwangazaschool.com` depuis `dtms.site` et tes profils, fiche Google Business Profile ; Search Console : sitemap renvoyé, indexation demandée, couverture relue une semaine après. **Fait le 2026-10-18** : image de partage par page et par langue (Pillow, `core/share.py`, maquette `site/partage.html`), champ d'identité « Nom pour la recherche » (`site_name`, console), données structurées sur chaque page, titres réécrits, images dans le `sitemap.xml`, connexion du Portail indexable (Caddy) ; pas d'étoiles ni de prix pour Google (rien d'inventé) ; titres modifiables : SITE ; ta part : `A-FAIRE.md` 6 terdecies et 7 bis.

- [ ] **WEB.2** Site de chaque école *(L, V1.7)* : à la racine de `{code}.mwangazaschool.com/` (la Gestion reste à `/app/`). L'école remplit elle-même son contenu depuis la Gestion : présentation, options et sections, admissions, actualités (annonces marquées « publiques »), galerie, contact, frais affichés seulement si elle le choisit ; publié ou non. **Sécurité** : modèles de pages fixes, texte en Markdown limité et nettoyé, aucun HTML ni script fourni par l'école, images ré-encodées (S.4), formulaire de contact limité. Domaine propre à une école : P3 (certificats à la demande, risque d'abus). Design : comme WEB.1 (références, maquette aux trois tailles, photos de l'école, pied de page complet), les couleurs et le logo de chaque école.

### 6.3 bis Équipe de la plateforme (EQ) — P1, demandée le 2026-10-18

But : quand d'autres personnes rejoignent Mwangaza (support, commercial, communication), chacune n'a que les droits de son travail, pour qu'une mauvaise manipulation ne fasse pas tomber une école ni la plateforme. Aujourd'hui, la console n'a qu'un rôle : super-admin, qui peut tout (`IsPlatformAdmin`, 19 points d'API).

**Regard senior** : pas de rôles libres comme ceux des écoles (M.3) : l'équipe restera petite, et des droits libres sur la console sont un risque. **Rôles fixes dans le code**, une liste de droits fins, plusieurs rôles possibles par personne. Les actions sans retour restent au seul propriétaire, avec confirmation. Tout ce qu'un membre fait est au journal de la plateforme sous son nom. Un membre du support qui ouvre les données d'une école passe par l'accès déjà noté et signalé à l'école (S.3.1).

| Rôle | Peut | Ne peut pas |
|---|---|---|
| Propriétaire | tout, dont l'équipe, l'identité de la plateforme, l'arrêt d'un espace réel | — |
| Technique | santé du serveur, appareils, tâches de fond, journal | changer une école, les comptes, le site |
| Support | voir les écoles, réinitialiser un mot de passe ou une double authentification (noté, école prévenue), espaces de démonstration | arrêter un espace réel, l'identité, l'équipe |
| Commercial | demandes de démonstration (WEB.1d), espaces d'essai et de démonstration, offres | données d'un espace réel |
| Communication | contenus du site (SITE), nouveautés envoyées aux écoles (5.4.3), témoignages | écoles, comptes, santé |
| Finance (V1.3) | abonnements, factures, échéances (ABO) | le reste |

- [x] **EQ.1** Équipe : serveur *(P1, M, 🤖)* — droits de la plateforme (`platform.schools.view`, `platform.schools.manage`, `platform.schools.stop`, `platform.accounts.support`, `platform.demos.manage`, `platform.leads.manage`, `platform.site.edit`, `platform.news.publish`, `platform.health.view`, `platform.audit.view`, `platform.billing.manage`, `platform.identity.edit`, `platform.team.manage`), rôles fixes ci-dessus, membre = compte avec un ou plusieurs rôles ; **double authentification obligatoire** pour tout membre ; `IsPlatformAdmin` remplacé par une vérification du droit sur **chaque** point de la console (test : chaque rôle reçoit 403 hors de ses droits) ; invitation, retrait (sessions coupées tout de suite) ; le propriétaire ne peut pas se retirer s'il est le seul ; journal de la plateforme avec l'auteur. Le super-admin d'aujourd'hui devient propriétaire.
- [x] **EQ.2** Équipe : écrans de la console *(P1, S à M, 🤖, après EQ.1)* — **maquettes d'abord** : « Équipe » (membres, rôles, dernière connexion, inviter, retirer), menu de la console réduit aux droits de chacun, confirmation renforcée des actions sans retour (taper le code de l'école pour l'arrêter).

### 6.3 ter Site géré depuis la console (SITE) — P1, demandée le 2026-10-18

But : la personne chargée de la communication tient le site à jour sans développeur : actualités, témoignages, questions fréquentes, écoles de référence, annonces, offres, photos.

**Regard senior** : **pas de constructeur de pages libre** (mise en page cassée, failles par du HTML collé, pages lentes, référencement perdu). Les **modèles de pages restent fixes** (WEB.1b) ; ce qui change souvent devient des **contenus structurés** saisis dans la console, en français et en anglais, avec aperçu avant publication et journal. Texte mis en forme : paragraphes, listes, gras, liens, rendus par le serveur sans HTML fourni (pas de dépendance ; sinon la demander). Images ré-encodées (S.4), texte alternatif obligatoire, crédit. **Témoignage publié seulement avec l'accord écrit** déposé (fichier) ; **photo avec un élève reconnaissable seulement avec l'accord coché et déposé**. Coût serveur : une lecture par page, mise en cache, cache vidé à chaque publication (numéro de version du site). Les textes principaux des pages restent dans le code et ses traductions (relus dans une PR) ; leurs titres et descriptions pour la recherche deviennent modifiables (avec WEB.1c).

- [x] **SITE.1a** Contenus du site : questions, « Prochainement », bandeau *(P1, M, 🤖, après EQ.1 ; SITE.1 découpée le 2026-10-19)* — questions fréquentes (accueil et parents), « Prochainement », bandeau d'annonce du site (texte, lien, dates de début et de fin) : modèles de plateforme, écran « Site » de la console (maquette d'abord), droit `platform.site.edit`, au journal ; les listes de `core/site_content.py` (WEB.1b) y passent, données structurées comprises ; les points des modules restent dans le code (ils décrivent le logiciel). **Fait le 2026-10-19** : `SiteEntry`, `SiteBanner`, écran `/site` de la console, textes d'avant repris par la migration, cache du site vidé à chaque changement.
- [ ] **SITE.1b** Contenus du site : témoignages, écoles de référence, titres de recherche *(P1, M, 🤖, après SITE.1a)* — témoignages (école, personne, fonction, citation fr/en, accord écrit déposé, fichier privé), écoles de référence (nom, logo, chiffres, lien), titres et descriptions de recherche de chaque page (WEB.1c) ; onglets du même écran.
- [ ] **SITE.2** Actualités *(P1, M, 🤖, après SITE.1a)* — articles (titre, résumé, texte mis en forme, image, langue, brouillon / publié / programmé, auteur) ; pages `/actualites/` et `/en/news/`, liste paginée, dans le `sitemap.xml` ; maquettes d'abord.
- [ ] **SITE.3** Photothèque *(P1, S, 🤖, après SITE.1a)* — photos envoyées depuis la console (ré-encodées, WebP en deux tailles, métadonnées retirées), texte alternatif, crédit, case « élève reconnaissable » qui exige l'accord déposé ; choisies dans les pages et les articles.
- [ ] **SITE.4** Offres *(P1, S, 🤖, avec ABO et WEB.1 prix)* — offres et prix affichés sur le site, saisis dans la console à partir du catalogue des abonnements.
- [ ] **SITE.5** Réseaux sociaux *(P1, S, 🤖 + 👤, après EQ.1 et WEB.1d)* — les comptes de Mwangaza (WhatsApp Business, page Facebook, Instagram, page LinkedIn, YouTube, TikTok) sont tenus par le membre « communication » : il en modifie les liens dans la console (droit `platform.site.edit`), un lien vide disparaît du site ; chaque actualité (SITE.2) a son bouton de partage (WhatsApp, Facebook, LinkedIn : simples liens, aucun script ni traceur des réseaux). **Toi** : créer les comptes avec l'adresse `@mwangazaschool.com` (OPS.4), double authentification (OPS.3), et donner l'accès par les rôles de chaque réseau (Meta Business Suite, administrateurs de la page LinkedIn), **jamais un mot de passe partagé** ; quand le membre part, on retire son rôle.

### 6.4 Emploi du temps (EDT) — P1, V1.4

Faisable, et utile à toutes les écoles. **Avis de développeur senior** : un emploi du temps sans conflit est un problème de contraintes ; une IA seule ne garantit pas zéro conflit (elle peut placer un enseignant dans deux classes à la même heure sans le voir). Donc : un **solveur** calcule, et l'**IA aide** autour (IA.2). Solveur proposé : OR-Tools CP-SAT (Google, licence Apache 2.0, utilisé partout pour ce problème) — **dépendance acceptée le 2026-10-13**.

- [ ] **EDT.1** Données *(M)* — après la 8.1 : grille horaire de l'école (jours, heures, récréations, demi-journées), salles et ateliers (type, capacité), volume horaire hebdomadaire de chaque cours par classe, enseignants (charge maximale, jours et heures où ils sont disponibles, cours qu'ils peuvent donner, enseignant partagé avec une autre école), contraintes (au plus N heures du même cours par jour, heures doubles pour les travaux pratiques d'atelier, cours à ne pas mettre en dernière heure…).
- [ ] **EDT.2** Éditeur et contrôle des conflits *(M)* : grille par classe, par enseignant et par salle ; déplacer une heure à la main ; chaque conflit montré tout de suite (enseignant, salle, classe, charge dépassée) ; versions (brouillon, publiée), l'ancienne gardée.
- [ ] **EDT.3** Génération automatique *(L)* : le solveur place tout en respectant les contraintes obligatoires et au mieux les souhaits ; en tâche de fond, une à la fois, temps limité (le serveur est partagé) ; s'il n'y a pas de solution, il dit **quelle contrainte bloque** ; on peut verrouiller des heures avant de relancer.
- [ ] **EDT.4** Publication *(S)* : PDF par classe, par enseignant, par salle ; **horaire des interrogations et des examens** de chaque période, fait par le directeur des études (ajouté le 2026-10-18, § 5 ter) ; emploi du temps dans le Portail (parents) et pour chaque enseignant ; changement après publication notifié (5.6). Plus tard : heures prestées pour la paie (7.3), appel en classe (V1.5).

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

- [ ] **INV.1** Moteur commun *(M ; prêts et retours prévus hors ligne, § 5 bis)* : articles, exemplaires avec étiquette QR (lue par la caméra comme la carte, V1.5), stock par lieu (bibliothèque, chaque atelier), mouvements immuables (une erreur se corrige par un mouvement inverse), inventaire annuel avec écarts ; audit.
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
  - [x] **8.3.3** Bulletin **fidèle au formulaire officiel**, d'après deux vrais bulletins reçus le 2026-10-15 (3e HT, IGE/P.S/137 ; 4e HT, IGE/P.S/096 ; scans dans `docs/ecole-pilote/prive/builtin/`, hors Git) : le 3e HT sert de **modèle par défaut à toute classe et option** ; la dernière année (`Level.has_state_exam`) remplace « Examen de repêchage » par le bloc « Examen d'État » (points obtenus et maximum, %, code du centre, résultat final, témoignage). Mesures (largeurs de colonnes, hauteurs de lignes, cadres) relevées sur les scans, mises à l'échelle de la zone imprimable ; police serif de type Times (Liberation Serif embarquée, comme Atkinson) ; cases noires (examen des cours sans examen, Application et Conduite hors périodes), lignes MAXIMA par groupe, MAXIMA GÉNÉRAUX, place et effectif, Application et Conduite par période, N° ID, province, ville, commune, N° permanent (champs de l'école et de l'élève, saisis par l'école, repris à l'import). Contrôle : superposition du PDF sur le scan à 150 ppp, écart de 1 mm au plus *(M)*
  - [x] **8.3.4** **Options d'impression au choix de la personne qui imprime** (IMP.1) : sur tout document imprimable (liste de classe, impayés, fiches de cotes, bulletins, reçus) un panneau « Imprimer » où elle choisit les colonnes à garder (moins de papier), le nombre d'exemplaires par feuille (1, 2, 3), le papier (A4, A5) et le sens, mémorisés par personne et par document ; le serveur applique ces choix (`columns`, `per_sheet`, `paper`, `orientation`), sans réglage de l'école sauf les valeurs de départ *(M)*
  - [x] **8.3.5** Notes seules sur le formulaire pré-imprimé (Q11 : texte placé au millimètre sur les cases du formulaire de l'école), impression de toute la classe en lot, démo *(M)*
  - [x] **8.3.6** **Fiches de cotes** : fiche d'un cours (élèves × périodes et examens, total du semestre, moyenne, plus haute et plus basse note, nombre sous la moitié, signature de l'enseignant), fiche vierge à remplir à la main, tableau de toute la classe (cours × élèves, servira à la délibération 8.4) ; droits `grades.enter` (ses cours) ou `grades.enter_any` ; options d'impression de 8.3.4 *(M)*
- [x] **8.5.1a** **Conduite : barème et incidents** *(P1, M)* — le directeur de discipline (DD, `discipline.configure`) tient la **liste des infractions avec leurs points** (modèle de départ proposé, modifiable) et les **seuils** TB, B, AB, ME, MA réglables par l'école ; tout enseignant (`discipline.record`) attribue une infraction à un élève (date, motif, note) ; liste des incidents d'un élève ; droits ajoutés aux rôles de départ et aux écoles existantes ; audit, isolation, `make demo`. Modèle : `04` § Conduite et discipline
- [x] **8.5.1b** **Conduite : parents et bulletin** *(P1, M, après 8.5.1a ; faite le 2026-10-16)* — le **parent est prévenu** (notification et carte « Conduite » de la page de l'enfant au Portail) ; la cote de conduite de chaque période se calcule d'après les points (`ConductGrade` : correction seule stockée) et alimente la ligne Conduite du bulletin ; le DD ou la délibération (8.4) peut la corriger avec un motif (`discipline.override`, journal)
- [x] **8.5.1c** **Application** *(P1, S, après 8.5.1b ; faite le 2026-10-16)* — cote d'application de chaque période proposée d'après le pourcentage de la période, corrigée par le titulaire (avant 8.4) avec motif, journal ; alimente la ligne Application du bulletin (`ApplicationGrade`, même forme que `ConductGrade`) — issue #282
- [ ] **8.4** *(découpée le 2026-10-16 en 8.4.0 à 8.4.6 ; issue #49 = suivi)* Délibération, repêchage, bulletin complété, situations de classe et d'école, passage de classe, proclamation. Tout reste dans le module `academics` (le lien avec les frais, seulement si l'école a aussi le module `finance`) : une école sans ce module n'en voit rien.
  - [x] **8.4.0** **Saisie des points sans devoirs** *(P1, S ; faite le 2026-10-16)* — réglage de l'école (tout l'établissement ou par cours) : soit des devoirs détaillés (comme aujourd'hui), soit **seulement le total de la période** (et des examens) reporté sur la fiche de cotation ; bulletin, fiches de cotes et délibération lisent les deux de la même façon — issue #293
  - [x] **8.4.1** **Règles de réussite et examens de repêchage** *(P1, M, après 8.4.0)* — règles de l'école (départ proposé, I16 à confirmer : réussite à 50 % du total, cours échoué sous 50 %, repêchage ouvert de 45 à 50 % ou pour tout cours échoué, nombre de cours échoués au repêchage qui fait échouer l'élève) ; saisie de la **note de repêchage de chaque cours échoué** par son enseignant, avec **sa signature** (la colonne « Examen de repêchage » du bulletin, ou « Examen d'État » en dernière année) ; échouer tous les repêchages (ou plus que le seuil) = échec proposé — issue #294
  - [x] **8.4.2** **Délibération d'une classe** *(P1, M, après 8.4.1 ; faite le 2026-10-17)* — tableau de la classe ; **décision proposée par le système** (règles de 8.4.1) puis **décision prise** : admis (passe), doublant, repêchage, réorienté, exclu, **abandon** ; quand la décision prise **diffère** de la proposition (réussi mais doublant, échoué mais passe), l'écart est **signalé** (pastille, motif obligatoire, journal) et compté à part dans les statistiques ; correction de la conduite et de l'application ; date de délibération ; classe « proclamée » seulement après validation, et **les résultats proclamés sont figés** (instantané : une correction ensuite = nouvelle version avec motif et journal, le bulletin déjà remis ne change pas en silence) — issue #295
  - [x] **8.4.3** **Bulletin complété** *(P1, S, après 8.4.2 ; faite le 2026-10-17)* — le bas du bulletin se remplit tout seul : repêchage par cours avec signature de l'enseignant, **mention « passe » / « double » cochée** (autres mentions à biffer selon la délibération), **date** de proclamation, nom et signature du chef d'établissement, cachet ; maquette `gestion/bulletin` d'après les scans — issue #296
  - [x] **8.4.4** **Situation de chaque classe et de l'école** *(P1, M, après 8.4.2 ; faite le 2026-10-17)* — à imprimer : par classe, inscrits, réussites, échecs, abandons, doublants, exclus, taux, par cours aussi, palmarès ; pour **toute l'école** : lauréat de l'école et sa classe, meilleur de chaque classe, taux par classe, niveau et global, **écarts de délibération**. **Critère au choix à chaque édition** : règles de la classe (repêchage compris) ou **moyenne seule** (≥ 50 %) — issue #297
  - [x] **8.4.5** **Passage de classe et confirmation de place** *(P1, M, après 8.4.2 ; faite le 2026-10-17)* — à la clôture de l'année : admis au niveau suivant, doublants dans la même classe, exclus et abandons retirés ; **confirmation de place des anciens** selon la décision (réussite ou non), demandée au parent par le Portail avant la rentrée ; rien créé sans confirmation de l'école — issue #298
  - [ ] **8.4.6** **Proclamation et frais** *(P1, M, après 8.4.3 **et NB.5** ; avec 8.8)* — à la proclamation, le bulletin va au parent **si la famille a payé le montant exigé** (réglage de l'école, solde de `finance`) ; sinon il reçoit un message « paiement pas encore finalisé » (sans cacher la décision de passage : on ne chasse pas l'enfant) ; **dérogation** accordée par le préfet (droit dédié, motif, durée, journal) pour une famille ou un élève ; la demande du parent passe par le Portail (voir 8.8)
  - [x] **8.4.7** **Reprise des résultats de l'année précédente** *(P1, S, avant 8.4.5 ; faite le 2026-10-17)* — une école qui arrive avec Mwangaza n'a pas les notes de l'an dernier : elle saisit ou importe (Excel) seulement la **décision finale** et le pourcentage de chaque ancien, ce qui suffit à confirmer sa place (comme la reprise des paiements `origin=prior`) — pourcentage repris dans la délibération (élève sans aucune note), import de toute l'école depuis un modèle garni ; issue #300
- [ ] **8.8** Portail parents : notes, bulletins PDF ; tableau de bord : résultats ; **pont parent ↔ école** : le parent écrit à l'école depuis le Portail (demande de dérogation, question sur une note ou une décision), l'école répond, fil gardé par élève *(P1, M ; version légère, la messagerie complète reste V1.7)*
- [ ] **PERF.6** **Rapidité des notes et de la délibération** *(P1, S, après 8.4.4)* — `make perf` étendu à la feuille de notes, au tableau de délibération, au palmarès, aux situations et au bulletin d'une classe de 60 et d'une école de 1 200 élèves ; budget de requêtes (`assertNumQueries`) sur chaque liste ; PDF en tâche de fond par paquets ; résultat dans `docs/claude/recherches/`
- [ ] **S.10** **Revue de sécurité des notes, bulletins et du Portail** *(P1, S, après 8.8 et 8.4.6)* — un parent ne voit que ses enfants (test d'accès à l'élève d'un autre, d'une autre école) ; bulletins PDF non devinables et servis après contrôle du droit ; blocage des frais impossible à contourner par l'adresse du fichier ; journal des consultations de bulletins ; limite d'essais ; permissions de la délibération (`grades.validate`, dérogation) vérifiées sur chaque point d'API
- [ ] **FIN.1 → FIN.3** Dépenses, sorties de caisse, budget (§ 6.1) *(P1)*

### V1.3 — Plateforme commerciale

- [ ] **ABO.1 → ABO.3** Abonnements par module (§ 6.2) *(P1)*
- [ ] **WEB.1** Page des prix du site (§ 6.3) *(P1 ; le site public est avancé au lancement : WEB.1a → WEB.1c)*
- [ ] **S.7 → S.9** Protection des données (dont **export complet des données d'une école** à sa demande ou à son départ), détection, revue ASVS (§ 4 bis) *(P1)*

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
- [ ] **8.5.2** Messagerie parent ↔ titulaire / administration ; rendez-vous ; mérites et récompenses ; renvoi temporaire et exclusion *(P2, L)* — la conduite est faite en 8.5.1a et 8.5.1b (P1)
- [ ] **8.6** Portail élèves ; espace titulaire *(P2, L)*
- [ ] **8.7** Transfert d'élève entre écoles de la plateforme ; attestations *(P2, M)*
- [ ] **8.9** Sondages ; blocage des bulletins en cas de dette (désactivé par défaut) *(P2, S)*
- [ ] **8.2.4** Import des points d'une classe depuis un classeur Excel (modèle fourni, erreurs montrées ligne par ligne, rien enregistré avant confirmation) *(P2, S)*
- [ ] **I18N.1** Swahili (puis lingala) pour le Portail et les messages aux parents, à côté du français et de l'anglais *(P2, S)*
- [ ] **SUP.1** Aide dans l'application (guide court par écran) et demande d'aide de l'école à la plateforme, suivie dans la console *(P2, M)*
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
- [ ] **Hors ligne** : le plan de la tâche dit si la fonction doit marcher sans réseau, et pourquoi (tableau du § 5 bis) ; si oui, elle passe par la file existante et a son test réseau coupé.
- [ ] Aucune écriture en base ajoutée à chaque requête ; tout ce qui est lourd en tâche de fond, par paquets.
- [ ] Les documents rendus faux sont corrigés dans la même PR.
- [ ] Sécurité : aucune donnée d'une autre école, permission vérifiée côté serveur, entrée de l'utilisateur jamais affichée comme du HTML, envoi de fichier contrôlé (S.4), point public limité en nombre d'essais.
- [ ] **Rapidité** : tout écran de liste ou d'impression a un nombre de requêtes borné (pas de N+1, testé), est paginé, et reste fluide avec 1 200 élèves ; les calculs lourds (classement, statistiques) sont faits une fois et gardés, pas à chaque ouverture.
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

Aucune écriture en base ajoutée à chaque requête · tout ce qui est lourd en tâche de fond, par paquets, une à la fois · rien d'ajouté à la première synchronisation des appareils · pas de nouveau processus sans raison mesurée · temps de réponse mesurés sur le vrai serveur pour tout écran qui parcourt tous les élèves (seuil : 2 s pour 1 200 élèves) · **aucun PDF de plusieurs pages dans une requête web** (un bulletin ≈ 1,9 s et 13 Mo : bloc PERF, § 4 ter).

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

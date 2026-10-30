# Suivi du projet

Ce fichier dit **où en est le projet**. Il est mis à jour à chaque étape (début et fin de tâche, décision, document reçu, blocage). Les cases à cocher restent dans `05-plan-de-travail.md` ; ici on garde l'état, l'avancement et le journal.

## État actuel

| | |
|---|---|
| Phase | V1.0 et V1.1 finies et en ligne ; **plan regroupé en 17 lots le 2026-10-29** pour finir toute la V1 avant la V2 (`05` § 2 : un lot = une PR) |
| Lot en cours | **Lot 2 — Site public**, partie 7/9 faite (formules, partenaires, chiffres, témoignages, chat) ; reste : articles longs et photos (8), coordonnées et déploiement (9) ; fiche `docs/claude/plans/lot-2.md` ; PR #412 ouverte (verte, pas fusionnée) |
| Prochain lot | Lot 3 — Vendre : contrats, abonnements, factures |
| Toi, en parallèle | `make deploy` si NB.8 et R.1 ne sont pas en ligne, puis PERF.8b ; OPS.1 ; identité de la plateforme et premier espace réel `itig` ; pour le lot 3 : tarif (T6), informations légales (I20), juriste ; Q15 et Q16 ci-dessous |
| Issue GitHub | #411 (une par lot, jalon « V1 complète ») |
| Branche | `lot/2-site` (PR du lot 2) |
| Dernière mise à jour | 2026-10-30 (lot 2 fini) |

## Avancement

Avant le 2026-10-29 : **153 tâches faites** (V1.0 : 67 ; V1.1 : 12 ; lancement, modules et rôles, sécurité S.1 à S.6, exploitation, site public, notes et bulletins, équipe, emploi du temps, IA : 74). Détail : annexe de `05` et `archives/05-file-2026-10-29.md`.

| Lot | Parties faites | Parties |
|---|:-:|:-:|
| 1 — Marque Mwangaza | 3 ✓ | 3 |
| 2 — Site public refait | 6 | 9 |
| 3 — Vendre : contrats, abonnements, factures | 0 | 3 |
| 4 — Bulletins aux parents | 0 | 3 |
| 5 — Console finie | 0 | 3 |
| 6 — Aide, guide et support | 0 | 2 |
| 7 — Finances et caisse complètes | 0 | 3 |
| 8 — Cours communs et notes | 0 | 2 |
| 9 — Emploi du temps fini et IA | 0 | 2 |
| 10 — Carte et présences | 0 | 3 |
| 11 — Bibliothèque et ateliers | 0 | 3 |
| 12 — Personnel et paie | 0 | 3 |
| 13 — Messagerie et portail des élèves | 0 | 2 |
| 14 — Inscriptions, transferts, langues | 0 | 3 |
| 15 — Sites des écoles | 0 | 2 |
| 16 — Cartes NFC et lecteurs | 0 | 2 |
| 17 — Revue finale de la V1 | 0 | 1 |
| **V1 complète** | **2 lots sur 17** | **43** |

Sur GitHub : jalon « V1 complète », une issue par lot (les anciens jalons V1.2 à V1.7 gardent les issues des tâches, fermées par la PR de leur lot).

## Bloquants et en attente

Liste complète et détaillée (maquettes M1–M20, informations I1–I18, décisions T1–T6) : `07-a-fournir.md` — plus rien n'y bloque le travail. Ce que l'utilisateur doit faire et comment : `../A-FAIRE.md`. Ici, seulement ce qui bloque bientôt.

| Sujet | Attendu de | Bloque |
|---|---|---|
| Cloudflare en proxy (nuage orange) et pare-feu du serveur limité à Cloudflare — décidé le 2026-10-13 (`A-FAIRE.md` § 9 quater, 5 ter) | toi (réglage Cloudflare) + Claude | premier espace réel |

## Questions ouvertes

À trancher au plus tard pendant la tâche indiquée. Une fois tranchée : déplacer dans le journal.

| # | Question | Pour | En attendant |
|---|---|---|---|
| Q12 | Découpage officiel de l'année au **primaire** (trimestres ? périodes et examens par trimestre ?) : pour proposer un modèle « primaire » à la création d'une année (C1) | avant la première école primaire (aucune en V1.0 : l'ITIG n'a pas de primaire) | pas de modèle « primaire » : une école du primaire part du modèle « 3 trimestres, 6 périodes, 3 examens » ou d'un découpage vide, et l'ajuste |
| Q15 | **Règles de délibération par défaut** (préréglage proposé à une école neuve, NB.4) : « courant » — passe à 50 % du total **et** 50 % dans chaque cours, conduite acceptable ; repêchage si échecs partiels avec 50 % du total, 4 cours au plus, jamais mathématiques et français ensemble, jamais la pratique ou l'atelier ; double sinon ; ou « réseau catholique » — 53 % pour le repêchage, 55 % pour entrer en dernière classe. Lequel par défaut, et l'ITIG en suit-il un autre ? | avant NB.4 | préréglage « courant », modifiable par chaque école (recherche du 2026-10-18 : aucune règle nationale en ligne) |

| Q16 | **Grille horaire proposée à une école neuve** (EDT.1a) : durée d'une heure (50 min ?), début 7 h 30, 7 heures du lundi au vendredi et 4 le samedi, récréations de 15 min après la 3e heure et de 10 min après la 5e, au plus 2 heures du même cours par jour, au plus 6 heures par jour pour un enseignant. Est-ce l'usage courant (à l'ITIG et ailleurs à Goma) ? | avant EDT.1a | ces valeurs ; chaque école les change dans ses paramètres |

Q1 à Q11 tranchées le 2026-09-26, Q13 et Q14 le 2026-10-10 (voir le journal). Prochain numéro : Q17.

## Journal

Entrées jusqu'au 2026-10-19 : `archives/06-journal-jusqua-2026-10-19.md`.

### 2026-10-30 — Lot 2 : demande d'agrandissement du site
Après essai, l'utilisateur veut un site **complet** (prix, partenaires, chiffres, témoignages, chat, articles longs avec photos, photos libres de droits à changer avant le vrai lancement) puis le déploiement : parties 6 à 9 ajoutées à la fiche. Décisions : 3 formules d'exemple modifiables dans la console ; chat maison (boîte de réception dans la console) + WhatsApp ; contenus d'exemple marqués « exemple » dans la console ; photos libres de droits seulement (pas de photos payantes téléchargées) ; coordonnées reçues : WhatsApp +243 856 725 368, `contact@mwangazaschool.com`, `support@mwangazaschool.com` (à confirmer), adresse Goma, Nord-Kivu, quartier Katoyi, Afia Bora, rue Scout. Fait : appareils noirs, reçu dans la carte hors ligne, journée en défilement avec fenêtre au clic.

### 2026-10-30 — Lot 2 : site public refait (parties 1 à 5)
Partie 5 : le site en ligne est gardé tel quel (demande de l'utilisateur après essai de la refonte, jugée trop laide) avec les couleurs, le logo et la police de la nouvelle marque, angles droits, photos inchangées ; ajout des actualités (liste paginée, article, accueil, `sitemap.xml`) et des titres de recherche réglés dans la console.
Tests : articles paru / programmé / brouillon / autre langue, redirection des modules, `sitemap.xml` ; captures 390 et 1440 px sans débordement. Suite : lot 3 (vendre).

### 2026-10-30 — Lot 2 : serveur du site (partie 2/5) et visuels décidés
- Fait : témoignages, écoles de référence, titres de recherche et photo du haut des pages, actualités (programmées sans tâche de fond, petit Markdown), photothèque (WebP sans métadonnées, accords privés), réseaux pour la communication ; API console, journal, cache, 4 articles dans `make demo` ; tests des droits, du journal, des accords, de l'article programmé, du Markdown et des photos.
- Décision (utilisateur) : les photos Wikimedia, trop anciennes, quittent le site ; à la place, les vrais écrans de l'application dans des téléphones et ordinateurs dessinés (comme ShuleSystem), avec des animations sobres et soignées. Lot passé à 5 parties (④ visuels, ⑤ pages).

### 2026-10-29 — Lot 1 : marque Mwangaza (fini)
- Fait : livre de marque PDF et logo (parties 1-2) ; partie 3 : thème des trois applications au bleu uniforme et au soleil, barres qui suivent la couleur principale de la plateforme, symbole et logotype (Poppins) dans le code, relief retiré, icônes et favicon renommés (`symbole-*.png`), couleurs par défaut migrées (`#1A2F80` / `#FFA81E`) sans toucher une couleur choisie, guides PDF régénérés, maquettes et skill `design` à jour.
- Tests : couleurs par défaut acceptées, accent refusé s'il est illisible sur la couleur principale (modèle et console), migration qui garde une couleur choisie ; écrans principaux regardés à 390 et 1440 px (logo du portail réduit dans l'en-tête du téléphone).
- Décisions : l'accent se contrôle contre la couleur principale (4,5:1) ; texte des écrans toujours en Atkinson ; seules 6 captures de maquettes refaites (`maquettes/README.md` § Logo).
- Suite : fusion, `make deploy`, puis lot 2 (site public refait).

### 2026-10-29 — Lot 1 : piste de marque choisie

Trois pistes proposées (A « Lever du jour », B « Horizon », C « Registre ») ; l'utilisateur retient **A**, avec le logotype écrit comme celui d'Ujuzi (Poppins, minuscules, serré) et des couleurs qui ne fassent pas « IA » : Ardoise, Craie, Bleu uniforme `#1A2F80`, Brume du lac, Soleil levant `#FFA81E`. Il proposait de garder C comme second logo si c'était une bonne idée : **un seul logo** (raison : fiche du lot). Page : `maquettes/marque/marque.html`. Suite : partie 2, livre de marque PDF.

### 2026-10-29 — Plan regroupé en 17 lots (une PR chacun)
- Demande : le projet avance trop lentement ; moins de PR, chacune plus complète ; finir toute la V1 avant la V2 ; marque refaite sur le modèle du livre de marque fourni (`docs/ecole-pilote/prive/`) ; site qui ne ressemble plus à une IA (grands sites, isig.ac.cd, photos d'élèves congolais) ; contrats, factures, abonnements, guide d'utilisation, console complète.
- Fait : `05` § 2 réécrit (62 tâches restantes + 9 ajoutées → 17 lots), § 2 bis (BRAND.1-2, SITE.R, CTR.1, ABO.4, CON.1-3, AIDE.1-2), § 8.1 « un lot, du début à la fin » ; `CLAUDE.md`, skills `tache`, `etat`, `noter` et `A-FAIRE.md` passés aux lots ; ancienne file et journal jusqu'au 2026-10-19 archivés (`docs/archives/`).
- Décisions : un lot = une branche = une PR, fait en parties (une conversation chacune) avec push de sauvegarde ; file figée ; une issue par lot (jalon « V1 complète ») ; S.7 répartie entre CTR.1 et CON.2 ; SUP.1 avancée au lot 6.
- Suite : fusion, puis lot 1 (Marque Mwangaza).

### 2026-10-27 — Tâche R.1 : import du personnel depuis Excel
- Fait : « Comptes du personnel » → « Importer depuis Excel » : modèle, aperçu ligne par ligne (numéro invalide ou de démonstration, rôle inconnu ou manquant, nom manquant, doublon ; « déjà dans l'école » ignorée), comptes créés d'un bloc ; lettres d'accès PDF, deux par A4, 50 par impression. Maquettes `gestion/personnel-import` et `gestion/lettre-acces-personnel`.
- Tests : aperçu sans écriture et sans rien dire des autres écoles, enregistrement par lots avec journal, fichier renvoyé deux fois, aperçu périmé (409), mot de passe de la lettre valable et compte déjà connecté exclu, école beta refusée, 403 sans `roles.manage` ; écran (Vitest).
- Décisions : pas de mot de passe à l'import (Argon2 ≈ 0,2 s chacun, un à la fois par processus) ; il est créé à l'impression de la lettre, réimprimable ; droit `roles.manage`.
- Suite : fusion, `make deploy`, puis OPS.1, identité de la plateforme et premier espace réel `itig`.

### 2026-10-27 — Tâche NB.8 : titulaire, bulletins et saisie depuis Ma classe
- Fait : bulletins imprimés par le titulaire et le cotitulaire pour leur classe (liste des élèves avec l'état du bulletin, sans le droit de lire tous les élèves) ; « Ma classe » : « Saisir » (fiche rendue à la main) et « Bulletins de la classe » ; « Cours et maxima » figé (la branche reste visible) ; « Programme officiel du ministère » expliqué (résumé, confirmation) ; récréation jamais couverte par une longue séance (éditeur, impression), libellé « Avant et après la récréation ».
- Tests : titulaire et cotitulaire impriment leur classe, 403 ailleurs, 404 autre école, journal ; menu du titulaire ; impression coupée autour de la récréation.
- Suite : fusion, `make deploy`, puis R.1.

### 2026-10-27 — Mise en ligne de NB.7, démo refaite, correction
- Fait : `make deploy` (23d406b) ; `make deploy-check` vert ; démo du vrai serveur (`itig`, créée par la console) renommée `itig-demo` par la migration, puis remise à zéro (`demonstrations.reset`, acteur : l'administrateur principal).
- Panne : le remplissage s'est arrêté à l'étape 8 sur 22 (une seule tâche de 10 min et 384 Mo pour tout : horaire plein, ~800 élèves et leurs notes ; carte Santé « Arrêté faute de mémoire »). Correction : **une tâche par étape**, reprise à l'étape où l'on en était (`demonstrations.fill`, `core.demo.fill(start, count)`) ; après sa mise en ligne, le remplissage de `itig-demo` est relancé là où il s'est arrêté, puis le logo de l'ITIG posé.
- Constat : `make deploy-demo` est refusé sur le vrai serveur (`DJANGO_DEMO_DATA` absent, voulu) et remettrait l'identité de la plateforme : réservé à un serveur d'essai ; documents corrigés. Migration manquante du libellé « Administrateur principal » (`accounts.0019`) ; la CI vérifie désormais qu'aucune migration ne manque (`makemigrations --check`).
- Suite : fusion de la correction, `make deploy` ; R.1.

### 2026-10-27 — Tâche NB.7 : saisie par le titulaire ou un tiers, démonstration au niveau de l'application
- Fait : cotitulaire d'une classe (`ClassGroup.co_homeroom_teacher`) ; le titulaire et le cotitulaire, comme le DE et la secrétaire, saisissent un total par élève dans un cours rendu sur papier, puis l'envoient (jamais le carnet d'un enseignant qui a ses devoirs) ; « Ma classe » pour le cotitulaire, sans « Bulletins prêts » ; `<Table freeze>` (titres et noms visibles) sur les tableaux à remplir ; atelier : séances aussi longues que l'école le veut, sans la limite de 2 h par jour. Démonstration : `itig-demo` (migration qui renomme l'espace en ligne, logo et images compris ; `itig` libre pour la vraie école), 39 h par classe sans trou, 40 enseignants fictifs, 1re période sans case vide et validée, « validée par » la directrice des études ; `make deploy-demo` (`demo --fresh`). Console : « Administrateur principal » au lieu de « Propriétaire ». Portfolio : Mwangaza, DTMS et Afronova présentés comme projets de l'entreprise (poussé sur `main` du dépôt du portfolio).
- Tests : `test_cotitular.py` (titulaire, cotitulaire, carnet privé, Ma classe, isolation), atelier de 4 h d'affilée, scénario de `test_demo.py` (grilles pleines, enseignants, `--fresh`) ; ≈ 106 s au lieu de 44 s (calcul de 20 s, trois fois).
- Défaut trouvé par la CI et corrigé : un reçu hors ligne d'une école au code avec tiret (`itig-demo`) était « inconnu » à la vérification (numéro découpé sur ses tirets, `finance/verification.py`) ; `demo --fresh` fait un `ANALYZE` avant d'effacer (plan de minutes par paquet sur base neuve) et se teste à part.
- Décisions : cotitulaire = une clé (un par classe) ; démo calculée en 20 s ; file réordonnée (05 § 2, « Recevoir les vraies données ») avec **R.1** (import du personnel) ajoutée.
- Suite : fusion, mise en ligne, `make deploy-demo`, puis R.1.

### 2026-10-27 — Tâche EDT.5a : horaire des interrogations et des examens (serveur)
- Fait : EDT.5 découpée (5a serveur, 5b écran/PDF/lecture). `ExamSchedule` (une par période, brouillon/publié) et `ExamSitting` ; contrôles rouges (classe, surveillant, salle, date hors période) et orange (absence, congé) en 4 requêtes ; publier/rouvrir (droit `timetable.publish`), journal ; `make demo` : épreuves de la 1re période de l'ITIG.
- Tests : `test_exams.py` (droits, isolation, chaque contrôle, publication refusée, figé, journal) ; scénario de `test_demo.py`.
- Décisions : l'horaire est placé à la main par le DE (pas de solveur) ; pas de clé vers `Evaluation` ; notification et lecture enseignants/Portail en 5b.
- Suite : EDT.5b (maquette d'abord), puis EDT.6.

### 2026-10-26 — Tâche IA.2b : analyse et propositions
- Fait : `timetable/review.py` (usage `timetable_review`) : dossier de chiffres calculés par le code (contrôles de l'année ou conflits d'un horaire calculé, règles, cours des classes en cause, codes courts) ; réponse JSON : explication + au plus 8 actions d'une liste fermée (assouplir une règle, la mettre en pause, changer les séances d'un cours, conseil « un enseignant de plus ») ; chaque action revérifiée à la lecture et à l'application (`POST review/<id>/apply/`, mêmes services et même journal que l'écran normal), `finish` clôt l'appel. Panneau « Demander conseil » (diagnostic et éditeur de brouillon), maquette `conseil-emploi-du-temps`.
- Tests : `test_review.py` (action invalide ou d'une autre école écartée, application avec journal, une action appliquée une fois, droits 403, isolation 404). Capture du panneau non faite (l'IA répond seulement avec une vraie clé).
- Décisions : « déplacer une heure » non proposé (l'éditeur le fait ; ne jamais toucher aux heures verrouillées) ; pas de modèle ni de migration.
- Suite : EDT.5 / EDT.6 / IA.1.2 (file `05` § 2).

### 2026-10-25 — Tâche IA.2a : consignes en phrases → règles
- Fait : `timetable/assistant.py` (consignes fixes, noms de l'école seulement avec un code court par cours, enseignant et salle, schéma de sortie, chaque règle revérifiée par `constraints.clean`, enregistrement `source=ai` avec la phrase) ; API `POST constraints/assist/`, `GET …/<id>/`, `…/keep/`, `…/abandon/` ; bouton « Dire mes consignes » de la carte Règles et fenêtre à cases (maquette `consignes-emploi-du-temps`).
- Tests : `test_assistant.py` (2 : phrases → règles vérifiées, cours d'une autre école et code inventé refusés, rien d'une autre école envoyé à l'IA, enregistrement une seule fois avec journal et appel « gardé » ; droits, verrous de l'IA, appel d'une autre école ou d'une autre personne en 404) ; capture à 390 et 1440 px de la fenêtre non faite (pile arrêtée).
- Décisions : « ne vient pas le vendredi » = `teacher_free_day` obligatoire (pas de nouveau kind) ; code court = 8 derniers caractères de l'UUID (le début d'un UUID v7 est l'heure : il se répète) ; correction d'une proposition après l'enregistrement par « Modifier » (pas de second éditeur) ; détail des cours envoyé seulement pour ceux que la phrase nomme.
- Suite : IA.2b (file `05` § 2, ligne 15.8).

### 2026-10-25 — Tâche IA.1.1 : socle IA (usages, cinq verrous, crédits, plafond)
- Fait : application `apps/ai` — catalogue `uses.py` (trois usages : grille de cours, règles de l'horaire, analyse), `authorize` (interrupteur et plafond de la plateforme → module et usage affecté, pause → `ai.use` et droit de l'écran hôte → crédits ≥ coût maximal → limite par personne), `submit` (une demande = une ligne, même identifiant = un seul appel), `execute` (file `ai`, `client.py` seul à parler à l'API), `AiCall` sans texte, `AiBalance` / `AiUsageMonth` / `AiPlatformMonth`, alertes à 80 % et 100 % (console) et à 80 % des crédits (notification `ai_credits`), purge, session support comptée sur la plateforme ; module `ai` et droit `ai.use` ; `manage.py ai_allowance` pour régler une école jusqu'à IA.1.2 ; `make demo` : usages et crédits fictifs.
- Tests : `apps/ai/tests/test_ai.py` (10 : chaque verrou refuse sans appeler l'API, limite par personne, coût en entiers, doublon, support, erreur sans frais, alertes une fois, isolation, journal de la plateforme, purge) ; file `ai` ajoutée au contrôle des tâches ; l'étape `test_demo` vérifie les crédits de démonstration.
- Décisions : pas de réservation de crédits (une ligne lue) ; réponse gardée dans `AiResult` (effacée quand gardée, abandonnée ou après 24 h : pas de cache partagé) ; `worker-ai` éteint tant que `COMPOSE_PROFILES=ai` (128 Mo de plus que la marge) ; `anthropic` chargé à l'appel seulement. Suite : IA.2a (consignes en phrases → règles).

### 2026-10-25 — Tâche EDT.4c : impressions de l'horaire
- Fait : `timetable/prints.py` et `GET /api/timetable/print/` (classe, enseignant avec sa charge, salle, horaire général ; version au choix ; une page par classe, enseignant ou salle) ; page « Imprimer l'horaire » (`/app/timetable/print`, aperçu puis PDF) et bouton dans l'éditeur ; PDF gardés (PERF.2) ; maquette `impression-emploi-du-temps`. EDT.4 est finie.
- Tests : `test_prints.py` (droit, isolation de l'école, contenu : récréation, case de deux heures, charge de l'enseignant, séance hors grille ; PDF gardé relu) ; captures à 390 et 1440 px sans débordement.
- Décisions : pas d'abréviation saisie (noms courts de l'écran + légende) ; A4 sur deux pages ou A3 sur une pour l'horaire général ; brouillon imprimable, marqué comme tel.
- Suite : IA.1.1 (file `05` § 2, ligne 15.7).

### 2026-10-25 — Tâche EDT.4b : lecture de l'horaire publié
- Fait : `timetable/schedule.py` (séances de la version publiée, début et fin d'après la grille de chaque classe) ; « Mon horaire » (`/app/my-timetable`, ses cours et « Ma classe » pour le titulaire), gardé sur l'appareil (table Dexie `reads`) et lu sans réseau ; carte « Horaire de la classe » sur la page de l'enfant (Portail, gardée par le service worker) ; notification `timetable_published`, une par personne touchée ; composant partagé `WeekSchedule` ; maquettes `gestion/mon-horaire`, `portail/enfant-horaire`.
- Tests : `test_schedule.py` (isolation, module, brouillon jamais lu, portail 404, une notification par personne et seulement aux touchés), `reads.test.ts`, scénario de `test_demo` ; captures à 390 et 1440 px sans débordement.
- Décisions : lecture sans réseau par la dernière lecture gardée plutôt que par l'instantané (rien au `ChangeLog` à chaque publication) ; `HasSchoolAccess` vérifie aussi le module ; le nom de l'enseignant seul, jamais son téléphone.
- Suite : EDT.4c.

### 2026-10-22 — Tâche EDT.4a : publication de l'horaire
- Fait : EDT.4 découpée (lecture en EDT.4b, #383 ; impressions en EDT.4c, #384) ; droit `timetable.publish` (chef, DE, rôles qui réglaient l'horaire) ; `timetable/versions.py` : publier (refusé tant qu'il y a du rouge, date d'effet, ancienne version archivée, journal `timetable.published`), API `…/drafts/<id>/publish/` et `/api/timetable/versions/` ; éditeur : « Publier » (fenêtre), version publiée ou archivée en lecture seule, « Nouveau brouillon depuis cette version » ; maquette `gestion/publication-emploi-du-temps` dessinée d'abord ; `make demo` publie l'horaire calculé de l'ITIG.
- Tests : `test_publication.py` (droit, isolation, conflit, date, immuabilité, archivage, journal), scénario de `test_demo` ; captures à 390 et 1440 px sans débordement.
- Décisions : le reste à placer ne bloque pas (horaire provisoire) ; date d'effet jamais avant la version en vigueur (heures prestées, EDT.6).
- Suite : EDT.4b.

### 2026-10-22 — Tâche EDT.3b : écran du calcul de l'horaire

- Fait : maquette `gestion/calcul-emploi-du-temps` dessinée d'abord, puis la page `/app/timetable/calculate` (boutons « Calculer » de l'éditeur et de « Règles et contrôles ») : brouillon de départ, portée, temps ; « Calculer » grisé si les contrôles ont du rouge ; suivi toutes les 2 s pendant un calcul, annulation ; souhaits non tenus ; règles qui bloquent en phrases avec l'écran qui corrige (`?rule=` ouvre la règle). Console : temps de calcul au plus, par école (`School.timetable_max_seconds`, 1 min par défaut, 3 min au plus), dans la carte des modules.
- Tests : temps ramené au maximum de l'école ; réglage écrit au journal de la plateforme et borné ; phrases de blocage (Vitest) ; captures à 390 et 1440 px (états « calculé » et « impossible »).
- Décisions : réglage par école plutôt que pour toute la plateforme ; pas de pourcentage (le solveur n'en donne pas) : temps écoulé sur temps donné ; `GET /api/timetable/runs/` rend `{time_limit_max, runs}`.
- Suite : EDT.4 (publication et impressions).

### 2026-10-22 — Tâche EDT.3a : calcul automatique de l'horaire (serveur)
- Fait : EDT.3 découpée (écran en EDT.3b, #379) ; `timetable/solver.py` (CP-SAT : unités, O1–O7, réglages, règles, souhaits, stabilité ; impossible → règles qui bloquent par hypothèses), `TimetableRun`, `runs.py`, tâche `run_timetable` (file `heavy`), API `/api/timetable/runs/` ; résultat dans un nouveau brouillon ; contrôle 7 `group_sessions_differ` ; OR-Tools ajouté ; `make demo` : heures de l'ITIG sous sa grille, horaire calculé en 10 s.
- Tests : `test_runs.py` (petit cas de 3 classes et 4 enseignants jugé par `checks.draft`, recalcul d'une classe, cas impossible nommé, droits, isolation, même demande, refus) ; scénario `test_demo` ; files des tâches et bibliothèques lourdes.
- Décisions : un fil en trois temps (recherche locale pour le premier horaire), pas de verrou Redis, nouveau brouillon plutôt qu'un historique (`03`) ; pic mesuré 257–271 Mo pour tout le processus (`docs/claude/recherches/edt3-solveur-mesures.md`, « À valider »).
- Sécurité : `pip-audit` rouge sur `main` depuis le 2026-10-21 (34 failles connues) ; aiohttp 3.14.5, certifi 2026.10.19, Pillow 13.0.0, pypdf 6.21.2 mis à jour dans le verrou.
- Suite : EDT.3b (écran du calcul).

### 2026-10-22 — Tâche EDT.2b : éditeur de l'horaire, autres vues
- Fait : onglets Classe, Enseignant, Salle, Général dans `/timetable` (vue gardée dans l'adresse) ; vue par enseignant (absences hachurées, charge placées / dues · au plus, « À placer » de ses cours), par salle (heures occupées, cours dont c'est la salle), horaire général (classes en lignes ; semaine en noms courts, un jour en clair ; mêmes gestes) ; teinte « enseignant absent » dans toutes les vues ; maquettes `emploi-du-temps-enseignant` et `-general`.
- Tests : `editor.test.ts` (absence, vues d'un enseignant et d'une salle, grilles mélangées, noms courts distincts) ; `make apercu ecran=gestion/timetable` sans débordement à 390, 820 et 1440 px.
- Décisions : rien de nouveau côté serveur (l'état du brouillon suffisait) ; noms courts calculés, distincts entre les cours d'une même classe ; pas d'« À placer » dans l'horaire général (`03`).
- Suite : EDT.3 (calcul automatique ; OR-Tools à accepter).

### 2026-10-21 — Tâche EDT.2a : éditeur de l'horaire, vue par classe
- Fait : EDT.2 découpée (EDT.2a serveur et vue par classe, EDT.2b autres vues) ; `Timetable` et `TimetableEntry` (jour, 1re heure, longueur), gestes un par un (placer, déplacer, échanger, salle, verrou, retirer, annuler les 50 derniers) dans `timetable/drafts.py`, conflits du brouillon par les contrôles du diagnostic (`checks.draft`) ; écran `/timetable` (maquette `gestion/emploi-du-temps-classe` dessinée d'abord : grille à l'ordinateur, un jour au téléphone, cases teintées pendant le choix) ; `make demo` : un brouillon de l'ITIG avec la 2HT Électricité A placée.
- Tests : `test_drafts.py` (droits, isolation, journal, refus, conflits, annuler, requêtes bornées), `editor.test.ts` (teintes, deux grilles), scénario de `test_demo` ; captures à 390 et 1440 px.
- Décisions : position sans clé vers `TimeSlot`, historique des gestes en JSON sur le brouillon, l'état complet renvoyé à chaque geste (ITIG de démo : 11 requêtes, 145 ms, 39 Ko), dix couleurs de cours en jetons (`03`).
- Suite : EDT.2b (vues par enseignant, par salle, horaire général).

### 2026-10-21 — Tâche EDT.1c : règles de l'emploi du temps et leurs contrôles
- Fait : `TimetableRule` (9 kinds en lignes, schéma par kind dans `timetable/constraints.py`, obligatoire ou souhait avec poids, journal), API `timetable/constraints/` et `choices/`, contrôles 6 (verrous en conflit) et 7 (contradictions, règle sans objet), groupes en parallèle et cours communs comptés une fois ; écran renommé « Règles et contrôles » avec la carte « Règles » et la fenêtre d'une règle (maquettes dessinées d'abord) ; `make demo` : sept règles à l'ITIG, dont l'atelier de la 2HT Électricité A le lundi de la 2e à la 7e heure.
- Tests : `test_constraints.py` (droits, isolation, schéma, journal, groupes, contrôles 6 et 7) et scénario de `test_demo` ; captures à 390 et 1440 px.
- Décisions : les réglages qui ont déjà leur place (heures par jour, charge, journée sans trou) ne deviennent pas des règles ; `stability` en EDT.3 ; matin = avant midi ; un cours dans un seul groupe ; 500 règles au plus (`03`).
- Suite : EDT.2 (éditeur de l'horaire et conflits).

### 2026-10-21 — Dépôt GitHub repassé en public jusqu'à la V2
- Les contrôles de la PR #372 ne démarraient plus : minutes d'Actions du dépôt privé épuisées. À la demande de l'utilisateur, `GUELORD-MWENDERWA/mwangaza` repassé en public (vérifié : la page répond sans connexion). Avant : aucun secret ni fichier de `prive/` ou `depot/` dans ce qui a été poussé depuis le passage en privé (commits de `main` et de la branche EDT.1b).
- Retour en privé à la fin de la V2 (`05`, ligne 9.16 ; `A-FAIRE.md` § 9 quinquies). En public : Actions sans limite, protection des secrets poussés de nouveau active, images du serveur publiques comme avant.

### 2026-10-21 — Tâche EDT.1b : cours, enseignants et contrôles avant le calcul
- Découpée avant de coder : les règles (`TimetableRule`) et les contrôles 6–7 deviennent **EDT.1c** (#371). Fait : placement de chaque cours (séances, au plus N h par jour, salle ou type exigé, récréation, moment) dans la vue « Emploi du temps » de « Cours et maxima », envoyé avec la grille ; disponibilités des enseignants (maximum, heures par jour, absences touchées sur la semaine) dans « Charges des enseignants » ; écran « Contrôles avant le calcul » (`/timetable-checks`, contrôles 1 à 5, rouge et orange, lien vers l'écran où corriger) ; trois maquettes.
- Tests : `timetable/tests/test_checks.py` (placement : droits, module, règles, journal ; disponibilités : isolation, 403, journal ; un cas par contrôle, isolation du rapport), Vitest des absences et des séances, `test_demo.py` (ateliers en deux séances, deux disponibilités, classes surchargées vues).
- Décisions : absences en heures (valables pour les deux vacations) ; la règle de l'école ne descend pas sous la plus longue séance ; heures changées sans le placement = séances recalculées (`03`, journal des décisions).
- Démo ITIG : 11 lignes rouges (9 classes techniques au-delà de 39 h, une salle de classe, le laboratoire), 23 orange (cours sans enseignant). Suite : EDT.1c.

### 2026-10-20 — Dépôt GitHub passé en privé
- Fait (à la demande de l'utilisateur) : `GUELORD-MWENDERWA/mwangaza` en privé, étape 1 de `A-FAIRE.md` § 9 quinquies. Vérifié : sans connexion, le dépôt répond 404. Le déploiement n'en dépend pas : `make deploy` envoie le code depuis la machine (`git archive`), le serveur tire ses images de ghcr.io avec `GHCR_TOKEN` (présent dans `serveur.env`).
- Suite (toi) : passer les images `mwangaza-backend` et `mwangaza-caddy-production` en privé (elles restent publiques sinon, avec le code dedans ; aucune commande ne le permet), puis `make deploy-check` ; surveiller les minutes d'Actions (2 000 par mois en privé, estimation ≈ 300).
- Conséquence : la protection des secrets poussés (push protection) ne s'applique plus en privé gratuit ; le contrôle avant commit (`make hooks`) reste.

### 2026-10-20 — Plan : cours communs, remplaçant, notifications (remis dans le plan)
- Demande de l'utilisateur du 2026-10-17 : cours par niveau et tronc commun entre sections, remplaçant d'un cours (totaux seulement, après envoi de la fiche), notifications partout où c'est utile (désactivables). Tâches 8.1.2a, 8.1.2b, 8.2.5, 8.2.6 (issues #309 à #312) ; réponses : remplaçant désigné par le directeur des études seul ; chaque classe garde ses maxima.
- Constat du 2026-10-20 : le commit du plan était resté sur la machine (jamais poussé) ; les issues existaient, pas les lignes du plan. Remises dans la V1.2, à côté de 8.4.6, sans changer la file (le bloc « Aller vers les écoles » reste devant). 8.1.2b s'appuie sur la règle `joint_courses` de la spécification de l'emploi du temps.
- Années scolaires : chaque année a ses classes, périodes et notes, rien n'est écrasé ; le passage de classe (8.4.5) ne modifie pas l'année passée.

### 2026-10-20 — Tâche EDT.1a : grille horaire et salles
- Fait : app `timetable` (`TimeGrid`, `TimeSlot`, `Room`, `ClassGroup.time_grid` et `home_room`, règles générales dans `School.settings["timetable"]`), module `timetable` et droit `timetable.manage` (préfet, DE, rôles qui avaient `courses.configure`) ; écrans « Grille horaire » (`/time-grid` : réglages, semaine corrigeable case par case, classes et places, règles) et « Salles et ateliers » (`/rooms`), maquettes dessinées d'abord ; `make demo` : grille proposée et salles de l'ITIG, deux vacations aux Volcans.
- Tests : isolation (grille, salle, classe d'une autre école), droits et module, grille proposée (39 places), identifiants des heures gardés, semaines refusées, grille par défaut, capacité, salles retirées, règles, journal ; Vitest du calcul de la semaine ; scénario de `test_demo.py`.
- Décisions : un seul droit pour l'instant ; grille proposée calculée par le serveur seul ; salles jamais supprimées. La démo montre 9 classes HT au-delà de 39 h (heures de la 8.1) : à ramener avant EDT.3. Q16 toujours ouverte (préréglage utilisé en attendant).
- Suite : EDT.1b.

### 2026-10-20 — Tâche EDT.0 : spécification de l'emploi du temps et nouvel ordre
- Demande : aller vers les écoles au plus vite, avec un emploi du temps « parfait » (cours et charges des enseignants, heures fixes comme l'atelier du lundi de la 2e à la 7e heure, pas 5 h de maths le même jour, IA qui aide le DE, horaires imprimables par classe et par enseignant, heures prestées).
- Fait : `docs/specs/emploi-du-temps.md` (paramètres, règles, 7 contrôles avant le calcul, solveur CP-SAT avec règle qui bloque, éditeur, IA en deux usages, versions, impressions, heures prestées, modèle, tests) ; file de `05` : bloc « Aller vers les écoles » (15.1 → 15.11) avant tout le reste ; EDT découpé en EDT.0 à EDT.6 (EDT.1 en deux), IA.2 en IA.2a et IA.2b, IA.1.1 avancée avec lui.
- Décisions : l'IA ne place ni ne valide rien, le solveur vérifie toute proposition ; liste fermée de règles ; heures prestées = horaire publié moins les exceptions notées (pas d'appel en classe avant la V1.5). Q16 ouverte (préréglage de la grille).
- Suite : EDT.1a.

### 2026-10-20 — Tâche PERF.8 : mémoire du serveur sans gaspillage
- Constat (carte Santé, une école fictive) : 28 % libre, `worker` 218/288 Mo, `scheduler` 111/144 Mo. Cause : coût fixe (Django chargé dans 4 conteneurs, 2 travailleurs rapides permanents, ≈ 22 Mo de bibliothèques par processus), pas une fuite ni les données.
- Fait : planificateur sans Django (`backend/beat.py`, `backend/task_schedule.py`, ≈ 139 → 52 Mo, plus de secrets dans son conteneur) ; `worker --autoscale=2,1` (≈ 213 → 135 Mo) ; Web Push, Excel, QR, Sentry chargés à la demande ; `MALLOC_ARENA_MAX=2`, `gc.freeze()` ; `make deploy-memoire`. Mesures : `docs/claude/recherches/perf-8-memoire-2026-10-20.md`.
- Tests : planificateur (tâches connues, bonnes files, sans Django), bibliothèques lourdes absentes au démarrage ; `core`, `audit`, `students`, Web Push verts.
- Plan : PERF.8 (fait) et PERF.8b (P0, mesure hors application après `make deploy`) ; règles de mémoire et coût des tâches à venir dans `05` § 8.5. Suite : toi `make deploy` puis `make deploy-memoire` ; SITE.1b.

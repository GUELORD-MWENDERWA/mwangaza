# Ce qui manque encore

Liste de tout ce qui manque pour aller jusqu'au bout : maquettes, informations de l'ITIG, décisions à prendre. Cocher au fur et à mesure (`/noter` ou `/document-ecole` le font). Établie le 2026-09-26 ; mise à jour le même jour : les 20 maquettes V1.0 manquantes sont dessinées (à valider), puis les réponses de l'utilisateur (Q1 à Q11, principe « l'ITIG est l'école d'exemple »).

Comment s'y prendre (quoi demander à l'ITIG et quand, message à envoyer, comptes à créer, commandes) : [`A-FAIRE.md`](../A-FAIRE.md).

**Rien ci-dessous ne bloque le travail** (décision du 2026-09-26). **On n'attend rien de l'ITIG** (redit le 2026-10-02) : c'est l'école d'exemple, pas la seule ; ce qui manque, Claude l'invente de façon réaliste (dernière section), et chaque école, l'ITIG comprise, saisit ses vraies données elle-même dans l'application. Le § 2 garde seulement la trace des exemples utilisés.

## 1. Maquettes manquantes

30 maquettes ont été fournies. Le 2026-09-26, à la demande de l'utilisateur (T3), Claude a dessiné dans le même système de design les écrans qui manquaient pour la V1.0, plus les bulletins officiels et les cours / maxima (V1.2) : **61 maquettes** au total (`maquettes/index.html`). **Valider** = fusionner la PR des maquettes ; une remarque sur un écran = commentaire de PR, Claude corrige avant de coder l'écran. Pour les lots suivants, même règle : si une maquette n'est pas fournie avant sa tâche, Claude la dessine, code avec elle sans attendre l'accord et la signale dans « À valider » de la PR (décision du 2026-09-29). **Documents imprimables** (reçus, listes, rapports, bulletins…) : même règle, Claude propose le design dans le système de design, état « à valider » (décision du 2026-09-26).

### V1.0

| # | Écran | App | Réf. | Tâche | Maquette (dessinée le 2026-09-26) | Validée |
|---|---|---|---|---|---|:-:|
| M1 | Activation de la double authentification : QR code à scanner + 8 codes de secours à imprimer | Gestion | B4 | 1.3 (API), 1.6 (écran) | `gestion/double-authentification-activation` | [ ] |
| M2 | Choix de l'école après connexion (compte dans plusieurs écoles) + changement d'école dans l'en-tête | Gestion | B3 | 1.2 (API `/api/me/`), 1.6 | `gestion/choix-ecole` | [ ] |
| M3 | Personnel : liste des comptes, créer un compte, attribuer des rôles, désactiver, réinitialiser le mot de passe | Gestion | B1–B3 | 1.2 (API ; plus d'« Autres écoles » : `03` § 4), 1.3 (nouveau mot de passe, réinitialiser la double auth., noms et téléphone : seulement pour un compte qui ne sert que dans l'école), 1.7 (écran) | `gestion/personnel-comptes` | [ ] |
| M4 | Mon compte : mot de passe, PIN, double authentification, langue | Gestion | B4–B5, I2 | 1.3 (API), 1.6 (écran), 3.7 (PIN) | `gestion/mon-compte` | [ ] |
| M5 | Paramètres de l'école : nom officiel, logo, couleur, en-tête des reçus, devises, seuils d'alerte ; à compléter pendant la tâche : contraste de la couleur (Q8), format et exemplaires du reçu, logo noir et blanc | Gestion | A1, cahier § 8.1 | 1.5 (API : identité, couleur avec contraste vérifié Q8, logo, fuseau, devises), 1.7 (écran), 3.2 (reçus), 4.2 (alertes) | `gestion/parametres-ecole` | [x] |
| M6 | Journal d'audit : qui a fait quoi, filtres par personne, action, date | Gestion | I1 | 1.4 (API ; le support n'est pas nommé : « Support Mwangaza »), 1.7 (écran), 2.4 (export Excel), 3.3 (appareil, heure hors ligne) | `gestion/journal-audit` | [ ] |
| M7 | Menu de la Gestion sur téléphone et tablette (moins de 900 px) | Gestion | cahier § 9.4 | 1.6 | `gestion/menu-mobile` | [ ] |
| M8 | Pages d'état : accès refusé, page introuvable, erreur, école suspendue, session expirée, nouvelle version, stockage local refusé, portail hors connexion | Gestion, Portail | — | 1.6 | `gestion/pages-etat` | [ ] |
| M9 | Fiche élève : onglets Identité, Famille, Historique (+ modification) ; corrigée le 2026-09-26 (Q10 : fiche propre à l'école) | Gestion | D2–D4 | 2.2 | `gestion/eleve-fiche-identite`, `-famille`, `-historique` | [ ] |
| M10 | Fiche famille : code famille, tuteurs, enfants **de l'école**, état du portail, réimprimer / nouveau code ; corrigée le 2026-09-26 (Q10) | Gestion | D4, H1 | 2.2 | `gestion/famille-fiche` | [ ] |
| M11 | Fiche d'inscription imprimable (A4, avec code famille) et liste de classe (PDF, Excel) | Impression | D5 | 2.4 | `gestion/fiche-inscription`, `gestion/liste-classe` | [ ] |
| M12 | Accorder une réduction à un élève ; échéancier particulier | Gestion | E3, E4 | 2.5, 2.6 | `gestion/eleve-reduction`, `gestion/eleve-echeancier` | [ ] |
| M13 | Ouvrir une session de caisse ; caisse avant de choisir un élève ; paiements du jour et recherche d'un reçu à réimprimer | Gestion | F1, F6 | 3.1 | `gestion/caisse-ouverture`, `gestion/caisse-accueil` | [ ] |
| M14 | Crédits d'élèves (surpaiements après synchronisation) à traiter par le comptable | Gestion | — | 3.6 | `gestion/credits-eleves` | [x] |
| M15 | Reçu d'annulation (80 mm et A4) | Impression | F7 | 3.8 | `gestion/recu-annulation` | [ ] |
| M16 | Clôtures de caisse vues par le comptable : historique, écarts, détail | Gestion | F8 | 3.8 | `gestion/clotures-caisse` | [x] |
| M17 | Situation financière d'un élève imprimable ; export des impayés (PDF, Excel) | Impression | G1, G2 | 4.1 | `gestion/situation-financiere`, `gestion/impayes-export` | [ ] |
| M18 | Changements de coordonnées faits par les parents, à prendre en compte par le secrétariat | Gestion | H5 | 4.4 | `gestion/changements-coordonnees` | [ ] |
| M19 | Portail : se connecter, mot de passe oublié, installer l'application | Portail | H1, H6 | 4.4 | `portail/connexion`, `portail/mot-de-passe-oublie`, `portail/installer` | [ ] |
| M20 | Guides de première connexion : caissier, comptable, parent | Gestion, Portail | I3 | 4.5.1 | `gestion/guide-premiere-connexion`, `portail/guide` | [ ] |

### V1.0 — clôture

Dessinées par Claude en 4.9 (à valider) : invitations au portail et suivi des comptes activés (`gestion/invitations-portail`), lettre d'invitation, deux par A4 (`gestion/lettre-invitation`). Dessinée par Claude en 4.10 (à valider) : mise en page du guide PDF de la version, qui est sa propre maquette (`frontend/guide/guide.html`, jetons du design, résultat `docs/guide/guide-v1.0.pdf`).

### Lancement — version finie (4.12 à 4.21)

À dessiner par Claude avec leur tâche, d'après les écrans existants (à valider dans la PR de la tâche) : console « Espaces » avec les trois types et l'état « arrêté » (`console/ecoles` mise à jour, 4.15), confirmation « Supprimer » (4.16), création d'un espace de démonstration et fiche d'accès (4.17), bandeau d'essai et de démonstration, reçu « SPÉCIMEN » (4.18), reprise des paiements d'avant Mwangaza (4.19), liste « Mise en route » du tableau de bord (4.20). Dessinée : annulation d'un import (`gestion/eleves-import-annulation`, 4.14, à valider).

### V1.1 — plateforme, notifications, communication

Dessinées par Claude (à valider) : console de la plateforme, tableau de bord et coquille propre à la console (`console/tableau-de-bord`, 5.2.1) ; identité de la plateforme (`console/identite-plateforme`, 5.2.2) ; écoles (`console/ecoles`, 5.3, redessinée d'après `gestion/superadmin-ecoles`) ; comptes (`console/comptes`, 5.4.1) ; appareils (`console/appareils`) et journal avec les sessions support (`console/journal`, 5.4.2) ; annonces aux écoles, avec le bandeau et la liste de la Gestion (`console/annonces`, 5.4.3) ; centre de notifications et réglages de la Gestion (`gestion/notifications`, 5.5.1). À dessiner : centre de notifications du Portail (5.5.2) · messages à une classe, calendrier, circulaires, convocations (5.7).

### V1.2 — carte unique et présences

À dessiner : carte (recto / verso, format carte bancaire et planche A4) et son modèle réglé par l'école (6.1) · poste de liaison des cartes (6.2) · borne de pointage puce / QR (6.3) · suivi des présences et du personnel (6.5) · absences et justification par le parent (6.6). Existe déjà : `gestion/presences-pointage-qr` (6.3), à compléter avec la puce.

### V1.3 — personnel, paie, dépenses

À dessiner : dépenses et rapports entrées / sorties (7.1) · dossier employé et contrats (7.2) · fiche de paie PDF (7.3) · espace enseignant, congés (7.4) · pénalités, validation d'inscription, documents téléversés (7.5). Existe déjà : paie.

### V1.4 — notes, bulletins, vie scolaire

Déjà dessinés le 2026-09-26 d'après les **formulaires officiels** trouvés en ligne : cours et maxima (`gestion/cours-maxima`, 8.1), bulletin des humanités techniques (`gestion/bulletin`, formulaire IGE/P.S/100) et bulletin 7e–8e (`gestion/bulletin-education-de-base`, IGE/P.S/005) — voir `docs/claude/recherches/2026-09-26-bulletins-rdc.md`. Reste à dessiner : attribution des enseignants (8.1) · délibération et palmarès (8.4) · discipline, messagerie, rendez-vous (8.5) · portail élève et espace titulaire (8.6) · transfert et attestations (8.7) · portail parents complet (8.8) · sondages (8.9). Existent déjà : saisie des notes, scolarité d'un enfant.

### V2

À dessiner tâche par tâche (9.1 à 9.15) au moment de les commencer.

## 2. Exemples de données d'une école (l'ITIG)

**Plus rien n'est attendu** (2026-10-02) : l'ITIG saisit ces informations elle-même dans l'application, comme toute école. La colonne « En attendant » dit ce qu'utilisent les données de démonstration ; si un document arrive quand même, `/document-ecole` l'intègre.

### Pour la V1.0

| # | Information | Tâche | Quand | En attendant | Reçue |
|---|---|---|---|---|:-:|
| I1 | Classes 2026-2027 : sections par niveau (7e A, B, C…), options et sections de la 1re à la 4e | 1.7 | semaine 1 | structure publique + sections inventées | [ ] |
| I2 | Format actuel du matricule | 1.7 | semaine 1 | `ITIG-{AAAA}-{0000}` (maquettes) | [ ] |
| I3 | Calendrier 2026-2027 : périodes, examens, dates ; date de proclamation de la P1 | 1.7, Q6 | semaine 1 | modèle secondaire : 2 semestres, 4 périodes, 2 examens | [ ] |
| I4 | Qui fait quoi : préfet, directeurs des études, directeur de discipline, économe / comptable, caissiers, secrétaires, promoteur ; liste des comptes à créer | 1.2 | — | un compte fictif par rôle (9 rôles système) ; l'école crée elle-même ses comptes | [ ] |
| I5 | Grille des frais 2026-2027 : types, devise de chaque frais, montants par niveau / option, tranches et dates limites, frais mensuels | 2.5 | semaine 2 | grille fictive réaliste, à partir de celle des maquettes (minerval en tranches USD, fonctionnement, atelier, motivation mensuelle en FC) | [ ] |
| I6 | Réductions pratiquées (enfants du personnel, fratrie, bourses) et qui les accorde | 2.5 | semaine 2 | modèles du cahier des charges : ils choisissent le motif, la valeur est saisie à chaque fois ; droit `finance.grant_discount` (préfet, comptable) ; valeurs par défaut par école à ajouter si l'ITIG en a de fixes | [ ] |
| I7 | Liste des élèves en Excel (même partielle, pour voir les colonnes) | 2.3 | semaine 2 | ~800 élèves fictifs avec familles, fratries et paiements sur plusieurs mois ; fichier Excel fictif : `make demo-excel` (2.3) | [ ] |
| I8 | Fiche d'inscription et liste de classe actuelles | 2.4 | semaine 2 | maquettes M11 | [ ] |
| I9 | La caisse aujourd'hui : combien de caisses et de caissiers, qui valide une annulation, comment se fait la clôture (le taux est tranché : fixe pour l'année, saisi par le comptable) | 3.1, 3.8 | semaine 3 | 2 caisses, règles des maquettes, taux de l'année 1 $ = 2 850 FC | [ ] |
| I10 | Modèle de reçu actuel (photo) et formulation du montant en lettres | 3.2 | semaine 3 | reçu proposé par Claude ; montant en lettres « Cent cinquante dollars américains et vingt-cinq centimes » (Q5), ajusté quand le reçu arrivera | [ ] |
| I11 | Imprimante thermique (marque, modèle, papier 80 ou 58 mm) ; ordinateurs, tablettes, navigateur ; connexion internet | — | — | tous les formats gérés au choix de l'école (58 mm, 80 mm, A4) ; Chrome | [ ] |
| I12 | Logo haute qualité (vectoriel si possible) + version noir et blanc ; nom officiel exact ; cachet ; en-tête | 1.5, 3.2 | semaine 3 | logo du site web ; version noir et blanc préparée par Claude (`ecole-pilote/documents/2026-09-26-logo-itig-noir-et-blanc.png`) | [ ] |
| I13 | Code de l'école dans l'adresse : `itig` ? | 1.5 | semaine 1 | `itig` | [ ] |

### Pour la V1.1 et la V1.2

| # | Information | Tâche | Reçue |
|---|---|---|:-:|
| I14 | Grille salariale, primes, règle de répartition de la motivation des enseignants, statut SECOPE, avances, retenues | 5.2, 5.3 | [ ] |
| I15 | Bulletin officiel vierge et rempli (photo ou scan), branches et maxima par classe et option — surtout 3e–4e (« 5e, 6e année »), Électronique, Mécanique automobile et 7e–8e. Formulaires IGE/P.S/094, /100 et /005 déjà trouvés en ligne (note de recherche du 2026-09-26) | 6.1, 6.3 | [ ] |
| I18 | Code de l'école (7 chiffres, imprimé sur les bulletins), N° ID et N° permanent des élèves ; bulletin officiel **pré-imprimé** acheté ou imprimé par l'école (question Q11) | 6.3 | [ ] |
| I16 | Règles de délibération (réussite, repêchage, passage), palmarès | 6.4 | [ ] |
| I17 | Cote de conduite et sanctions pratiquées | 6.7 | [ ] |

## 3. Décisions et comptes (toi)

| # | Sujet | Quand | Fait |
|---|---|---|:-:|
| T1 | **Nom et domaine** (Q9) — **tranché le 2026-09-26 : Mwangaza, `mwangaza.school`** ; reste à vérifier la disponibilité et acheter le domaine avant les vraies données d'une école, 4.6.3 (`A-FAIRE.md` § 9 ; le serveur de démonstration s'en passe : DuckDNS, 4.6.2) | domaine acheté avant 4.6.3 | [x] |
| T2 | Valider les propositions Q1 à Q11 de `06-suivi.md` — **tranché le 2026-09-26** (journal de `06-suivi.md`) | avant 1.2 | [x] |
| T3 | Maquettes : les fournir, ou laisser Claude les dessiner (défaut) — **tranché le 2026-09-26 : Claude dessine** ; reste à valider les maquettes dessinées (PR) | maintenant | [x] |
| T4 | Comptes : hébergeur (**tranché le 2026-10-04 : Oracle Cloud « Always Free »**, gratuit, + DuckDNS pour la démonstration ; `A-FAIRE.md` § 9 ter), Cloudflare, stockage objet, suivi d'erreurs (Sentry ou GlitchTip) | Oracle et DuckDNS quand tu mets la démonstration en ligne ; Cloudflare avant 4.6.3 ; le reste avant 4.7 | [ ] |
| T5 | Conditions d'utilisation, politique de confidentialité, contrat de traitement des données avec chaque école (Claude peut rédiger un brouillon) | avant les vraies données d'une école (4.6.2) | [ ] |
| T6 | Tarif des écoles (essai gratuit ?) | avant les abonnements (9.2) | [ ] |

## 4. Données de démonstration

Commande `make demo` (créée en 1.1, enrichie à chaque tâche qui ajoute un modèle ; détail ci-dessous) : elle efface et recrée des données **entièrement fictives et réalistes**, pour le développement et les démonstrations. En production, chaque école saisit ses vraies données (`make demo` y est refusé ; seul l'essai sur plusieurs appareils, `make reseau-demo`, le permet, 4.11). Rien de propre à l'ITIG n'est écrit dans le code : tout passe par les paramètres de l'école de démonstration.

- **École `itig`** « ITIG Don Bosco Goma (démo) » : structure publique réelle (7e–8e EB, 1re–4e, 4 options), couleur `#003C6C`, logo du site web et sa version noir et blanc ; environ **800 élèves** aux noms inventés, avec leurs familles (fratries comprises) ; grille de frais fictive réaliste (frais en USD et en FC) ; taux de l'année 1 $ = 2 850 FC ; 2 caisses ; paiements de septembre à aujourd'hui pour le tableau de bord et les impayés ; un rôle personnalisé « chef d'atelier ».
- **École `volcans`** « Complexe scolaire Les Volcans (fictif) » : petite école (≈ 150 élèves) pour prouver l'isolation entre écoles, avec une famille qui a des enfants dans les deux écoles (deux fiches famille, deux codes, un seul compte parent).
- **Un compte par rôle** (directeur, directeur des études, directeur de discipline, comptable, caissier, secrétaire, promoteur, enseignant, parent, super-admin) avec un mot de passe de développement connu, jamais utilisé en production. Fait en 1.2 : numéros `0000001001` à `0000001010` à l'ITIG (dans l'ordre des rôles de `04` § 8, puis le chef d'atelier), `0000002001`, `…004`, `…005` à Volcans (directeur, comptable, caissière), l'enseignant `0000001008` dans les deux écoles, super-admin `0000000000` ; mot de passe `mwangaza-demo` ; `make demo` affiche la liste. Numéros en +243 0… : jamais ceux de vraies personnes. Depuis la 1.3 : double authentification activée pour les comptes qui l'exigent (directeur, comptable, caissière des deux écoles) avec une même clé de développement affichée par `make demo`, code du moment avec `make totp` ; le promoteur `0000001007` l'active à sa première connexion (pour essayer M1). Journal d'audit (1.4) : `make demo` n'y écrit rien (c'est la préparation du système, pas l'action d'une personne) ; il se remplit avec ce qu'on fait en essayant l'application (connexions, rôles, comptes du personnel) et ne s'efface pas quand on relance `make demo`. Serveur de démonstration en ligne (4.6.2) : mot de passe propre au serveur (`DJANGO_DEMO_PASSWORD`) au lieu de `mwangaza-demo`, et pas de clé commune : chaque compte qui l'exige lie sa propre application à la première connexion et la garde quand `make deploy-demo` est relancé. Depuis la 1.5 : double authentification du super-admin `0000000000` (même clé, `make totp`) ; ITIG de démonstration en essai (couleur `#003C6C`, fin de l'essai dans 90 jours), Volcans active (couleur `#7A3E00`, offre « Standard ») ; logo public de l'ITIG (`ecole-pilote/documents/2026-09-25-logo-itig-carre.png`) ; `make demo` les remet comme au départ (couleur, abonnement, pas suspendues, logo).
- **Identité de la plateforme** (5.1) : nom « Mwangaza », couleurs de départ, sans logo ni icône (la lampe), téléphone de support fictif `+243 000 000 999`, e-mail `support@example.com`, mentions légales qui disent « données fictives » ; `make demo` la remet comme au départ (un nom ou un logo essayé dans l'administration est effacé). Les vraies valeurs (éditeur, hébergeur, contact) se saisissent dans les paramètres de la plateforme.
- **Organisation scolaire** (1.7, en attendant I1–I3) : année 2026-2027 en cours dans les deux écoles. ITIG : découpage du modèle secondaire aux dates des maquettes, niveaux 7e EB, 8e EB, 1re à 4e, options Électricité (`ELEC`), Électronique (`ELO`), Mécanique générale (`MG`), Mécanique automobile (`MA`), **23 classes** (7e et 8e EB A, B, C ; chaque option de la 1re à la 4e, section A ; Électricité 1re B), l'enseignant de démonstration titulaire de la 3e Électricité A, matricule `ITIG-{AAAA}-{0000}`. Volcans : découpage sans dates (à saisir), 7e EB, 8e EB, 1re et 2e des humanités générales, options Scientifique et Pédagogie générale, 4 classes, matricule `LV/{AA}/{0000}`. `make demo` remet ces éléments comme au départ sans effacer ce qu'on a ajouté en essayant, et n'écrit rien au journal.
- **Élèves** (2.2–2.3) : environ 800 à l'ITIG et 150 aux Volcans, aux noms inventés, avec familles (fratries, tuteurs) et inscriptions de l'année ; créés une seule fois par école. `make demo-excel` écrit une liste Excel fictive (~800 élèves, erreurs glissées exprès) pour essayer l'import.
- **Frais** (2.5–2.6, en attendant I5) : grille fictive d'après les maquettes — minerval en tranches USD, fonctionnement et frais connexes en une fois, atelier par option, motivation des enseignants mensuelle en FC, Exetat en 4e ; taux de l'année s'il manque (ITIG 1 $ = 2 850 FC, Volcans 2 830 FC) ; ce que doit chaque élève inscrit ; quelques réductions (enfants du personnel, fratries, bourses).
- **Caisse** (3.1–3.8) : ITIG « Caisse 1 » (caissière `0000001005`) et « Caisse 2 » (comptable `0000001004`), Volcans « Caisse principale » ; toutes refermées à chaque `make demo`. Une seule fois par école : paiements de deux semaines avant la rentrée jusqu'à hier (sur dix élèves, quatre à jour avant la 1re tranche, deux ont donné 60,00 $, un le dû du 30/09, trois rien), une session clôturée par caisse et par jour ; deux crédits d'élèves (bourse accordée après paiement, minerval encaissé deux fois hors ligne) ; demandes d'annulation (une validée, une refusée, une en attente, une du comptable que le directeur valide) ; un appareil par caissier et secrétaire (« Appareils connectés »).
- **Annonces** (4.3) : une seule fois par école, publiées par le directeur : deux à toutes les familles (dont une archivée), une aux dernières classes ; lues par une famille sur deux, jamais par celle du compte du portail (ses annonces restent « Nouvelle »).
- **Annonces de la plateforme** (5.4.3) : une seule fois, publiées par le super-admin : « Maintenance du serveur samedi soir » (toutes les écoles), « Votre période d'essai est prolongée » (ITIG seule), « Nouvelle version de l'application » (archivée) ; aucune lue à chaque `make demo` (le bandeau s'affiche pour chaque compte).
- **Notifications** (5.5.1) : celles des annonces de la plateforme en cours, au personnel actif des écoles visées (19 comptes à l'ITIG, 4 aux Volcans), datées comme l'annonce et remises à « non lues » à chaque `make demo` ; aucun appareil abonné (il s'abonne depuis `/app/notifications`, application construite).
- **Portail** (4.4) : compte `0002000001` (mot de passe `mwangaza-demo`) relié à la famille de l'ITIG qui a aussi des enfants aux Volcans ; le code des Volcans, affiché par `make demo`, sert à « Ajouter un enfant d'une autre école » ; accès remis à chaque `make demo`. Trois demandes de coordonnées des parents attendent le secrétariat de l'ITIG (une seule fois). Environ une famille sur trois de chaque école a activé son compte depuis la rentrée (comptes sans mot de passe utilisable, une seule fois par école : 4.9).

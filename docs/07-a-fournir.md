# Ce qui manque encore

Liste de tout ce qui manque pour aller jusqu'au bout : maquettes, informations de l'ITIG, décisions à prendre. Cocher au fur et à mesure (`/noter` ou `/document-ecole` le font). Établie le 2026-09-26 ; mise à jour le même jour : les 20 maquettes V1.0 manquantes sont dessinées (à valider), puis les réponses de l'utilisateur (Q1 à Q11, principe « l'ITIG est l'école d'exemple »).

Comment s'y prendre (quoi demander à l'ITIG et quand, message à envoyer, comptes à créer, commandes) : [`A-FAIRE.md`](../A-FAIRE.md).

**Rien ci-dessous ne bloque le travail** (décision du 2026-09-26). L'ITIG est l'école d'exemple, pas la seule : ce qui manque, Claude l'invente de façon réaliste (dernière section), et chaque école saisit ensuite ses vraies données elle-même. Les documents de l'ITIG remplacent les données fictives quand ils arrivent.

## 1. Maquettes manquantes

30 maquettes ont été fournies. Le 2026-09-26, à la demande de l'utilisateur (T3), Claude a dessiné dans le même système de design les écrans qui manquaient pour la V1.0, plus les bulletins officiels et les cours / maxima (V1.2) : **61 maquettes** au total (`maquettes/index.html`). **Valider** = fusionner la PR des maquettes ; une remarque sur un écran = commentaire de PR, Claude corrige avant de coder l'écran. Pour les lots suivants, même règle : si une maquette n'est pas fournie avant sa tâche, Claude la dessine et la montre avant de coder. **Documents imprimables** (reçus, listes, rapports, bulletins…) : même règle, Claude propose le design dans le système de design, état « à valider » (décision du 2026-09-26).

### V1.0 — nécessaires pour le pilote

| # | Écran | App | Réf. | Tâche | Maquette (dessinée le 2026-09-26) | Validée |
|---|---|---|---|---|---|:-:|
| M1 | Activation de la double authentification : QR code à scanner + 8 codes de secours à imprimer | Gestion | B4 | 1.3 (API), 1.6 (écran) | `gestion/double-authentification-activation` | [ ] |
| M2 | Choix de l'école après connexion (compte dans plusieurs écoles) + changement d'école dans l'en-tête | Gestion | B3 | 1.2 (API `/api/me/`), 1.6 | `gestion/choix-ecole` | [ ] |
| M3 | Personnel : liste des comptes, créer un compte, attribuer des rôles, désactiver, réinitialiser le mot de passe | Gestion | B1–B3 | 1.2 (API ; plus d'« Autres écoles » : `03` § 4), 1.3 (nouveau mot de passe, réinitialiser la double auth., noms et téléphone : seulement pour un compte qui ne sert que dans l'école), 1.7 (écran) | `gestion/personnel-comptes` | [ ] |
| M4 | Mon compte : mot de passe, PIN, double authentification, langue | Gestion | B4–B5, I2 | 1.3 (API), 1.6 (écran), 3.7 (PIN) | `gestion/mon-compte` | [ ] |
| M5 | Paramètres de l'école : nom officiel, logo, couleur, en-tête des reçus, devises, seuils d'alerte ; à compléter pendant la tâche : contraste de la couleur (Q8), format et exemplaires du reçu, logo noir et blanc | Gestion | A1, cahier § 8.1 | 1.5, 1.7, 3.2 | `gestion/parametres-ecole` | [ ] |
| M6 | Journal d'audit : qui a fait quoi, filtres par personne, action, date | Gestion | I1 | 1.4 | `gestion/journal-audit` | [ ] |
| M7 | Menu de la Gestion sur téléphone et tablette (moins de 900 px) | Gestion | cahier § 9.4 | 1.6 | `gestion/menu-mobile` | [ ] |
| M8 | Pages d'état : accès refusé, page introuvable, erreur, école suspendue, session expirée, nouvelle version, stockage local refusé, portail hors connexion | Gestion, Portail | — | 1.6 | `gestion/pages-etat` | [ ] |
| M9 | Fiche élève : onglets Identité, Famille, Historique (+ modification) ; corrigée le 2026-09-26 (Q10 : fiche propre à l'école) | Gestion | D2–D4 | 2.2 | `gestion/eleve-fiche-identite`, `-famille`, `-historique` | [ ] |
| M10 | Fiche famille : code famille, tuteurs, enfants **de l'école**, état du portail, réimprimer / nouveau code ; corrigée le 2026-09-26 (Q10) | Gestion | D4, H1 | 2.2 | `gestion/famille-fiche` | [ ] |
| M11 | Fiche d'inscription imprimable (A4, avec code famille) et liste de classe (PDF, Excel) | Impression | D5 | 2.4 | `gestion/fiche-inscription`, `gestion/liste-classe` | [ ] |
| M12 | Accorder une réduction à un élève ; échéancier particulier | Gestion | E3, E4 | 2.5, 2.6 | `gestion/eleve-reduction`, `gestion/eleve-echeancier` | [ ] |
| M13 | Ouvrir une session de caisse ; caisse avant de choisir un élève ; paiements du jour et recherche d'un reçu à réimprimer | Gestion | F1, F6 | 3.1 | `gestion/caisse-ouverture`, `gestion/caisse-accueil` | [ ] |
| M14 | Crédits d'élèves (surpaiements après synchronisation) à traiter par le comptable | Gestion | — | 3.6 | `gestion/credits-eleves` | [ ] |
| M15 | Reçu d'annulation (80 mm et A4) | Impression | F7 | 3.8 | `gestion/recu-annulation` | [ ] |
| M16 | Clôtures de caisse vues par le comptable : historique, écarts, détail | Gestion | F8 | 3.8 | `gestion/clotures-caisse` | [ ] |
| M17 | Situation financière d'un élève imprimable ; export des impayés (PDF, Excel) | Impression | G1, G2 | 4.1 | `gestion/situation-financiere`, `gestion/impayes-export` | [ ] |
| M18 | Changements de coordonnées faits par les parents, à prendre en compte par le secrétariat | Gestion | H5 | 4.4 | `gestion/changements-coordonnees` | [ ] |
| M19 | Portail : se connecter, mot de passe oublié, installer l'application | Portail | H1, H6 | 4.4 | `portail/connexion`, `portail/mot-de-passe-oublie`, `portail/installer` | [ ] |
| M20 | Guides de première connexion : caissier, comptable, parent | Gestion, Portail | I3 | 4.5 | `gestion/guide-premiere-connexion`, `portail/guide` | [ ] |

### V1.1 — à prévoir avant la semaine 5

Pas encore dessinées (Claude les dessine avant la semaine 5 si elles ne sont pas fournies) : Dépenses et rapports entrées / sorties (5.1) · dossier employé et contrats (5.2) · fiche de paie PDF (5.3) · réglages des notifications et relances (5.4) · carte d'élève PDF (5.5) · pénalités, validation d'inscription, documents téléversés (5.6) · messages à une classe, calendrier, circulaires, convocations (5.8) · espace enseignant (5.9). Existent déjà : paie, pointage QR.

### V1.2 — à prévoir avant la semaine 9

Déjà dessinés le 2026-09-26 d'après les **formulaires officiels** trouvés en ligne : cours et maxima (`gestion/cours-maxima`, 6.1), bulletin des humanités techniques (`gestion/bulletin`, formulaire IGE/P.S/100) et bulletin 7e–8e (`gestion/bulletin-education-de-base`, IGE/P.S/005) — voir `docs/claude/recherches/2026-09-26-bulletins-rdc.md`. Reste à dessiner : attribution des enseignants (6.1) · délibération et palmarès (6.4) · présences RFID et du personnel (6.5) · absences et justification par le parent (6.6) · discipline, messagerie, rendez-vous (6.7) · portail élève et espace titulaire (6.8) · transfert et attestations (6.9) · portail parents complet (6.10) · congés, sondages (6.11). Existent déjà : saisie des notes, scolarité d'un enfant.

### V2

À dessiner tâche par tâche (7.1 à 7.15) au moment de les commencer.

## 2. Informations de l'ITIG

Déposer les fichiers dans `docs/ecole-pilote/depot/` puis `/document-ecole`. Pour une réponse sans fichier : `/noter …`. Aucune de ces informations ne bloque : la colonne « En attendant » dit ce qu'on utilise.

### Pour la V1.0

| # | Information | Tâche | Quand | En attendant | Reçue |
|---|---|---|---|---|:-:|
| I1 | Classes 2026-2027 : sections par niveau (7e A, B, C…), options et sections de la 1re à la 4e | 1.7 | semaine 1 | structure publique + sections inventées | [ ] |
| I2 | Format actuel du matricule | 1.7 | semaine 1 | `ITIG-{AAAA}-{0000}` (maquettes) | [ ] |
| I3 | Calendrier 2026-2027 : périodes, examens, dates ; date de proclamation de la P1 | 1.7, Q6 | semaine 1 | modèle secondaire : 2 semestres, 4 périodes, 2 examens | [ ] |
| I4 | Qui fait quoi : préfet, directeurs des études, directeur de discipline, économe / comptable, caissiers, secrétaires, promoteur ; liste des comptes à créer | 1.2, 4.8 | semaine 1 | un compte fictif par rôle (9 rôles système) ; « qui est le promoteur » : l'utilisateur le demande à l'ITIG | [ ] |
| I5 | Grille des frais 2026-2027 : types, devise de chaque frais, montants par niveau / option, tranches et dates limites, frais mensuels | 2.5 | semaine 2 | grille fictive réaliste, à partir de celle des maquettes (minerval en tranches USD, fonctionnement, atelier, motivation mensuelle en FC) | [ ] |
| I6 | Réductions pratiquées (enfants du personnel, fratrie, bourses) et qui les accorde | 2.5 | semaine 2 | modèles du cahier des charges | [ ] |
| I7 | Liste des élèves en Excel (même partielle, pour voir les colonnes) | 2.3 | semaine 2 | ~800 élèves fictifs avec familles, fratries et paiements sur plusieurs mois | [ ] |
| I8 | Fiche d'inscription et liste de classe actuelles | 2.4 | semaine 2 | maquettes M11 | [ ] |
| I9 | La caisse aujourd'hui : combien de caisses et de caissiers, qui valide une annulation, comment se fait la clôture (le taux est tranché : fixe pour l'année, saisi par le comptable) | 3.1, 3.8 | semaine 3 | 2 caisses, règles des maquettes, taux de l'année 1 $ = 2 850 FC | [ ] |
| I10 | Modèle de reçu actuel (photo) et formulation du montant en lettres | 3.2 | semaine 3 | reçu proposé par Claude ; montant en lettres « Cent cinquante dollars américains et vingt-cinq centimes » (Q5), ajusté quand le reçu arrivera | [ ] |
| I11 | Imprimante thermique (marque, modèle, papier 80 ou 58 mm) ; ordinateurs, tablettes, navigateur ; connexion internet | 4.8 | à la mise en place | tous les formats gérés au choix de l'école (58 mm, 80 mm, A4) ; test sur la vraie imprimante en 4.8 ; Chrome | [ ] |
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
| T1 | **Nom et domaine** (Q9) — **tranché le 2026-09-26 : Mwangaza, `mwangaza.school`** ; reste à vérifier la disponibilité et acheter le domaine avant 4.6 (`A-FAIRE.md` § 9) | maintenant ; domaine acheté avant 4.6 | [x] |
| T2 | Valider les propositions Q1 à Q11 de `06-suivi.md` — **tranché le 2026-09-26** (journal de `06-suivi.md`) | avant 1.2 | [x] |
| T3 | Maquettes : les fournir, ou laisser Claude les dessiner (défaut) — **tranché le 2026-09-26 : Claude dessine** ; reste à valider les maquettes dessinées (PR) | maintenant | [x] |
| T4 | Comptes : VPS, Cloudflare, stockage objet, suivi d'erreurs (Sentry ou GlitchTip) | avant 4.6 | [ ] |
| T5 | Conditions d'utilisation, politique de confidentialité, contrat de traitement des données avec l'ITIG (Claude peut rédiger un brouillon) | avant 4.8 | [ ] |
| T6 | Tarif du pilote ITIG (gratuit pendant l'essai ?) | avant 4.8 | [ ] |

## 4. Données de démonstration

Commande `make demo` (créée avec la tâche 1.1 : pour l'instant les deux écoles ; enrichie à chaque tâche) : elle efface et recrée des données **entièrement fictives et réalistes**, pour le développement et les démonstrations. En production, chaque école saisit ses vraies données. Rien de propre à l'ITIG n'est écrit dans le code : tout passe par les paramètres de l'école de démonstration.

- **École `itig`** « ITIG Don Bosco Goma (démo) » : structure publique réelle (7e–8e EB, 1re–4e, 4 options), couleur `#003C6C`, logo du site web et sa version noir et blanc ; environ **800 élèves** aux noms inventés, avec leurs familles (fratries comprises) ; grille de frais fictive réaliste (frais en USD et en FC) ; taux de l'année 1 $ = 2 850 FC ; 2 caisses ; paiements de septembre à aujourd'hui pour le tableau de bord et les impayés ; un rôle personnalisé « chef d'atelier ».
- **École `volcans`** « Complexe scolaire Les Volcans (fictif) » : petite école (≈ 150 élèves) pour prouver l'isolation entre écoles, avec une famille qui a des enfants dans les deux écoles (deux fiches famille, deux codes, un seul compte parent).
- **Un compte par rôle** (directeur, directeur des études, directeur de discipline, comptable, caissier, secrétaire, promoteur, enseignant, parent, super-admin) avec un mot de passe de développement connu, jamais utilisé en production. Fait en 1.2 : numéros `0000001001` à `0000001010` à l'ITIG (dans l'ordre des rôles de `04` § 8, puis le chef d'atelier), `0000002001`, `…004`, `…005` à Volcans (directeur, comptable, caissière), l'enseignant `0000001008` dans les deux écoles, super-admin `0000000000` ; mot de passe `mwangaza-demo` ; `make demo` affiche la liste. Numéros en +243 0… : jamais ceux de vraies personnes. Depuis la 1.3 : double authentification activée pour les comptes qui l'exigent (directeur, comptable, caissière des deux écoles) avec une même clé de développement affichée par `make demo`, code du moment avec `make totp` ; le promoteur `0000001007` l'active à sa première connexion (pour essayer M1).

# Plan de travail

Chaque tâche est faite dans une branche, avec tests, puis cochée ici. Les références (A1, F5…) renvoient à `02-perimetre-v1.md`.

Pour lancer une tâche dans Claude Code : `/tache 2.3` (ou « Fais la tâche 2.3 du plan de travail. »). Claude relit `CLAUDE.md` et les documents liés.

État actuel, tâche en cours, bloquants et journal de chaque étape : `06-suivi.md` (`/etat` dans Claude Code). Ce qui manque encore (maquettes, informations, décisions) : `07-a-fournir.md`.

Données de démonstration : `make demo` est créée en 1.1 (avancée, prévue en 1.5) et chaque tâche qui ajoute des modèles l'enrichit (données fictives et réalistes ; en production, chaque école saisit ses vraies données).

Sur GitHub, chaque version est un **jalon** (milestone) et chaque tâche une **issue** portant son numéro (ex. « 1.1 — App core… »). La PR d'une tâche ferme son issue (`Closes #n`). Ce fichier reste la référence ; GitHub montre la progression de chaque version.

## Avant de coder (toi, cette semaine)

- [x] ~~Récupérer auprès de l'ITIG les éléments listés au § 11 du cahier des charges (surtout : grille des frais, liste des élèves en Excel, modèle de reçu actuel)~~ — plus un préalable (2026-09-26) : Claude crée des données fictives réalistes ; les documents de l'ITIG servent quand ils arrivent (`07-a-fournir.md` § 2)
- [ ] Choisir le nom définitif, vérifier le domaine, l'acheter — nom et domaine choisis le 2026-09-26 : **Mwangaza**, `mwangaza.school` ; reste à l'acheter (avant 4.6)
- [ ] Créer les comptes : hébergeur VPS, Cloudflare, stockage objet, GitHub (dépôt privé)
- [x] ~~Noter le modèle de l'imprimante thermique de l'ITIG~~ — plus nécessaire (2026-09-26) : formats standards gérés (58 mm, 80 mm, A4), test sur la vraie imprimante en 4.8

## Semaine 1 — Socle

- [x] **0.1** Créer le monorepo selon `03-architecture-technique.md` § 3 ; Docker Compose de développement (postgres, redis, django, front) ; compléter la section « Commandes » de `CLAUDE.md`
- [x] **0.2** Qualité : ruff, pytest, ESLint, Prettier, Vitest, pre-commit, GitHub Actions (lint + tests)
- [x] **1.1** App `core` : `TenantModel`, `TenantManager` qui lève une erreur sans école, `TenantMiddleware` par sous-domaine, UUID v7, classe `Money` + tests
- [x] **1.2** App `accounts` : `User` (téléphone comme identifiant), `Membership`, `Role`, codes de permissions, 9 rôles système copiés à la création d'une école (B1–B3, `04` § 8) ; API des rôles et des comptes du personnel, `GET /api/me/`
- [x] **1.3** Connexion par session, TOTP pour les rôles sensibles, limitation des tentatives (B4) ; API de « Mon compte » (mot de passe, double authentification, langue) et, pour l'école, nouveau mot de passe, réinitialisation de la double authentification, noms et téléphone d'un compte qui ne sert que chez elle
- [x] **1.4** App `audit` : `AuditLog` + utilitaire d'enregistrement (I1) ; API du journal (`/api/audit/`) ; audit des rôles, des comptes du personnel, de Mon compte et de la connexion (1.2, 1.3)
- [x] **1.5** Super-admin : création / suspension d'école, liste des écoles, connexion « en tant qu'école » tracée (A1–A3) ; couleur de l'école choisie dans ses paramètres, contraste vérifié (Q8) ; double authentification du super-admin dans l'administration Django *(ajoutée le 2026-09-26, 1.3)* ; « en tant qu'école » dans le journal d'audit (`impersonated_by`), modifications d'un compte par le support dans l'administration Django (téléphone, noms, mot de passe, désactivation) notées dans le journal de chaque école de la personne *(ajouté le 2026-09-26, 1.4)* ; API des paramètres de l'école (nom, couleur, logo, fuseau, devises)
- [x] **1.6** Front `gestion` : squelette React + Vite + PWA + Tailwind + shadcn/ui + i18next ; écran de connexion ; mise en page avec menu selon permissions ; écrans de la connexion en étapes (code, nouveau mot de passe, activation M1) et « Mon compte » (M4) sur l'API de la 1.3 *(ajoutés le 2026-09-26 : aucune tâche ne prévoyait M4)* ; session support « en tant qu'école » : ouverture avec le motif et bandeau rouge permanent (fin, bouton « Quitter »), lien « Ouvrir en tant qu'école » de l'administration vers cet écran ; nom, couleur et logo de l'école sur l'écran de connexion *(ajoutés le 2026-09-26, 1.5)*
- [x] **1.7** App `schools` : année scolaire depuis modèle, périodes, niveaux, options, classes, format de matricule + écrans (C1–C3) ; écrans « Comptes du personnel » (M3) et « Rôles et permissions » sur l'API de la 1.2 *(ajoutés le 2026-09-26 : aucune tâche ne les prévoyait)* ; écran « Journal d'audit » (M6) sur l'API de la 1.4 *(ajouté le 2026-09-26)* ; écran « Paramètres de l'école » (M5 : identité, logo, couleur, fuseau, devises) sur l'API de la 1.5 *(ajouté le 2026-09-26)*

## Semaine 2 — Élèves et frais

- [x] **2.1** App `students` : `Student`, `Family`, `Guardian`, `Enrollment`, génération du matricule et du code famille ; nombre d'élèves dans la liste des écoles de l'administration (A2) *(ajouté le 2026-09-26, 1.5)* ; matricule donné selon le format de l'école (1.7 : format, rendu, aperçu) avec une séquence par école et par année, « Prochain matricule » réel ; effectifs dans l'écran « Organisation scolaire » (colonne « Effectif / capacité ») ; une classe qui a des élèves ne se supprime plus (protégée par les inscriptions) *(ajoutés le 2026-09-27, 1.7)*
- [ ] **2.2** Écrans élèves (D2–D4), découpée le 2026-09-27 :
   - [x] **2.2.1** Liste des élèves (recherche rapide, filtres année et classe) et « Inscrire un élève » (création, inscription, famille nouvelle ou existante) ; lecture des années et des classes avec `students.view` (filtres de la liste, inscription) *(ajouté le 2026-09-27, 1.7 : ces listes demandent aujourd'hui `classes.manage`)*
   - [ ] **2.2.2** Fiche élève (onglets Identité modifiable avec photo, Famille, Historique ; Finances vide jusqu'à la 2.7) et fiche famille (tuteurs, contacts, enfants, liaison famille) ; ouvrir la fiche depuis la liste et après l'inscription ; recherche `Ctrl K` de l'en-tête ; lien vers la fiche existante quand un doublon est signalé
- [ ] **2.3** Import Excel : téléversement, correspondance des colonnes, aperçu, rapport d'erreurs, import en tâche Celery (D1). Tester avec un fichier fictif réaliste (~800 élèves), puis avec le vrai fichier de l'ITIG quand il arrive
- [ ] **2.4** Impressions : fiche d'inscription avec code famille, liste de classe PDF / Excel (D5) ; export Excel du journal d'audit, limité à la période filtrée, l'export lui-même noté dans le journal (M6) *(ajouté le 2026-09-26, 1.4 : même bibliothèque Excel)*
- [ ] **2.5** App `finance` — configuration : `FeeType`, `FeeRule`, `InstallmentTemplate`, `ExchangeRate`, `Discount` + écrans (E1–E3, E5) ; devise au choix pour chaque barème ; taux de l'année corrigeable avec historique ; une devise utilisée par un frais ou un paiement ne peut plus être retirée des devises de l'école (M5) *(ajouté le 2026-09-26, 1.5)* ; nouvelle année créée en reprenant aussi les barèmes d'une autre (C1 : les classes sont reprises depuis la 1.7) *(ajouté le 2026-09-27)*
- [ ] **2.6** Génération des `StudentCharge` à l'inscription et quand un barème change ; échéancier particulier (E4)
- [ ] **2.7** Calcul du solde et des retards d'un élève (service + tests couvrant réductions, devises, annulations)

## Semaine 3 — Caisse et hors-ligne

- [ ] **3.1** Caisses et sessions de caisse ; `Payment`, `PaymentAllocation`, répartition automatique + ajustement (F1–F2), en ligne d'abord
- [ ] **3.2** Reçu dans le navigateur au format choisi par l'école (thermique 58 / 80 mm ; A6, A5 ou petit format sur A4 avec traits de découpe ; 1 ou 2 exemplaires), montant en lettres (français), zone signature / cachet, QR code signé ; page publique de vérification `/v/{id}` (F3–F4, F6) ; design des reçus proposé par Claude ; carte « Reçus et documents » des paramètres de l'école (M5 : imprimante et format, exemplaires, lignes d'en-tête avec adresse, téléphone et e-mail, mention, logo noir et blanc) *(ajoutée le 2026-09-27, 1.7)*
- [ ] **3.3** App `sync` : `Device`, enregistrement d'appareil avec préfixe et clé de signature des reçus, `SyncOperation`, `ChangeLog`, endpoints `snapshot`, `pull`, `push` idempotents ; `AuditLog.device` et heure de l'appareil pour les actions faites hors ligne (M6) *(ajouté le 2026-09-26, 1.4)* ; case « Se souvenir de cet appareil » de l'écran de connexion et « Appareils connectés » de Mon compte (M4) *(reportés de la 1.6)*
- [ ] **3.4** Front : base Dexie, instantané initial, file d'opérations, synchronisation automatique, indicateur d'état, stockage persistant ; indicateur complet (opérations en attente, dernière synchronisation : la 1.6 ne montre qu'en ligne / hors ligne) ; nouvelle version installée seulement file vide (M8) *(précisé en 1.6)*
- [ ] **3.5** Caisse hors-ligne complète : recherche élève, solde, encaissement, reçu, numérotation locale (F5). Tests Playwright : couper le réseau, encaisser, reconnecter, vérifier aucun doublon
- [ ] **3.6** Crédit élève en cas de surpaiement après synchronisation
- [ ] **3.7** PIN de déverrouillage hors-ligne, expiration à 7 jours, révocation d'appareil (B5) ; carte « Code PIN » de Mon compte (M4) *(reportée de la 1.6)*
- [ ] **3.8** Annulation avec demande / validation (F7) ; clôture de caisse (F8)

## Semaine 4 — Rapports, portail parents, mise en production

- [ ] **4.1** Impayés : liste filtrable, export ; situation financière imprimable (G1–G2)
- [ ] **4.2** Tableau de bord directeur (G3) ; seuils d'alerte de l'école (M5 : écart de caisse, annulations par caissier et par jour, caisse non clôturée) *(ajouté le 2026-09-26, 1.5)*
- [ ] **4.3** Annonces côté école (H4)
- [ ] **4.4** Front `portail` : activation par téléphone + code famille, liste des enfants multi-écoles, paiements, reçus PDF, échéances, annonces, mise à jour des coordonnées, installable (H1–H6) ; école suspendue : « service temporairement indisponible » (A1) *(ajouté le 2026-09-26, 1.5)*
- [ ] **4.5** Guides de première connexion : caissier, comptable, parent (I3) ; traduction anglaise (I2) ; traduction française des textes du serveur (administration Django, messages) *(ajoutée le 2026-09-26, 1.5)*
- [ ] **4.6** Infra de production : VPS, Caddy, wildcard Cloudflare, variables d'environnement, déploiement en une commande ; adresse IP réelle du visiteur transmise par Caddy et Cloudflare (limitation des tentatives, 1.3)
- [ ] **4.7** Sauvegardes continues + dump quotidien + **test de restauration** (I4) ; suivi d'erreurs ; sonde de disponibilité
- [ ] **4.8** Mise en place à l'ITIG : l'école saisit ou importe ses vraies données (élèves, frais, comptes) avec notre aide, formation des caissiers, test sur la vraie imprimante

## Semaines 5 à 8 — V1.1

- [ ] **5.1** Dépenses par catégorie, rapports entrées / sorties
- [ ] **5.2** RH : dossier employé, contrats, qualifications, statut SECOPE
- [ ] **5.3** Paie : périodes, lignes, primes, motivation enseignants liée aux frais, avances, retenues, fiche de paie PDF
- [ ] **5.4** Notifications push (paiement reçu, échéance proche, annonce) ; relances automatiques d'impayés
- [ ] **5.5** Cartes d'élève PDF avec photo et QR ; pointage d'entrée par scan QR sur tablette, hors-ligne
- [ ] **5.6** Pénalités de retard, validation d'inscription liée au paiement, documents téléversés
- [ ] **5.7** Connexion Google, champs complémentaires de la fiche élève
- [ ] **5.8** Communication : messages à une classe, calendrier des événements, circulaires PDF, convocations ; portail : calendrier, titulaire et enseignants avec contacts *(ajoutée le 2026-09-25 — cahier § 8.9, 8.10)*
- [ ] **5.9** Espace enseignant : fiche de paie et horaire ; jeton de carte RFID / NFC de l'élève, révocable *(ajoutée le 2026-09-25 — cahier § 8.3, 8.5, 8.12)*

## Semaines 9 à 14 — V1.2 (bulletins avec Mwangaza à partir de la P2 / 1er semestre — décision Q6)

- [ ] **6.1** Cours, maxima, domaines, attribution enseignants
- [ ] **6.2** Saisie des notes (y compris hors-ligne), verrouillage, validation, historique
- [ ] **6.3** Bulletin EPST PDF avec QR d'authenticité, calcul des totaux, places, mentions ; deux modes d'impression : bulletin complet, ou notes seules sur le formulaire pré-imprimé (Q11) ; régime et code de l'école (EPST, 7 chiffres) dans les paramètres de l'école (M5) *(ajouté le 2026-09-27, 1.7)*
- [ ] **6.4** Délibération, décisions, palmarès, passage de classe
- [ ] **6.5** Lecteurs RFID ESP32 (dossier `firmware/`) et API de pointage ; présences du personnel
- [ ] **6.6** Notifications d'absence et de retard, justification par le parent
- [ ] **6.7** Discipline ; messagerie parent ↔ titulaire / administration ; rendez-vous
- [ ] **6.8** Portail élèves ; espace enseignant et titulaire
- [ ] **6.9** Transfert d'élève entre écoles de la plateforme (copie du dossier vers l'école d'arrivée) ; attestations et certificats
- [ ] **6.10** Portail parents V1.2 : présences en direct, notes, bulletins PDF, discipline, documents ; tableau de bord : taux de présence et résultats scolaires *(ajoutée le 2026-09-25 — cahier § 8.10, 8.13)*
- [ ] **6.11** Congés et permissions du personnel ; sondages ; option de blocage des bulletins / examens en cas de dette (désactivée par défaut) *(ajoutée le 2026-09-25 — cahier § 8.4, 8.5, 8.9)*

## V2 — après la V1.2 (proposition : ordre et découpage à valider avant de commencer)

Chaque tâche V2 sera redécoupée en sous-tâches (7.1.1, 7.1.2…) au moment de la commencer.

- [ ] **7.1** Réseau : tableau consolidé promoteur / coordination confessionnelle, comparaison entre années (cahier § 6.1, 8.13)
- [ ] **7.2** Plateforme : abonnements et facturation des écoles (tarif par élève, offres Découverte / Standard / Réseau, essai), revendeurs, annonces à toutes les écoles, statistiques globales (§ 5, 6.1) ; écran dédié du super-admin (maquette `superadmin-ecoles` : cartes, liste, abonnements), en V1.0 l'administration Django *(ajouté le 2026-09-26, 1.5)*
- [ ] **7.3** Paiement en ligne Mobile Money via agrégateur, argent versé directement sur le compte de l'école (§ 5, 8.14)
- [ ] **7.4** SMS et WhatsApp avec crédits achetés par l'école ; relances d'impayés par SMS (§ 8.4, 8.9)
- [ ] **7.5** Applications Android et iPhone (Capacitor) publiées dans les stores (§ 8.10)
- [ ] **7.6** Pré-inscription en ligne, test d'admission, liste d'attente (§ 8.3)
- [ ] **7.7** Comptabilité SYSCOHADA complète : journal, grand livre, budget prévisionnel, rapprochement bancaire (§ 8.4)
- [ ] **7.8** Emploi du temps automatique sans conflit ; devoirs et cours publiés (enseignant, élève, parent) (§ 8.6, 8.10–8.12)
- [ ] **7.9** Évaluations d'atelier (écoles techniques) ; évaluation des enseignants (§ 8.5, 8.6)
- [ ] **7.10** Rapports officiels EPST : statistiques de fin d'année, listes ENAFEP / Exetat, palmarès officiel (§ 8.13)
- [ ] **7.11** Enseignement supérieur LMD : semestres, unités d'enseignement, crédits, sessions (§ 7)
- [ ] **7.12** Vie scolaire : bibliothèque, cantine (menu dans le portail), transport (itinéraires, suivi GPS), internat (§ 8.10, 8.14)
- [ ] **7.13** Gestion matérielle : inventaire, ateliers (équipements, matières d'œuvre, TP), boutique (uniformes, fournitures) (§ 8.14)
- [ ] **7.14** Orientation scolaire, anciens élèves, site vitrine généré pour chaque école (`{ecole}.mwangaza.school/`) (§ 8.14, architecture § 2)
- [ ] **7.15** Sécurité en profondeur : Row Level Security PostgreSQL (architecture § 4)

## Plus tard (non planifié)

Migration depuis d'autres logiciels ; rapports transmis aux sous-divisions EPST ; maternelle ; intelligence artificielle (non prévue au départ).

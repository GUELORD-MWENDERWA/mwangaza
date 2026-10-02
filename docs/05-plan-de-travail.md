# Plan de travail

Chaque tâche est faite dans une branche, avec tests, puis cochée ici. Les références (A1, F5…) renvoient à `02-perimetre-v1.md`.

Pour lancer une tâche dans Claude Code : `/tache 2.3` (ou « Fais la tâche 2.3 du plan de travail. »). Claude relit `CLAUDE.md` et les documents liés.

État actuel, tâche en cours, bloquants et journal de chaque étape : `06-suivi.md` (`/etat` dans Claude Code). Ce qui manque encore (maquettes, informations, décisions) : `07-a-fournir.md`.

Données de démonstration : `make demo` est créée en 1.1 (avancée, prévue en 1.5) et chaque tâche qui ajoute des modèles l'enrichit (données fictives et réalistes ; en production, chaque école saisit ses vraies données).

Sur GitHub, chaque version est un **jalon** (milestone) et chaque tâche une **issue** portant son numéro (ex. « 1.1 — App core… »). La PR d'une tâche ferme son issue (`Closes #n`). Ce fichier reste la référence ; GitHub montre la progression de chaque version.

## Avant de coder (toi, cette semaine)

- [x] ~~Récupérer auprès de l'ITIG les éléments listés au § 11 du cahier des charges (surtout : grille des frais, liste des élèves en Excel, modèle de reçu actuel)~~ — plus un préalable (2026-09-26) : Claude crée des données fictives réalistes ; les documents de l'ITIG servent quand ils arrivent (`07-a-fournir.md` § 2)
- [ ] Choisir le nom définitif, vérifier le domaine, l'acheter — nom et domaine choisis le 2026-09-26 : **Mwangaza**, `mwangaza.school` ; à acheter **quand tu décides la mise en ligne** (4.6.2) ; ne bloque pas le développement (2026-10-02)
- [ ] Créer les comptes : hébergeur, stockage objet (GitHub : fait) — avec la mise en ligne (4.6.2, 4.7)
- [x] ~~Noter le modèle de l'imprimante thermique de l'ITIG~~ — plus nécessaire (2026-09-26) : formats standards gérés (58 mm, 80 mm, A4)

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
- [x] **2.2** Écrans élèves (D2–D4), découpée le 2026-09-27 :
   - [x] **2.2.1** Liste des élèves (recherche rapide, filtres année et classe) et « Inscrire un élève » (création, inscription, famille nouvelle ou existante) ; lecture des années et des classes avec `students.view` (filtres de la liste, inscription) *(ajouté le 2026-09-27, 1.7 : ces listes demandent aujourd'hui `classes.manage`)*
   - [x] **2.2.2** Fiche élève (onglets Identité modifiable avec photo, Famille, Historique ; Finances vide jusqu'à la 2.7) et fiche famille (tuteurs, contacts, enfants, liaison famille) ; ouvrir la fiche depuis la liste et après l'inscription ; recherche `Ctrl K` de l'en-tête ; lien vers la fiche existante quand un doublon est signalé
- [x] **2.3** Import Excel : téléversement, correspondance des colonnes, aperçu, rapport d'erreurs, import en tâche Celery (D1). Tester avec un fichier fictif réaliste (~800 élèves), puis avec le vrai fichier de l'ITIG quand il arrive
- [x] **2.4** Impressions : fiche d'inscription avec code famille, liste de classe PDF / Excel (D5) ; export Excel du journal d'audit, limité à la période filtrée, l'export lui-même noté dans le journal (M6) *(ajouté le 2026-09-26, 1.4 : même bibliothèque Excel)* ; sélection de plusieurs élèves dans la liste pour la même impression : pas planifiée, à ajouter si une école la demande
- [x] **2.5** App `finance` — configuration, découpée le 2026-09-27 :
   - [x] **2.5.1** `FeeType`, `FeeRule`, `InstallmentTemplate`, `ExchangeRate` + écran « Frais et barèmes » (E1, E2, E5) ; devise au choix pour chaque barème ; taux de l'année corrigeable avec historique ; une devise utilisée par un frais ou un paiement ne peut plus être retirée des devises de l'école (M5) *(ajouté le 2026-09-26, 1.5)* ; nouvelle année créée en reprenant aussi les barèmes d'une autre (C1 : les classes sont reprises depuis la 1.7) *(ajouté le 2026-09-27)*
   - [x] **2.5.2** `Discount` + écran « Accorder une réduction » depuis la fiche élève (E3), avec l'effet sur ce que doit l'élève — **à faire juste après la 2.6** (a besoin des `StudentCharge`)
- [x] **2.6** Frais dus des élèves, découpée le 2026-09-27 :
   - [x] **2.6.1** Génération des `StudentCharge` à l'inscription (import compris) et quand un barème change ; sur la fiche élève : changer de classe (frais recalculés, sauf ceux déjà payés), enregistrer un départ (abandon, transfert, exclusion, avec date), inscrire pour l'année un élève déjà connu *(ajouté le 2026-09-27, 2.2.2 : service et API faits en 2.1)*
   - [x] **2.6.2** Échéancier particulier (E4) : service, API et écran (maquette `eleve-echeancier`) ; puis la 2.5.2
- [x] **2.7** Calcul du solde et des retards d'un élève (service + tests couvrant réductions, devises, annulations) ; frais de l'année (après réductions, par devise) sur la fiche d'inscription et colonne « situation des paiements » de la liste de classe, avec `finance.view_reports` *(ajouté le 2026-09-27, 2.4)*

## Semaine 3 — Caisse et hors-ligne

- [x] **3.1** Caisses et paiements en ligne, découpée le 2026-09-28 :
   - [x] **3.1.1** Serveur : `CashRegister`, `CashSession`, `Payment`, `PaymentAllocation` ; ouverture de session (une par caisse, une par caissier) ; encaissement avec répartition automatique + ajustement, conversion au taux de l'année, numéro de reçu donné par le serveur avec le code de la caisse en attendant les appareils (3.3) (F1–F2) ; solde : allocations des paiements non annulés dans `finance.services._settle` (payé, situation « partielle »), avec un test d'annulation *(ajouté le 2026-09-28, 2.7)* ; `finance.services.sync_charges` laisse intacts les frais dus déjà payés, même en partie (changement de classe, barème modifié) *(ajouté le 2026-09-27, 2.6.1)* ; `reschedule_charges` et l'écran « Échéancier particulier » ne proposent que les échéances pas encore payées, même en partie *(ajouté le 2026-09-28, 2.6.2)* ; démo : caisses et paiements sur plusieurs mois
   - [x] **3.1.2** Écrans de caisse en ligne : ouverture de session (`caisse-ouverture`), accueil avec paiements du jour et recherche (`caisse-accueil`, réimpression en 3.2), encaissement (`caisse-encaissement`) ; carte « Caisses » des paramètres de l'école (nom, code, active) *(décidé le 2026-09-28 : pas de maquette)*
- [x] **3.2** Reçus, découpée le 2026-09-28 :
   - [x] **3.2.1** Paramètres des reçus : `School.settings.receipt` (imprimante thermique 58 / 80 mm ou feuille A4 avec reçus A6, A5 ou petit format ; 1 ou 2 exemplaires ; lignes d'en-tête avec adresse, téléphone et e-mail ; mention) et logo noir et blanc (`logo_monochrome`) ; carte « Reçus et documents » des paramètres de l'école (M5) *(ajoutée le 2026-09-27, 1.7)*
   - [x] **3.2.2** Reçu dans le navigateur au format choisi par l'école (thermique 58 / 80 mm ; A6, A5 ou petit format sur A4 avec traits de découpe ; 1 ou 2 exemplaires), montant en lettres (français), zone signature / cachet, QR code vers `/v/{id}` (bibliothèque `uqr`, acceptée le 2026-09-28 ; signature par l'appareil : 3.3) ; design des reçus proposé par Claude ; « Encaisser et imprimer » et « Réimprimer » (DUPLICATA, audit) (F3, F6) ; bouton « Test » de l'imprimante
   - [x] **3.2.3** Page publique de vérification `/v/{id}` (F4, maquette `portail/verification-recu`) ; QR code du portail sur la fiche d'inscription *(ajouté le 2026-09-27, 2.4)*
- [x] **3.3** App `sync`, découpée le 2026-09-28 :
   - [x] **3.3.1** Appareils : `Device` (préfixe, clé publique de signature des reçus, caisse, révocation), case « Se souvenir de cet appareil » de l'écran de connexion et « Appareils connectés » de Mon compte (M4) *(reportés de la 1.6)* ; `AuditLog.device` et heure de l'appareil pour les actions faites hors ligne (M6) *(ajouté le 2026-09-26, 1.4)*
   - [x] **3.3.2** Synchronisation serveur : `SyncOperation`, `ChangeLog`, endpoints `snapshot`, `pull`, `push` idempotents ; appareil révoqué refusé
- [x] **3.4** Front : base Dexie, instantané initial, file d'opérations, synchronisation automatique, indicateur d'état, stockage persistant ; indicateur complet (opérations en attente, dernière synchronisation : la 1.6 ne montre qu'en ligne / hors ligne) ; nouvelle version installée seulement file vide (M8) *(précisé en 1.6)*
- [x] **3.5** Caisse hors-ligne complète, découpée le 2026-09-29 :
   - [x] **3.5.1** Encaisser hors ligne : recherche élève, solde et frais dus lus sur l'appareil avec les paiements en attente, encaissement par la file d'opérations avec numérotation locale (F5) — **toujours par la file sur un appareil mémorisé**, avec ou sans réseau *(décidé le 2026-09-29)* —, reçu imprimé sans serveur, paiements de la session « en attente » / « refusé » ; page bloquante « stockage refusé » (M8) sur la caisse *(ajoutée le 2026-09-29, 3.4)*. Tests Playwright : couper le réseau, encaisser deux fois, reconnecter, vérifier aucun doublon
   - [x] **3.5.2** Ouverture de caisse et réimpression hors ligne (opérations de synchronisation, maquettes `caisse-ouverture` et `caisse-accueil`) ; QR code du reçu signé par l'appareil et vérification de la signature sur `/v/…` (F4) *(déplacé de la 3.3 le 2026-09-28)*
- [x] **3.6** Crédit élève, découpée le 2026-09-29 :
   - [x] **3.6.1** Crédit côté serveur : surplus d'un paiement hors ligne arrivé après un autre (3.3.2), réduction sur une échéance déjà payée (M14) ; retrait de la réduction → crédit annulé ; utilisation par le comptable sur les échéances les plus anciennes, sans nouveau paiement (justificatif imprimable) *(décidé le 2026-09-29)* ; écran « Crédits d'élèves » (maquette `credits-eleves`) ; colonnes « Déjà payé » / « Effet » du dialogue « Accorder une réduction » *(ajouté le 2026-09-28, 2.5.2)*
   - [x] **3.6.2** Crédit proposé et utilisé à la caisse au prochain paiement de l'élève, en ligne et hors ligne (crédit sur l'appareil, opération de synchronisation) ; crédit à traiter visible sur la fiche élève (Finances) *(ajouté le 2026-09-29, 3.6.1)*
- [x] **3.7** PIN hors-ligne et appareils (B5), découpée le 2026-09-29 :
   - [x] **3.7.1** PIN de déverrouillage : carte « Code PIN » de Mon compte (M4) *(reportée de la 1.6)*, empreinte PBKDF2 gardée sur l'appareil ; démarrage sans réseau (`/api/me/` indisponible) sur l'écran de déverrouillage (maquette `deverrouillage-pin`) ; 5 PIN faux ou dernière connexion complète il y a plus de 7 jours → connexion complète exigée. Test Playwright : démarrer sans réseau, déverrouiller, encaisser
   - [x] **3.7.2** Appareils de l'école : liste et révocation par un responsable (`roles.manage`) ; écran « Appareils et synchro » (maquette `appareils-synchro` : appareils de l'école, révocation, carte « Cet appareil » avec la file d'attente) ; données locales effacées à la révocation *(ajoutés le 2026-09-29, 3.4)*
- [x] **3.8** Annulation et clôture de caisse, découpée le 2026-09-29 :
   - [x] **3.8.1** Annulation d'un paiement (F7) : demande avec motif, en ligne et hors ligne (opération `cancellation.request`, maquette `demande-annulation` faite par Claude) ; validation ou refus par un autre compte (`finance.approve_cancellation`), écran « Annulations » (maquette `annulations`) ; reçu d'annulation dans une série propre (maquette `recu-annulation`, M15) ; annulation d'un paiement qui a donné un crédit (surplus hors ligne, ou tranche payée puis réduite) : annuler aussi ce crédit *(ajouté le 2026-09-29, 3.6.1)* ; appareil : garder la date d'annulation des paiements pour un duplicata exact *(ajouté le 2026-09-29, 3.5.2)*
   - [x] **3.8.2** Clôture de caisse par le caissier (F8, maquette `caisse-cloture`) : `CashClosing` par devise, en ligne et hors ligne (opération `cash_session.close`), bordereau imprimé ; un paiement hors ligne d'une session déjà close est refusé (`no_open_session`) : décider quoi en faire *(ajouté le 2026-09-29, 3.3.2)* ; de même pour une ouverture de caisse hors ligne refusée (caisse prise entre-temps) et ses encaissements *(découpée le 2026-09-30)*
   - [x] **3.8.3** Clôtures de caisse vues par le comptable (M16, maquette `clotures-caisse`) : liste, écarts, sessions non clôturées, paiements arrivés après la clôture, détail, bordereau, Excel (l'alerte au directeur au-delà du seuil : 4.2) ; duplicata fait sur l'appareil : compter aussi les crédits utilisés avant le paiement (l'appareil ne reçoit que les crédits à traiter) *(ajouté le 2026-09-29, 3.6.2)*

## Semaine 4 — Rapports, portail parents, mise en production

- [x] **4.1** Impayés et situation financière, découpée le 2026-09-30 :
   - [x] **4.1.1** Impayés (G1, maquettes `impayes` et `impayes-export`) : liste filtrable (classe, frais, tranche, retard, devise), chiffres clés, export Excel (une ligne par frais en retard) et PDF par classe, exports tracés
   - [x] **4.1.2** Situation financière imprimable (G2, maquette `situation-financiere`) depuis la fiche élève et groupée depuis les Impayés (sélection) ; colonnes « Échu non payé » et « Paiements » et filtre « Paiement » de la liste des élèves (maquette `eleves-liste`) *(ajouté le 2026-09-28, 2.7)*
- [x] **4.2** Tableau de bord directeur (G3) ; seuils d'alerte de l'école (M5 : écart de caisse, annulations par caissier et par jour, caisse non clôturée) *(ajouté le 2026-09-26, 1.5)*
- [x] **4.3** Annonces côté école (H4)
- [x] **4.4** Front `portail` : activation par téléphone + code famille, liste des enfants multi-écoles, paiements, reçus PDF, échéances, annonces, mise à jour des coordonnées, installable (H1–H6) ; école suspendue : « service temporairement indisponible » (A1) *(ajouté le 2026-09-26, 1.5)* ; annonce marquée lue par la famille et « lue par N familles » dans la liste des annonces de la Gestion *(ajouté le 2026-10-01, 4.3)*, découpée le 2026-10-02 :
   - [x] **4.4.1** Accès au portail (H1, A1, M19) : app `portal`, activation par téléphone + code famille + mot de passe, connexion, mot de passe oublié (nouveau code à usage unique depuis la fiche famille, « Nouveau code »), école suspendue ; coquille du Portail (en-tête, i18n, client API)
   - [x] **4.4.2** Enfants et installable (H2, H6) : accueil multi-écoles (une carte par enfant, situation des paiements résumée), « Ajouter un enfant d'une autre école » ; « Suspendre l'accès » de la fiche famille, affiché sur la carte ; installable (PWA, écran « Installer », bandeau de l'accueil) *(découpée le 2026-10-02)*
   - [x] **4.4.3** Paiements et reçus (H3) : paiements d'un enfant (payé, reste, en retard, échéances, détail des frais), photo (si consentement), reçus PDF ; barre de navigation du Portail
   - [x] **4.4.4** Annonces (H4) : annonces des écoles reliées, pièce jointe, marquée lue ; « lue par N familles » dans la Gestion
   - [x] **4.4.5** Coordonnées (H5, M18) : profil du portail ; écran « Demandes des parents » de la Gestion
- [x] **4.5** Guides de première connexion : caissier, comptable, parent (I3) ; traduction anglaise (I2) ; traduction française des textes du serveur (administration Django, messages) *(ajoutée le 2026-09-26, 1.5)*, découpée le 2026-10-02 :
   - [x] **4.5.1** Guides de première connexion (I3, M20) : caissier et comptable dans la Gestion (étapes sur les vrais écrans, reprise, « Passer le guide », « Aide et guide ») ; parent dans le Portail (après l'activation, « Revoir le guide » du profil)
   - [x] **4.5.2** Traductions (I2) : textes du serveur en français (administration Django, messages, PDF, Excel) ; relecture de la traduction anglaise des deux applications
- [ ] **4.6** Infra de production : VPS, Caddy, wildcard Cloudflare, variables d'environnement, déploiement en une commande ; adresse IP réelle du visiteur transmise par Caddy et Cloudflare (limitation des tentatives, 1.3) ; Caddy envoie `/v/*` de l'adresse de l'école à Django (vérification d'un reçu) *(ajouté le 2026-09-28, 3.2.3)*, découpée le 2026-10-02 (domaine, Cloudflare et VPS pas encore achetés) :
   - [x] **4.6.1** Production prête, essayée sur la machine : images Docker (front construit, Django + gunicorn, Caddy), `infra/docker-compose.yml`, Caddyfile (sous-domaines, `/v/*`, compression, cache des PWA), variables d'environnement, adresse IP réelle du visiteur ; `make prod-local`
   - [ ] **4.6.2** Mise en ligne, **quand tu le décides** (ne bloque pas la suite) : démonstration gratuite possible (Oracle Cloud « Always Free » + adresse DuckDNS, certificats Let's Encrypt demandés seulement pour une école qui existe, données fictives avec des mots de passe propres au serveur) ou VPS + `mwangaza.school` + Cloudflare (certificat d'origine, pare-feu limité à Cloudflare) ; serveur préparé (mises à jour, SSH par clé), `make deploy` en une commande, premier super-admin. **Vraies données d'une école seulement avec le vrai domaine et les sauvegardes (4.7)** : changer d'adresse ensuite obligerait à réinstaller les applications et rendrait invérifiables les QR des reçus imprimés
- [ ] **4.7** Sauvegardes continues + dump quotidien + **test de restauration** (I4) ; suivi d'erreurs ; sonde de disponibilité — avec la mise en ligne
- [x] ~~**4.8** Mise en place à l'ITIG~~ — retirée le 2026-10-02 : on n'attend rien de l'ITIG ; comme toute école, elle saisit ou importe elle-même ses données (import Excel, écrans de la V1.0), quand elle veut
- [x] **4.9** Invitation des familles au portail (H7) : lettre PDF par famille (adresse du portail avec QR, code famille, 3 étapes, aide), imprimable pour une classe ou depuis la fiche famille ; message prêt à partager (WhatsApp, SMS) ; suivi des comptes activés par classe (« pas encore activé ») ; code remis noté au journal *(ajoutée le 2026-10-02)*
- [ ] **4.10** Guide de la V1.0 en PDF (I5) : ce que fait la version et comment, rôle par rôle (directeur, promoteur, comptable, caissier, secrétaire, directeur des études et de discipline, enseignant, parent, super-admin), avec captures des écrans sur les données de démonstration ; ce qu'elle ne fait pas encore et ce qu'apportent les versions suivantes ; dans le système de design, régénéré à chaque version (`make guide`) *(ajoutée le 2026-10-02)*

Découpage revu le 2026-10-02 (demande de l'utilisateur) : la V1.0 est mise de côté une fois 4.9 et 4.10 faites (la mise en ligne vient quand tu le décides), puis V1.1 → V1.4 dans l'ordre. Plus de semaines : le rythme réel (la V1.0 en une semaine) les rendait trompeuses. Chaque tâche trop grosse est redécoupée (X.Y.1, X.Y.2…) au moment de la commencer.

## V1.1 — Plateforme, notifications et communication

- [ ] **5.1** Identité de la plateforme : nom, nom court, logo, icône des applications, couleurs, contact du support, mentions légales, dans les paramètres de la plateforme (plus rien d'écrit en dur : changer le nom ou le logo ne demande pas de code) ; lue par la Gestion, le Portail, la console, les PDF, l'administration et les manifestes des applications (servis par le serveur) ; test qui refuse le nom de la plateforme écrit en dur dans les textes
- [ ] **5.2** Console de la plateforme — socle : troisième application (`frontend/apps/console`, `admin.<domaine>`) avec son propre design ; connexion du super-admin (mot de passe + double authentification) ; tableau de bord (écoles, élèves, encaissements du jour, santé du serveur) ; écran « Identité de la plateforme » (5.1) ; l'administration Django ne sert plus qu'au dépannage
- [ ] **5.3** Console — écoles (maquette `superadmin-ecoles`) : cartes et liste, créer une école avec son directeur, paramètres, suspendre / réactiver, abonnement (offre, essai, échéance ; sans facturation), « Ouvrir en tant qu'école » (session support)
- [ ] **5.4** Console — comptes, appareils et journal : chercher un compte dans toutes les écoles, réinitialiser son mot de passe ou sa double authentification, sessions support, appareils enregistrés, journal de la plateforme ; annonces de la plateforme aux écoles
- [ ] **5.5** Notifications sur l'écran — socle : notifications système (Web Push) qui s'affichent même application fermée, sur Android, ordinateur et iPhone (application installée sur l'écran d'accueil) ; abonnement de chaque appareil, préférences par compte, centre de notifications dans la Gestion et le Portail ; envoi par Celery
- [ ] **5.6** Notifications — événements : parent (paiement reçu avec son reçu, annonce, échéance proche, retard de paiement), personnel (annonce, alertes du directeur : écart de caisse, annulations, caisse non clôturée) ; relances automatiques d'impayés réglées par l'école
- [ ] **5.7** Communication : annonces au personnel (destinataire « Personnel » de 4.3, écran où le personnel les lit), messages à une classe, calendrier des événements, circulaires PDF, convocations ; portail : calendrier, titulaire et enseignants avec contacts (cahier § 8.9, 8.10)

## V1.2 — Carte unique et présences

Une seule carte par élève et par membre du personnel : **puce sans contact (NFC) + QR code + photo et informations**. Pointage de deux façons : la puce (téléphone Android enregistré ou lecteur ESP32) ou le QR (caméra de n'importe quel téléphone ou tablette enregistrés, iPhone compris).

- [ ] **6.1** Carte de l'élève et du personnel : modèle de carte réglé par l'école (couleurs, champs, recto / verso) ; PDF au format carte bancaire (imprimante à cartes) et planche A4 ; jeton secret dans la puce et le QR (pas le matricule), révocable ; carte perdue remplacée, l'ancienne refusée partout ; cartes conseillées : NTAG215 / 216 (lues par tous les téléphones NFC et par l'ESP32)
- [ ] **6.2** Liaison des cartes : poste d'encodage sur un appareil enregistré (téléphone Android avec NFC, ou lecteur ESP32 en mode encodage) ; classe par classe, scanner le QR imprimé puis poser la carte : la puce reçoit le jeton, est liée à la personne et protégée en écriture, en une seconde ; carte déjà liée, doublon ou carte d'une autre école refusés ; suivi « à lier / liées »
- [ ] **6.3** Pointage par téléphone ou tablette enregistrés : mode borne plein écran, puce (Android) et / ou caméra QR (tout appareil) ; entrée / sortie, retard selon l'horaire de l'école ; photo affichée pour contrôle ; hors ligne (file d'opérations, idempotent)
- [ ] **6.4** Lecteurs ESP32 (`firmware/`) : PN532 + écran + buzzer, enregistrés comme appareils de l'école, pointages gardés en mémoire si le réseau coupe, API de pointage idempotente ; guide de montage
- [ ] **6.5** Suivi des présences : listes du jour par classe, absents, retards, correction manuelle (journal), présences du personnel ; rapports et export ; tableau de bord : taux de présence
- [ ] **6.6** Présences et parents : notification d'arrivée, d'absence et de retard (5.5), justification par le parent dans le Portail, présences en direct dans le Portail ; alerte après X absences

## V1.3 — Personnel, paie et dépenses

- [ ] **7.1** Dépenses par catégorie, rapports entrées / sorties
- [ ] **7.2** RH : dossier employé, contrats, qualifications, statut SECOPE ; carte du personnel sans compte (6.1)
- [ ] **7.3** Paie : périodes, lignes, primes, motivation enseignants liée aux frais, avances, retenues (absences pointées, en option), fiche de paie PDF
- [ ] **7.4** Espace enseignant : fiche de paie et horaire ; congés et permissions du personnel (cahier § 8.5, 8.12)
- [ ] **7.5** Pénalités de retard, validation d'inscription liée au paiement, documents téléversés
- [ ] **7.6** Connexion Google, champs complémentaires de la fiche élève

## V1.4 — Notes, bulletins et vie scolaire

- [ ] **8.1** Cours, maxima, domaines, attribution enseignants
- [ ] **8.2** Saisie des notes (y compris hors-ligne), verrouillage, validation, historique
- [ ] **8.3** Bulletin EPST PDF avec QR d'authenticité, calcul des totaux, places, mentions ; deux modes d'impression : bulletin complet, ou notes seules sur le formulaire pré-imprimé (Q11) ; régime et code de l'école (EPST, 7 chiffres) dans les paramètres de l'école (M5) *(ajouté le 2026-09-27, 1.7)*
- [ ] **8.4** Délibération, décisions, palmarès, passage de classe
- [ ] **8.5** Discipline ; messagerie parent ↔ titulaire / administration ; rendez-vous
- [ ] **8.6** Portail élèves ; espace enseignant et titulaire
- [ ] **8.7** Transfert d'élève entre écoles de la plateforme (copie du dossier vers l'école d'arrivée) ; attestations et certificats
- [ ] **8.8** Portail parents : notes, bulletins PDF, discipline, documents ; tableau de bord : résultats scolaires (cahier § 8.10, 8.13)
- [ ] **8.9** Sondages ; option de blocage des bulletins / examens en cas de dette (désactivée par défaut) (cahier § 8.4, 8.9)

## V2 — après la V1.4 (proposition : ordre et découpage à valider avant de commencer)

Chaque tâche V2 sera redécoupée en sous-tâches (9.1.1, 9.1.2…) au moment de la commencer.

- [ ] **9.1** Réseau : tableau consolidé promoteur / coordination confessionnelle, comparaison entre années (cahier § 6.1, 8.13)
- [ ] **9.2** Plateforme : abonnements et facturation des écoles (tarif par élève, offres Découverte / Standard / Réseau, essai), revendeurs, statistiques globales (§ 5, 6.1) ; la console elle-même arrive en V1.1 (5.2–5.4)
- [ ] **9.3** Paiement en ligne Mobile Money via agrégateur, argent versé directement sur le compte de l'école (§ 5, 8.14)
- [ ] **9.4** SMS et WhatsApp avec crédits achetés par l'école ; relances d'impayés par SMS (§ 8.4, 8.9)
- [ ] **9.5** Applications Android et iPhone (Capacitor) publiées dans les stores ; lecture de la puce de la carte sur iPhone (§ 8.10)
- [ ] **9.6** Pré-inscription en ligne, test d'admission, liste d'attente (§ 8.3)
- [ ] **9.7** Comptabilité SYSCOHADA complète : journal, grand livre, budget prévisionnel, rapprochement bancaire (§ 8.4)
- [ ] **9.8** Emploi du temps automatique sans conflit ; devoirs et cours publiés (enseignant, élève, parent) (§ 8.6, 8.10–8.12)
- [ ] **9.9** Évaluations d'atelier (écoles techniques) ; évaluation des enseignants (§ 8.5, 8.6)
- [ ] **9.10** Rapports officiels EPST : statistiques de fin d'année, listes ENAFEP / Exetat, palmarès officiel (§ 8.13)
- [ ] **9.11** Enseignement supérieur LMD : semestres, unités d'enseignement, crédits, sessions (§ 7)
- [ ] **9.12** Vie scolaire : bibliothèque, cantine (menu dans le portail), transport (itinéraires, suivi GPS), internat (§ 8.10, 8.14)
- [ ] **9.13** Gestion matérielle : inventaire, ateliers (équipements, matières d'œuvre, TP), boutique (uniformes, fournitures) (§ 8.14)
- [ ] **9.14** Orientation scolaire, anciens élèves, site vitrine généré pour chaque école (`{ecole}.mwangaza.school/`) (§ 8.14, architecture § 2)
- [ ] **9.15** Sécurité en profondeur : Row Level Security PostgreSQL (architecture § 4)

## Plus tard (non planifié)

Migration depuis d'autres logiciels ; rapports transmis aux sous-divisions EPST ; maternelle ; intelligence artificielle (non prévue au départ).

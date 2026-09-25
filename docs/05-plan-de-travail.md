# Plan de travail

Chaque tâche est faite dans une branche, avec tests, puis cochée ici. Les références (A1, F5…) renvoient à `02-perimetre-v1.md`.

Pour lancer une tâche dans Claude Code : `/tache 2.3` (ou « Fais la tâche 2.3 du plan de travail. »). Claude relit `CLAUDE.md` et les documents liés.

État actuel, tâche en cours, bloquants et journal de chaque étape : `06-suivi.md` (`/etat` dans Claude Code).

## Avant de coder (toi, cette semaine)

- [ ] Récupérer auprès de l'ITIG les éléments listés au § 11 du cahier des charges (surtout : grille des frais, liste des élèves en Excel, modèle de reçu actuel)
- [ ] Choisir le nom définitif, vérifier le domaine, l'acheter
- [ ] Créer les comptes : hébergeur VPS, Cloudflare, stockage objet, GitHub (dépôt privé)
- [ ] Noter le modèle de l'imprimante thermique de l'ITIG

## Semaine 1 — Socle

- [ ] **0.1** Créer le monorepo selon `03-architecture-technique.md` § 3 ; Docker Compose de développement (postgres, redis, django, front) ; compléter la section « Commandes » de `CLAUDE.md`
- [ ] **0.2** Qualité : ruff, pytest, ESLint, Prettier, Vitest, pre-commit, GitHub Actions (lint + tests)
- [ ] **1.1** App `core` : `TenantModel`, `TenantManager` qui lève une erreur sans école, `TenantMiddleware` par sous-domaine, UUID v7, classe `Money` + tests
- [ ] **1.2** App `accounts` : `User` (téléphone comme identifiant), `Membership`, `Role`, codes de permissions, rôles système copiés à la création d'une école (B1–B3)
- [ ] **1.3** Connexion par session, TOTP pour les rôles sensibles, limitation des tentatives (B4)
- [ ] **1.4** App `audit` : `AuditLog` + utilitaire d'enregistrement (I1)
- [ ] **1.5** Super-admin : création / suspension d'école, liste des écoles, connexion « en tant qu'école » tracée (A1–A3)
- [ ] **1.6** Front `gestion` : squelette React + Vite + PWA + Tailwind + shadcn/ui + i18next ; écran de connexion ; mise en page avec menu selon permissions
- [ ] **1.7** App `schools` : année scolaire depuis modèle, périodes, niveaux, options, classes, format de matricule + écrans (C1–C3)

## Semaine 2 — Élèves et frais

- [ ] **2.1** App `students` : `Student`, `Family`, `Guardian`, `Enrollment`, génération du matricule et du code famille
- [ ] **2.2** Écrans élèves : liste, recherche rapide, fiche, création, inscription, liaison famille (D2–D4)
- [ ] **2.3** Import Excel : téléversement, correspondance des colonnes, aperçu, rapport d'erreurs, import en tâche Celery (D1). Tester avec le vrai fichier de l'ITIG
- [ ] **2.4** Impressions : fiche d'inscription avec code famille, liste de classe PDF / Excel (D5)
- [ ] **2.5** App `finance` — configuration : `FeeType`, `FeeRule`, `InstallmentTemplate`, `ExchangeRate`, `Discount` + écrans (E1–E3, E5)
- [ ] **2.6** Génération des `StudentCharge` à l'inscription et quand un barème change ; échéancier particulier (E4)
- [ ] **2.7** Calcul du solde et des retards d'un élève (service + tests couvrant réductions, devises, annulations)

## Semaine 3 — Caisse et hors-ligne

- [ ] **3.1** Caisses et sessions de caisse ; `Payment`, `PaymentAllocation`, répartition automatique + ajustement (F1–F2), en ligne d'abord
- [ ] **3.2** Reçu 80 mm et A4 dans le navigateur, montant en lettres (français), QR code ; page publique de vérification `/v/{id}` (F3–F4, F6)
- [ ] **3.3** App `sync` : `Device`, enregistrement d'appareil avec préfixe, `SyncOperation`, `ChangeLog`, endpoints `snapshot`, `pull`, `push` idempotents
- [ ] **3.4** Front : base Dexie, instantané initial, file d'opérations, synchronisation automatique, indicateur d'état, stockage persistant
- [ ] **3.5** Caisse hors-ligne complète : recherche élève, solde, encaissement, reçu, numérotation locale (F5). Tests Playwright : couper le réseau, encaisser, reconnecter, vérifier aucun doublon
- [ ] **3.6** Crédit élève en cas de surpaiement après synchronisation
- [ ] **3.7** PIN de déverrouillage hors-ligne, expiration à 7 jours, révocation d'appareil (B5)
- [ ] **3.8** Annulation avec demande / validation (F7) ; clôture de caisse (F8)

## Semaine 4 — Rapports, portail parents, mise en production

- [ ] **4.1** Impayés : liste filtrable, export ; situation financière imprimable (G1–G2)
- [ ] **4.2** Tableau de bord directeur (G3)
- [ ] **4.3** Annonces côté école (H4)
- [ ] **4.4** Front `portail` : activation par téléphone + code famille, liste des enfants multi-écoles, paiements, reçus PDF, échéances, annonces, mise à jour des coordonnées, installable (H1–H6)
- [ ] **4.5** Guides de première connexion : caissier, comptable, parent (I3) ; traduction anglaise (I2)
- [ ] **4.6** Infra de production : VPS, Caddy, wildcard Cloudflare, variables d'environnement, déploiement en une commande
- [ ] **4.7** Sauvegardes continues + dump quotidien + **test de restauration** (I4) ; suivi d'erreurs ; sonde de disponibilité
- [ ] **4.8** Mise en place à l'ITIG : import des élèves, frais, comptes, formation des caissiers, impression de test

## Semaines 5 à 8 — V1.1

- [ ] **5.1** Dépenses par catégorie, rapports entrées / sorties
- [ ] **5.2** RH : dossier employé, contrats, qualifications, statut SECOPE
- [ ] **5.3** Paie : périodes, lignes, primes, motivation enseignants liée aux frais, avances, retenues, fiche de paie PDF
- [ ] **5.4** Notifications push (paiement reçu, échéance proche, annonce) ; relances automatiques d'impayés
- [ ] **5.5** Cartes d'élève PDF avec photo et QR ; pointage d'entrée par scan QR sur tablette, hors-ligne
- [ ] **5.6** Pénalités de retard, validation d'inscription liée au paiement, documents téléversés
- [ ] **5.7** Connexion Google, champs complémentaires de la fiche élève

## Semaines 9 à 14 — V1.2 (ordre à ajuster selon la date des bulletins ITIG)

- [ ] **6.1** Cours, maxima, domaines, attribution enseignants
- [ ] **6.2** Saisie des notes (y compris hors-ligne), verrouillage, validation, historique
- [ ] **6.3** Bulletin EPST PDF avec QR d'authenticité, calcul des totaux, places, mentions
- [ ] **6.4** Délibération, décisions, palmarès, passage de classe
- [ ] **6.5** Lecteurs RFID ESP32 (dossier `firmware/`) et API de pointage ; présences du personnel
- [ ] **6.6** Notifications d'absence et de retard, justification par le parent
- [ ] **6.7** Discipline ; messagerie parent ↔ titulaire / administration ; rendez-vous
- [ ] **6.8** Portail élèves ; espace enseignant et titulaire
- [ ] **6.9** Transfert d'élève entre écoles de la plateforme ; attestations et certificats

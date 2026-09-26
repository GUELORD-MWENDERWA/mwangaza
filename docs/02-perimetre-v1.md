# Périmètre de la version 1

## 1. Réalisme du calendrier

Objectif demandé : une première version utilisable en **un mois**, développée seul avec Claude Code. C'est possible **uniquement** avec un périmètre serré. Les priorités cochées (multi-écoles, rôles, finances, impayés, portail parents, tableau de bord, paie) forment trop de travail pour 4 semaines si on ajoute le hors-ligne. On découpe donc :

| Lot | Durée | But |
|---|---|---|
| **V1.0** | semaines 1 à 4 | L'ITIG encaisse les frais sur Mwangaza, même sans internet, et les parents voient les paiements. |
| **V1.1** | semaines 5 à 8 | Paie et dossiers du personnel, dépenses, relances push, cartes d'élève QR et pointage par tablette. |
| **V1.2** | semaines 9 à 14 | Notes, bulletins EPST, délibération, présences RFID, discipline, messagerie, portail élèves. |
| **V2** | ensuite | Voir cahier des charges. |

Pourquoi les finances d'abord : la rentrée a eu lieu le 1er septembre, les écoles encaissent maintenant, et la caisse est l'endroit où l'argent et la confiance se jouent. Pourquoi la paie en V1.1 : la première paie se fait en fin de mois, elle peut arriver quelques semaines après la caisse. Bulletins (décision Q6 du 2026-09-26) : la 1re période 2026 reste sur papier à l'ITIG ; les bulletins se font avec Mwangaza à partir de la 2e période / 1er semestre ; l'ordre V1.1 puis V1.2 ne change pas.

Deux modules non cochés sont **indispensables** au portail parents et à la caisse, donc inclus en V1.0 : élèves / inscriptions et classes.

Le **hors-ligne** est conçu dès le premier jour (identifiants, synchronisation, reçus) même s'il ne couvre que la caisse en V1.0 : l'ajouter après coup obligerait à tout refaire.

## 2. Contenu de V1.0

### A. Plateforme et super-admin

- **A1** — En tant que super-admin, je crée une école (nom, code sous-domaine, logo, devises, fuseau horaire) et son premier compte directeur.
  - L'école est accessible à `{code}.mwangaza.school/app`.
  - Je peux suspendre une école : ses utilisateurs ne peuvent plus se connecter, les données restent.
- **A2** — Je vois la liste des écoles avec nombre d'élèves, date de dernière activité, statut d'abonnement (saisi à la main en V1.0).
- **A3** — Je peux me connecter en tant qu'une école pour le support ; l'action est inscrite dans l'audit et un bandeau l'indique à l'écran.

### B. Comptes, rôles, connexion

- **B1** — Rôles prédéfinis (9) : directeur, directeur des études, directeur de discipline / surveillant, comptable, caissier, secrétaire, promoteur, enseignant (sans fonctions en V1.0), parent. Plusieurs personnes peuvent avoir le même rôle. Permissions : `04-modele-de-donnees.md` § 8.
- **B2** — L'école crée un rôle personnalisé en cochant des permissions (ex : « chef d'atelier » à l'ITIG, en attendant le module ateliers de la V2).
- **B3** — Un utilisateur peut avoir plusieurs rôles et appartenir à plusieurs écoles avec un seul compte.
- **B4** — Connexion identifiant + mot de passe ; TOTP obligatoire pour directeur, comptable, caissier, promoteur.
- **B5** — Sur un appareil déjà connecté, un code PIN déverrouille l'application, y compris hors-ligne. Après 5 PIN faux, reconnexion complète exigée.

### C. Organisation de l'école

- **C1** — Le directeur crée l'année scolaire 2026-2027 à partir d'un modèle (secondaire : 2 semestres, 4 périodes, 2 examens).
- **C2** — Il crée niveaux, options et classes (ex : 3e Électricité A).
- **C3** — Il configure le format du matricule (ex : `ITIG-{AAAA}-{0000}`).

### D. Élèves

- **D1** — Le secrétariat importe un fichier Excel d'élèves : aperçu, correspondance des colonnes, rapport d'erreurs ligne par ligne, import sans doublon (même nom + date de naissance + classe signalés).
- **D2** — Il crée, modifie et recherche un élève (nom, post-nom, prénom, matricule) en moins de 2 secondes sur 3 000 élèves.
- **D3** — Il inscrit l'élève dans une classe pour l'année ; matricule attribué automatiquement.
- **D4** — Il lie l'élève à une famille (tuteur principal + contacts) ; une famille peut avoir plusieurs enfants.
- **D5** — Il imprime la fiche d'inscription (avec le code famille) et la liste d'une classe (PDF, Excel).

### E. Frais et échéanciers

- **E1** — Le comptable crée des types de frais (minerval, fonctionnement, frais connexes…).
- **E2** — Il définit un barème : montant et devise (USD ou FC, au choix pour chaque barème) par niveau / option / classe, découpé en tranches avec dates limites, ou mensuel.
- **E3** — Il applique une réduction à un élève (montant ou %), avec motif. L'auteur est enregistré.
- **E4** — Il crée un échéancier particulier pour un élève.
- **E5** — Il saisit le taux de change de l'année scolaire (USD → FC), fixe toute l'année. Il peut le corriger en cours d'année : l'historique garde qui, quand, l'ancien et le nouveau taux ; les paiements déjà faits gardent le taux utilisé.

### F. Caisse et reçus

- **F1** — Le caissier cherche un élève, voit ce qu'il doit par frais et par tranche, dans chaque devise.
- **F2** — Il encaisse un montant (total ou partiel) dans une devise ; le système répartit sur les échéances les plus anciennes ; il peut ajuster la répartition avant de valider.
- **F3** — Le reçu s'imprime aussitôt, dans le format choisi par l'école dans ses paramètres : thermique 58 mm ou 80 mm, ou imprimante ordinaire avec un reçu A6 (4 par A4), A5 (2 par A4) ou petit format (≈ 10 × 7 cm) et des traits de découpe — un petit reçu à coller dans le cahier de l'élève ; 1 exemplaire, ou 2 avec une souche pour l'école. Contenu : école, logo (noir et blanc sur thermique), numéro unique, élève, classe, détail, montant en chiffres et en lettres (ex : « Cent cinquante dollars américains et vingt-cinq centimes », « Deux cent quatre-vingt-cinq mille francs congolais »), devise, taux utilisé si conversion, reste à payer, nom du caissier, date/heure, zone signature / cachet, QR code.
- **F4** — Le QR code ouvre une page publique de vérification qui affiche le minimum : école, numéro, date, montant, reçu valide / annulé, élève en initiales seulement (aucune donnée personnelle complète). Un reçu imprimé **hors ligne** reste vérifiable : le QR code est signé par l'appareil, la page affiche « reçu authentique, en attente de synchronisation ».
- **F5** — **Hors-ligne** : F1 à F3 fonctionnent sans internet. Les paiements sont synchronisés automatiquement au retour du réseau. Aucun doublon même si l'envoi est répété.
- **F6** — Réimpression d'un reçu (mention « DUPLICATA »).
- **F7** — Annulation d'un paiement : demandée avec motif, validée par un utilisateur ayant la permission ; un reçu d'annulation est produit ; le paiement d'origine reste visible, marqué annulé.
- **F8** — Clôture de caisse : le caissier saisit le montant compté par devise ; le système affiche le total attendu et l'écart ; la clôture est signée par le caissier et visible du comptable. Après clôture, plus d'encaissement dans cette session.

### G. Impayés et tableau de bord

- **G1** — Liste des élèves en retard par classe, frais, tranche ; export PDF / Excel.
- **G2** — Situation financière d'un élève imprimable.
- **G3** — Tableau de bord directeur : encaissé aujourd'hui / ce mois par devise, total des impayés, taux de recouvrement par classe, effectifs par classe et par sexe.

### H. Portail parents

- **H1** — Le parent ouvre `parents.mwangaza.school`, saisit son numéro de téléphone et le code famille imprimé, choisit un mot de passe.
- **H2** — Il voit la liste de ses enfants, même dans des écoles différentes : chaque école garde sa propre fiche de l'enfant et de la famille ; le parent ajoute une autre école à son compte avec le code famille qu'elle lui a remis.
- **H3** — Pour chaque enfant : classe, école, photo (si consentement), situation des paiements, reçus (PDF), prochaines échéances.
- **H4** — Il voit les annonces de l'école.
- **H5** — Il met à jour son adresse et ses contacts ; la modification est signalée au secrétariat de chaque école de ses enfants, qui l'applique à sa propre fiche.
- **H6** — Le portail s'installe sur l'écran d'accueil du téléphone et reste léger.

### I. Transversal

- **I1** — Audit de toute action sur finances, rôles et élèves.
- **I2** — Interface en français, traduction anglaise disponible.
- **I3** — Guide de première connexion pour caissier, comptable et parent.
- **I4** — Sauvegarde quotidienne automatique vers un stockage externe, restauration testée une fois.

## 3. Hors périmètre V1.0 (ne pas coder maintenant)

Paie, RH, dépenses, notes, bulletins, délibération, présences, discipline, messagerie, portail élèves, paiement en ligne, SMS / WhatsApp, applications dans les stores, connexion Google, pré-inscription en ligne, bibliothèque, cantine, transport, ateliers, IA, rapports EPST, comptabilité SYSCOHADA complète.

## 4. Critères de réussite du pilote ITIG

- Tous les élèves de l'ITIG importés et inscrits dans leur classe.
- Les caissiers encaissent uniquement sur Mwangaza pendant 2 semaines, y compris pendant des coupures.
- Aucune différence entre la clôture de caisse et l'argent compté qui soit due au logiciel.
- Au moins 30 % des familles ont activé leur compte parent à la fin du premier mois.
- Le directeur consulte le tableau de bord sans aide.

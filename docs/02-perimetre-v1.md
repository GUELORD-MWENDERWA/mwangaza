# Périmètre de la version 1

## 1. Réalisme du calendrier

Objectif demandé : une première version utilisable en **un mois**, développée seul avec Claude Code. C'est possible **uniquement** avec un périmètre serré. Les priorités cochées (multi-écoles, rôles, finances, impayés, portail parents, tableau de bord, paie) forment trop de travail pour 4 semaines si on ajoute le hors-ligne. On découpe donc :

| Lot | But |
|---|---|
| **V1.0** — finances, caisse, portail parents | Une école encaisse ses frais, même sans internet, et les parents voient les paiements. **Faite** ; il reste l'invitation des familles et le guide PDF (4.9, 4.10), puis elle est mise de côté ; mise en ligne quand l'utilisateur le décide. |
| **V1.1** — plateforme, notifications, communication | Identité de la plateforme configurable (nom, logo…), console de la plateforme avec son propre design (au lieu de l'administration Django), notifications sur l'écran même application fermée, communication de l'école. |
| **V1.2** — carte unique et présences | Une carte par élève et par membre du personnel (puce NFC + QR + photo), liée en une seconde ; pointage par la puce (téléphone Android enregistré, lecteur ESP32) ou par le QR (n'importe quel appareil enregistré) ; présences suivies et signalées aux parents. |
| **V1.3** — personnel, paie, dépenses | Dossiers du personnel, paie, dépenses, espace enseignant, congés, pénalités de retard. |
| **V1.4** — notes, bulletins, vie scolaire | Notes, bulletins EPST, délibération, discipline, messagerie, portail élèves, transferts. |
| **V2** | Voir cahier des charges et `05` (abonnements, Mobile Money, SMS / WhatsApp, applications dans les stores…). |

Découpage revu le 2026-10-02 à la demande de l'utilisateur : la plateforme et les notifications d'abord (elles servent à toutes les fonctions suivantes), puis la carte et les présences (les présences du personnel nourrissent la paie), puis la paie, puis les notes. **On n'attend rien de l'ITIG** : c'est l'école d'exemple ; comme toute école, elle saisit ses données elle-même.

Pourquoi les finances d'abord : la rentrée a eu lieu le 1er septembre, les écoles encaissent maintenant, et la caisse est l'endroit où l'argent et la confiance se jouent. Pourquoi la paie en V1.1 : la première paie se fait en fin de mois, elle peut arriver quelques semaines après la caisse. Bulletins : V1.4 ; une école qui les veut plus tôt les fait sur papier en attendant (la décision Q6 du 2026-09-26, « à partir de la P2 », est remplacée par le découpage du 2026-10-02).

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
- **H7** — L'école invite toutes ses familles d'un coup : une lettre PDF par famille (adresse du portail avec QR, code famille, étapes), imprimable par classe, ou un message prêt à partager ; elle voit quelles familles ont activé leur compte. *(ajouté le 2026-10-02)*

### I. Transversal

- **I1** — Audit de toute action sur finances, rôles et élèves.
- **I2** — Interface en français, traduction anglaise disponible. Textes du serveur (administration, messages, PDF, Excel) traduits aussi ; ils suivent la langue choisie dans l'application, pas celle du navigateur.
- **I3** — Guide de première connexion pour caissier, comptable et parent.
- **I4** — Sauvegarde quotidienne automatique vers un stockage externe, restauration testée une fois.
- **I5** — Guide de la version en PDF : ce qu'elle fait, rôle par rôle, avec captures ; ses limites et ce qu'apportent les versions suivantes. *(ajouté le 2026-10-02)*

## 3. Hors périmètre V1.0 (ne pas coder maintenant)

Version de chaque fonction : `05-plan-de-travail.md`.

Paie, RH, dépenses, notes, bulletins, délibération, présences, discipline, messagerie, portail élèves, paiement en ligne, SMS / WhatsApp, applications dans les stores, connexion Google, pré-inscription en ligne, bibliothèque, cantine, transport, ateliers, IA, rapports EPST, comptabilité SYSCOHADA complète.

## 4. Critères de réussite d'une école qui démarre

Valables pour toute école, l'ITIG comprise ; rien n'est attendu d'une école en particulier.

- Tous les élèves de l'école importés et inscrits dans leur classe.
- Les caissiers encaissent uniquement sur Mwangaza pendant 2 semaines, y compris pendant des coupures.
- Aucune différence entre la clôture de caisse et l'argent compté qui soit due au logiciel.
- Au moins 30 % des familles ont activé leur compte parent à la fin du premier mois.
- Le directeur consulte le tableau de bord sans aide.

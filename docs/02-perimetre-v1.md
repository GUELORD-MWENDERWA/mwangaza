# Périmètre de la version 1

## 1. Réalisme du calendrier

Objectif demandé : une première version utilisable en **un mois**, développée seul avec Claude Code. C'est possible **uniquement** avec un périmètre serré. Les priorités cochées (multi-écoles, rôles, finances, impayés, portail parents, tableau de bord, paie) forment trop de travail pour 4 semaines si on ajoute le hors-ligne. On découpe donc :

| Lot | But |
|---|---|
| **V1.0** — finances, caisse, portail parents | Une école encaisse ses frais, même sans internet, et les parents voient les paiements. **Faite**, guide PDF compris (4.10 : `docs/guide/guide-v1.0.pdf`), puis mise de côté ; mise en ligne quand l'utilisateur le décide. |
| **V1.1** — plateforme, notifications, communication | Identité de la plateforme configurable (nom, logo…), console de la plateforme avec son propre design (au lieu de l'administration Django), notifications sur l'écran même application fermée, communication de l'école. **Faite** le 2026-10-12 (5.7), guide `docs/guide/guide-v1.1.pdf`. |
| **Lancement** — modules, rôles libres, sécurité | Modules et rôles libres (M.2, M.3), sécurité avant les vraies données (bloc S, P0), restauration réelle des sauvegardes, essai sur vrais téléphones ; puis le premier espace réel. |
| **V1.2** — notes, bulletins, finances de l'école | Cours et charges horaires des enseignants, notes (hors ligne compris), bulletins EPST, délibération ; dépenses, sorties de caisse, budget (FIN) ; Row Level Security (S.6). |
| **V1.3** — plateforme commerciale | Abonnements par module, factures de la plateforme aux écoles, lecture seule si impayé (ABO) ; page des prix du site de la plateforme (le site public lui-même, WEB.1a → WEB.1c, est avancé au lancement le 2026-10-17) ; protection des données, détection, revue de sécurité. |
| **V1.4** — emploi du temps et IA | Emploi du temps calculé par un solveur sans conflit, éditeur, publication, heures prestées (EDT, **avancé le 2026-10-20 avant la fin de la V1.2**, avec l'IA du directeur des études : spécification `docs/specs/emploi-du-temps.md`) ; IA (Claude) qui aide sans jamais décider seule : contraintes en phrases, grille de cours depuis un bulletin en PDF, assistant, rédaction (IA) ; vendue avec l'abonnement, pilotée depuis la console (usages par école, crédits, plafond). |
| **V1.5** — carte et présences | Carte avec QR d'abord (NFC et ESP32 en option), pointage, suivi des présences, parents prévenus. |
| **V1.6** — bibliothèque et ateliers | Moteur commun de prêts et de stock (INV) ; prêts de livres, bon de prêt, parents prévenus, pertes facturées (BIB) ; stock et commandes de matériel des ateliers (ATL). |
| **V1.7** — sites des écoles, personnel, vie scolaire | Site de chaque école rempli par elle (WEB.2), dossiers du personnel, paie, espace enseignant, discipline, messagerie, portail élèves, transferts. |
| **V2** | Voir cahier des charges et `05` (Mobile Money, SMS / WhatsApp, rapports EPST, applications dans les stores…). |

Découpage revu le 2026-10-02 à la demande de l'utilisateur, puis **le 2026-10-13** (plan révisé et validé, tâche L.0) : la sécurité et les modules avant les vraies données, les notes et bulletins avant la carte (chaque école sort des bulletins chaque période ; la carte NFC demande du matériel), les abonnements ensuite, puis l'emploi du temps et l'IA, la bibliothèque et les ateliers. **On n'attend rien de l'ITIG** : c'est l'école d'exemple ; comme toute école, elle saisit ses données elle-même.

Pourquoi les finances d'abord : la rentrée a eu lieu le 1er septembre, les écoles encaissent maintenant, et la caisse est l'endroit où l'argent et la confiance se jouent. Pourquoi la paie en V1.1 : la première paie se fait en fin de mois, elle peut arriver quelques semaines après la caisse. Bulletins : V1.2 depuis le 2026-10-13 (la décision Q6 du 2026-09-26, « à partir de la P2 », reste remplacée).

Deux modules non cochés sont **indispensables** au portail parents et à la caisse, donc inclus en V1.0 : élèves / inscriptions et classes.

Le **hors-ligne** est conçu dès le premier jour (identifiants, synchronisation, reçus) même s'il ne couvre que la caisse en V1.0 : l'ajouter après coup obligerait à tout refaire.

## 2. Contenu de V1.0

### A. Plateforme et super-admin

- **A1** — En tant que super-admin, je crée une école (nom, code sous-domaine, logo, devises, fuseau horaire) et son premier compte directeur.
  - L'école est accessible à `{code}.mwangazaschool.com/app`.
  - Je peux suspendre une école : ses utilisateurs ne peuvent plus se connecter, les données restent.
- **A2** — Je vois la liste des écoles avec nombre d'élèves, date de dernière activité, statut d'abonnement (saisi à la main en V1.0).
- **A3** — Je peux me connecter en tant qu'une école pour le support ; l'action est inscrite dans l'audit et un bandeau l'indique à l'écran.

### B. Comptes, rôles, connexion

- **B1** — Rôles de départ (9), copiés dans chaque école neuve : directeur, directeur des études, directeur de discipline / surveillant, comptable, caissier, secrétaire, promoteur, enseignant (sans fonctions en V1.0), parent. Ce sont des rôles ordinaires : l'école les renomme, change leurs permissions et les supprime (M.3.2). Plusieurs personnes peuvent avoir le même rôle. Permissions : `04-modele-de-donnees.md` § 8.
- **B2** — L'école crée un rôle personnalisé en cochant des permissions (ex : « chef d'atelier » à l'ITIG, en attendant le module ateliers de la V1.6).
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
- **F3** — Le reçu s'imprime aussitôt, dans le format choisi par l'école dans ses paramètres : thermique 58 mm ou 80 mm, ou imprimante ordinaire sur une feuille de la largeur d'un A4 : demi A4 (21 × 14,8 cm) ou tiers d'A4 (21 × 9,9 cm), **un reçu par feuille**, un seul exemplaire (le registre des reçus tient lieu de souche). Contenu : école, logo (noir et blanc sur thermique), numéro unique, élève, classe, détail, montant en chiffres et en lettres (ex : « Cent cinquante dollars américains et vingt-cinq centimes », « Deux cent quatre-vingt-cinq mille francs congolais »), devise, taux utilisé si conversion, reste à payer, nom du caissier, date/heure, zone signature / cachet, QR code.
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

- **H1** — Le parent ouvre `parents.mwangazaschool.com`, saisit son numéro de téléphone et le code famille imprimé, choisit un mot de passe.
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

## 2 bis. Version de lancement (ajouté le 2026-10-10)

Ce qu'il faut en plus pour qu'une vraie école démarre sans aide ; tâches 4.12 à 4.21 et 4.7.1 de `05-plan-de-travail.md`, détail des espaces dans `03-architecture-technique.md` § 4 bis.

- **A4** — La plateforme n'a qu'une console. J'y crée des espaces de trois types : **réel** (vide, pour une vraie école, rien d'inventé), **essai** (vide, pour moi et les personnes intéressées), **démonstration** (rempli de données fictives). Je lance (en le créant), suspends, réactive et arrête chaque espace.
- **A5** — Je supprime un espace d'essai ou de démonstration ; jamais un espace réel, que j'arrête.
- **A6** — Je crée un espace de démonstration en un clic et je reçois sa fiche d'accès (adresses, un numéro par rôle, mot de passe, codes famille) à remettre à un visiteur ; je le remets à zéro quand je veux.
- **A7** — Un espace d'essai ou de démonstration se reconnaît partout : bandeau à l'écran, « SPÉCIMEN » sur les reçus. Ses chiffres ne comptent pas dans ceux de la plateforme.
- **C4** — Le directeur d'une école neuve suit une liste « Mise en route » qui le mène, étape par étape, jusqu'au premier encaissement. (4.20.1 : en haut du tableau de bord, et dès l'accueil après la connexion depuis la 4.20.2 ; année, classes, frais et taux, compte qui encaisse, caisse et appareil, élèves, puis deux étapes facultatives — reprise, invitation des parents ; chaque étape se coche seule ; le directeur termine la liste quand l'école peut encaisser, elle ne revient plus.)
- **C5** — L'école choisit si les matricules sont attribués automatiquement (précise C3 et D3) ; sinon elle garde les siens ou n'en a pas.
- **D6** — Le secrétariat importe ses élèves sans matricule et annule un import raté.
- **E6** — Une école qui démarre en cours d'année importe ce que chaque élève a déjà payé avant Mwangaza, sans reçu ni effet sur la caisse du jour. (4.19 : fichier Excel d'après un modèle déjà garni, aperçu avec erreurs et totaux, une ligne par élève et par devise, frais facultatif ; visible sur la fiche élève, le relevé et le Portail ; corrigé par l'annulation habituelle.)
- **H8** — Le parent reste connecté sur son téléphone, y compris quand le réseau est mauvais ; une session finie le ramène à la connexion avec un message clair.
- **I4** (précisé) — Sauvegardes et restauration prêtes et essayées sur la machine avant l'achat du stockage ; branchées au vrai stockage à la mise en ligne.

## 3. Hors périmètre V1.0 (ne pas coder maintenant)

Version de chaque fonction : `05-plan-de-travail.md`.

Paie, RH, dépenses, notes, bulletins, délibération, présences, discipline, messagerie, portail élèves, abonnements, emploi du temps, IA, sites web, bibliothèque, ateliers (versions V1.2 à V1.7) ; paiement en ligne, SMS / WhatsApp, applications dans les stores, pré-inscription en ligne, cantine, transport, rapports EPST, comptabilité SYSCOHADA complète (V2).

## 4. Critères de réussite d'une école qui démarre

Valables pour toute école, l'ITIG comprise ; rien n'est attendu d'une école en particulier.

- Tous les élèves de l'école importés et inscrits dans leur classe.
- Les caissiers encaissent uniquement sur Mwangaza pendant 2 semaines, y compris pendant des coupures.
- Aucune différence entre la clôture de caisse et l'argent compté qui soit due au logiciel.
- Au moins 30 % des familles ont activé leur compte parent à la fin du premier mois.
- Le directeur consulte le tableau de bord sans aide.

# Cahier des charges — Mwangaza

> Version 1.0 — septembre 2026. Ce document décrit **tout le produit visé**. Ce qui est construit maintenant est limité par `02-perimetre-v1.md`. Chaque fonction porte un lot : **V1.0**, **V1.1**, **V1.2**, **V2** ou **Plus tard**.

## 1. Contexte

Les écoles congolaises gèrent encore largement élèves, frais et bulletins sur papier ou Excel. Les parents doivent se déplacer ou appeler le secrétariat pour connaître la situation de leur enfant. Des plateformes existent (MASOMO, Msomi System, SchoolBook RDC, Edu-RDC, EDUC RDC), mais la plupart supposent une connexion internet stable.

Contraintes du terrain à Goma et dans l'Est :

- coupures fréquentes d'internet et d'électricité ;
- forfaits de données chers, beaucoup de téléphones Android d'entrée de gamme ;
- paiements en USD et en FC, souvent partiels et étalés (budgets familiaux sous forte pression) ;
- contexte sécuritaire et sanitaire instable : les données doivent survivre à la perte d'un ordinateur ou à la fermeture temporaire d'une école.

École pilote : **ITIG Don Bosco Goma** — institut technique industriel conventionné catholique (salésien), environ 1 200 élèves, une soixantaine d'enseignants, ateliers de mécanique générale, automobile, électricité et électronique.

## 2. Vision

Une seule plateforme en ligne qui héberge beaucoup d'écoles. Elle a deux visages :

- **Le logiciel de gestion** (application « Gestion ») : utilisé par le personnel pour tout gérer — élèves, finances, caisse, paie, notes, présences. Il fonctionne **même sans internet** et se synchronise dès que la connexion revient.
- **Le portail** (application « Portail ») : utilisé par les parents et les élèves pour **consulter** en direct paiements, échéances, présences, notes, bulletins et annonces. Il sert surtout à voir et à être informé ; les seules actions sont simples (mettre à jour ses coordonnées, télécharger un document, demander un rendez-vous, écrire au titulaire).

Les deux applications partagent le même serveur et la même base de données. Ce que la caisse encaisse apparaît chez le parent dès la synchronisation.

### Nos avantages face aux concurrents

1. Hors-ligne réel pour la caisse et la saisie (pas seulement « consultable hors-ligne »).
2. Présence automatique par badge RFID (lecteurs ESP32 fabriqués localement) ou QR code.
3. Prix plus bas, adapté aux écoles de l'Est.
4. Interface très simple, guidée dès la première connexion.
5. Documents conformes EPST prêts à imprimer (bulletins, listes, palmarès).
6. Application parents installable sur téléphone.
7. Support de proximité à Goma.

## 3. Nom du produit

Le nom doit venir de chez nous, être court, facile à dire au téléphone et évoquer l'éducation. Propositions (en swahili, langue courante à Goma) :

| Nom | Sens | Pourquoi |
|---|---|---|
| **Mwangaza** (nom de travail) | lumière, clarté | L'école devient transparente pour les parents. Sonne bien, se retient. |
| Shule Yetu | notre école | Chaleureux, communautaire. |
| Tujifunze | apprenons ensemble | Dynamique, parle aux élèves. |
| Ujuzi | savoir, compétence | Court, moderne ; colle aux écoles techniques. |
| Nyota | étoile | Réussite, excellence. Très court. |
| Kivu Elimu | l'éducation du Kivu | Ancré localement, mais limite l'expansion nationale. |

**Choisi le 2026-09-26 : Mwangaza**, domaine `mwangazaschool.com` (`mwangaza.cd`, `.com` et `.app` n'étaient pas disponibles ; « Shule Yetu » est déjà une plateforme scolaire).

## 4. Cibles

- Toutes les structures d'enseignement : écoles privées, conventionnées, publiques, réseaux de promoteurs, coordinations confessionnelles, sous-divisions EPST, universités et instituts supérieurs (LMD), centres de formation professionnelle.
- Lancement : Goma (5 à 20 écoles la première année), puis Nord-Kivu, puis toute la RDC.
- Taille typique : 1 000 à 3 000 élèves, plus de 5 postes utilisés en même temps.

## 5. Modèle économique (recommandation)

- **Tarif par élève inscrit et par an**, avec un minimum par école. Simple à comprendre, suit la taille de l'école. Facturé par trimestre pour étaler la charge.
- **Trois offres** :
  - *Découverte* (gratuite) : petite école sous un plafond d'élèves, modules finances de base et portail parents limité. Sert d'acquisition.
  - *Standard* : tous les modules pour une école.
  - *Réseau* : promoteurs et coordinations, tableau consolidé multi-écoles, tarif dégressif.
- **Essai** : un trimestre scolaire complet gratuit.
- **Options payantes** : crédits SMS/WhatsApp, lecteurs RFID et cartes PVC, nom de domaine propre, formation sur site.
- Le montant se calibre avec les tarifs des concurrents et les premières écoles. Repère : le coût annuel par élève doit rester une très petite fraction du minerval.
- **Paiements en ligne (plus tard)** : l'argent doit aller **directement sur le compte marchand de l'école**, jamais transiter par la plateforme (confiance des écoles, et détenir des fonds pour autrui pose des questions réglementaires). Passer par un agrégateur (type FlexPay, MaxiCash, CinetPay) pour couvrir M-Pesa, Orange Money et Airtel Money d'un coup ; comparer frais et agréments au moment de l'intégration.
- **SMS** : l'école achète des crédits SMS. Dans l'immédiat, on utilise les notifications de l'application et les notifications push, qui sont gratuites.

## 6. Acteurs et rôles

### 6.1 Plateforme

- **Super-administrateur** (propriétaire de la plateforme) : crée, active et suspend les écoles ; suit abonnements et paiements des écoles ; voit les statistiques globales et la santé du système ; diffuse des annonces à toutes les écoles ; peut se connecter « en tant qu'école » pour le support (tracé dans l'audit) ; gère les revendeurs et agents commerciaux.
- **Promoteur / réseau** : voit toutes ses écoles avec statistiques consolidées.
- **Coordination confessionnelle** : voit les écoles de sa coordination (statistiques, pas de données nominatives financières sauf accord).
- **Sous-division EPST** : reçoit les rapports officiels (Plus tard).

### 6.2 École

Rôles prédéfinis : promoteur, préfet des études / directeur, directeur des études, directeur de discipline, secrétaire, comptable, caissier, économe / intendant, titulaire, enseignant, surveillant, bibliothécaire, infirmier, chauffeur / responsable transport.

- Chaque école peut créer ses propres rôles en cochant des permissions.
- Une personne peut cumuler plusieurs rôles (ex : enseignant + titulaire + parent).
- **Identité unique sur la plateforme** : un enseignant qui travaille dans deux écoles a un seul compte, avec un rôle dans chaque école.

### 6.3 Familles

- **Un compte par famille**, identifié par le numéro de téléphone du tuteur principal. Les autres tuteurs figurent comme contacts dans la fiche.
- Un compte famille voit tous ses enfants, même inscrits dans des écoles différentes de la plateforme. Chaque école garde sa propre fiche de l'enfant et de la famille ; le parent relie chaque école à son compte avec le code famille qu'elle lui remet.
- **Élève** : compte optionnel, à partir d'un niveau configuré par l'école.

## 7. Organisation scolaire

- Niveaux : primaire, éducation de base (7e–8e), humanités générales, humanités techniques et professionnelles, supérieur LMD, formation professionnelle courte. (Maternelle possible plus tard.)
- Options des humanités configurées par chaque école (liste officielle proposée en suggestion).
- Classes avec plusieurs sections par niveau (1re A, 1re B…).
- **Découpage de l'année configurable par école**, avec modèles prêts :
  - secondaire : 2 semestres, chacun avec 2 périodes + 1 examen ;
  - primaire : modèle officiel à confirmer ;
  - LMD : semestres, unités d'enseignement, crédits, sessions (moteur séparé, V2).
- Clôture d'année : archivage, passage automatique selon la délibération, redoublants, abandons, exclusions, historique complet de l'élève sur toutes ses années dans l'école (chaque école a son propre dossier ; un transfert en donne une copie à la nouvelle école).

## 8. Modules fonctionnels

### 8.1 Plateforme multi-écoles — V1.0

- Accès du personnel par sous-domaine : `{code-ecole}.mwangazaschool.com`.
- Portail familles sur une adresse unique : `parents.mwangazaschool.com` (un parent peut avoir des enfants dans plusieurs écoles).
- Personnalisation par école : logo, nom, couleurs, en-têtes de reçus et bulletins, frais, barèmes et maxima, rôles.
- Transfert d'un élève d'une école à une autre de la plateforme avec son dossier (V1.7).
- Identité de la plateforme (nom, logo, couleurs, contact) dans ses paramètres, jamais écrite en dur : on peut la changer sans code (V1.1).
- Console de la plateforme pour le super-admin, avec son propre design : écoles, abonnements, comptes, appareils, journal, santé (V1.1) ; l'administration Django ne sert qu'au dépannage.

### 8.2 Connexion et sécurité des comptes — V1.0

- Identifiant + mot de passe.
- Double authentification (application TOTP) obligatoire pour les rôles financiers et la direction.
- Code PIN pour déverrouiller rapidement l'application sur un appareil déjà connecté (et hors-ligne).
- Connexion Google (V1.7).
- Création du compte famille : l'école génère un **code famille** imprimé sur le reçu ou la fiche d'inscription ; le parent l'active avec son numéro de téléphone et choisit un mot de passe. Pas de SMS nécessaire. Vérification par SMS en option plus tard.

### 8.3 Élèves et inscriptions

- Fiche élève — V1.0 : nom, post-nom, prénom, sexe, date et lieu de naissance, nationalité, province et territoire d'origine, adresse, photo, école de provenance, tuteurs avec contacts, contact d'urgence. V1.7 : groupe sanguin, allergies, besoins particuliers, religion, identifiant officiel EPST / Exetat.
- Matricule généré automatiquement, format configurable par école. Chaque école a sa propre fiche de l'élève : pas d'identité partagée entre écoles.
- Import Excel / CSV des élèves existants — V1.0. Migration depuis d'autres logiciels — Plus tard.
- Inscription au secrétariat — V1.0 ; validation de l'inscription liée au paiement — V1.7 ; pré-inscription en ligne par les parents, test d'admission, liste d'attente — V2.
- Documents téléversés (acte de naissance, bulletins antérieurs, certificats, photos, autres) — V1.7.
- Documents générés : fiche d'inscription et listes de classe (V1.0) ; carte unique de l'élève : puce NFC + QR code + photo (V1.5) ; attestation de fréquentation, certificat de scolarité, lettre de transfert (V1.7).
- Consentement des parents pour la photo — V1.0.

### 8.4 Finances

**Devises — V1.0**
- Multi-devises configurables (USD et FC activés par défaut).
- Chaque frais est défini en USD ou en FC, au choix pour chaque barème. Un paiement dans une autre devise est converti au taux de l'année saisi par le comptable (fixe toute l'année, corrigeable avec historique) ; le taux utilisé est enregistré sur le paiement.

**Frais — V1.0**
- Types : minerval, inscription / réinscription, fonctionnement, frais connexes (bulletins, cartes, examens d'État), uniformes, transport, cantine, activités parascolaires, frais d'examens officiels, frais personnalisés.
- Frais applicables à toute l'école, un niveau, une option, une classe ou un élève.
- Frais qui financent la **prime / motivation des enseignants** marqués comme tels (utilisés par la paie).

**Échéanciers — V1.0**
- Par tranches (1re, 2e, 3e…) ou mensuel, avec dates limites.
- Échéancier propre à un élève (arrangement particulier).
- Pénalités de retard configurables — V1.7.

**Réductions — V1.0**
- Réduction générique en montant ou en pourcentage, avec motif et auteur. Modèles prédéfinis : enfants du personnel, fratrie, bourse, exonération de la direction.

**Caisse — V1.0**
- Plusieurs caisses et caissiers.
- Encaissement **hors-ligne**.
- Paiement partiel accepté ; répartition automatique sur les échéances les plus anciennes, modifiable.
- Reçu imprimé automatiquement dans le format choisi par l'école : thermique 58 ou 80 mm, ou petit reçu (A6, A5, ≈ 10 × 7 cm) sur feuille A4 avec traits de découpe ; 1 ou 2 exemplaires (souche) ; QR code de vérification, valable aussi pour un reçu imprimé hors ligne.
- Annulation seulement avec autorisation d'un responsable et motif.
- Clôture de caisse journalière par caissier et par devise, avec écart constaté.

**Impayés — V1.0**
- Liste des élèves en retard, filtrable par classe, frais et tranche.
- Situation financière d'un élève imprimable.
- Relances automatiques par notification (V1.1) ; par SMS / WhatsApp avec crédits (V2).
- Blocage de l'accès aux bulletins ou aux examens en cas de dette : option configurable par l'école, désactivée par défaut (V1.7).

**Dépenses et comptabilité**
- V1.2 : dépenses par catégorie, entrées / sorties, rapports journaliers, mensuels et annuels.
- Les catégories sont reliées dès le départ au plan de comptes **SYSCOHADA**, pour pouvoir activer plus tard la vraie comptabilité (journal, grand livre, budget prévisionnel, rapprochement bancaire — V2) sans reprendre les données.

### 8.5 Paie et ressources humaines — V1.7

- Dossier de l'employé : identité, fonction, diplômes et qualifications, contrats, matricule SECOPE / statut (mécanisé, non payé).
- Paie mensuelle : salaire de base, primes, prime / motivation enseignants (liée aux frais correspondants), avances sur salaire, retenues (absences, avances).
- Fiche de paie PDF, consultable par l'employé dans son espace.
- Congés et permissions — V1.7. Évaluation des enseignants — V2.
- Présence du personnel reliée au module présences (V1.5).

### 8.6 Enseignement, notes et bulletins — V1.2

- Cours par classe avec maxima (sur 10, 20, 40, 80…), pondération ou heures, domaines / branches, attribution enseignant–cours–classe, programme officiel pré-rempli quand disponible.
- Évaluations : interrogations, devoirs, travaux pratiques, examens, repêchage / seconde session, épreuves spéciales (ENAFEP, TENAFEP, Exetat blanc). Pour les écoles techniques : **évaluations d'atelier** (V2).
- Saisie des notes par l'enseignant, le titulaire ou le secrétariat, y compris sur téléphone et hors-ligne.
- Contrôle : date limite de verrouillage, validation par le directeur des études, historique de toute modification, publication aux parents après validation seulement.
- Bulletins : format officiel EPST, calcul automatique des totaux, pourcentages et places, mentions et appréciations automatiques, conduite, taux de présence, QR code d'authenticité, signature électronique du chef d'établissement, PDF téléchargeable par le parent. Deux modes d'impression : bulletin complet, ou notes seules sur le formulaire officiel pré-imprimé.
- Délibération : tableau par classe, règles de réussite configurables, décisions (admis, ajourné, repêchage, réorienté, exclu), palmarès imprimable, statistiques de réussite par classe et par cours.
- Emploi du temps : génération automatique sans conflit, modifiable à la main (V1.4, avec l'aide de l'IA).
- Devoirs publiés pour les élèves (V2).

### 8.7 Présences

- V1.5 : **une seule carte** par élève et par membre du personnel : puce sans contact (NFC) + QR code + photo et informations. Liaison carte ↔ personne en une seconde sur un appareil enregistré (scanner le QR imprimé, poser la carte).
- V1.5 : pointage de deux façons, hors ligne compris : par la **puce**, avec un téléphone Android enregistré (NFC) ou un lecteur **ESP32** au portail (fabrication maison, mémoire tampon en cas de coupure) ; par le **QR code**, avec la caméra de n'importe quel téléphone ou tablette enregistrés (iPhone compris). Pointage des élèves, des enseignants et du personnel.
- Notifications au parent : absence, retard ; alerte après X absences ; justification d'absence envoyée par le parent ; taux de présence sur le bulletin.
- La carte contient un jeton aléatoire, pas le matricule.

### 8.8 Discipline — V1.7

Cote de conduite, sanctions (avertissement, renvoi temporaire, exclusion), convocation des parents, mérites et récompenses, visibles par les parents.

### 8.9 Communication

- V1.0 : annonces de l'école visibles dans le portail.
- V1.1 : notifications push (reçu de paiement, échéance proche, annonce), messages à une classe, calendrier des événements, circulaires PDF, convocations.
- V1.7 : messagerie parent ↔ titulaire et administration (les parents ne peuvent écrire qu'au titulaire et à l'administration), demande de rendez-vous, sondages.
- V2 : SMS et WhatsApp avec crédits achetés par l'école.

### 8.10 Portail parents

- Forme : application web installable (PWA) dès V1.0 ; applications Android et iPhone publiées dans les stores en V2 (même code, empaqueté).
- V1.0 : enfants (toutes écoles), profil de l'enfant, situation des paiements, reçus, échéances à venir, annonces, mise à jour des coordonnées.
- V1.1 : notifications sur l'écran du téléphone, même application fermée ; calendrier, titulaire et enseignants avec contacts.
- V1.5 : présences en direct.
- V1.2 à V1.7 : notes, bulletins (téléchargement PDF), discipline, emploi du temps, documents (attestations), demande de rendez-vous, messages.
- V2 : devoirs, menu de cantine et transport.

### 8.11 Portail élèves — V1.7

Compte à partir d'un niveau configuré par l'école. L'élève voit : notes et bulletins, présences, emploi du temps, devoirs et cours, place dans la classe, enseignants, situation financière, annonces, livres empruntés.

### 8.12 Espace enseignant et titulaire

- V1.7 : voir son horaire, sa fiche de paie, demander un congé.
- V1.2 à V1.7 : ses classes et élèves, prise des présences, saisie des notes, écrire aux parents, demander un congé ; pour le titulaire : vue complète de sa classe (notes, présences, paiements), préparation et vérification des bulletins, cote de conduite, rapport de classe, convocation des parents.
- V2 : publier devoirs et cours.

### 8.13 Tableaux de bord et rapports

- V1.0 : encaissements du jour et du mois par devise, impayés, effectifs par classe, sexe et âge.
- V1.5 : taux de présence. V1.2 : résultats scolaires.
- V2 : comparaison entre années ; tableau consolidé promoteur / coordination.
- Exports PDF, Excel, CSV et impression directe (V1.0 pour les listes financières).
- Rapports officiels EPST : statistiques de fin d'année, listes des candidats ENAFEP / Exetat, palmarès (V2).

### 8.14 Modules supplémentaires

Précisés le 2026-10-13 (détail et découpage : `05` § 6) :

- **Finances de l'école — V1.2** : dépenses avec justificatif et validation, sorties de caisse comprises dans les clôtures, budget prévu et réalisé, entrées / sorties, trésorerie par devise.
- **Abonnements par module — V1.3** : la plateforme vend des modules (prix par module, par élève, par période), facture l'école, la passe en lecture seule si elle ne paie pas.
- **Sites web** : site de la plateforme (V1.3) ; site de chaque école, rempli par elle, à `{code}.mwangazaschool.com/` (V1.7).
- **Emploi du temps — V1.4** : grille horaire, salles, volumes horaires, charges et disponibilités des enseignants, contraintes ; calcul sans conflit par un solveur, retouches à la main, publication (PDF, Portail, enseignants).
- **Intelligence artificielle — V1.4** : Claude aide à l'emploi du temps (contraintes en phrases, explication des conflits), répond aux questions sur les données, rédige des brouillons ; il ne voit que ce que la personne peut voir et ne décide jamais seul.
- **Bibliothèque — V1.6** : catalogue, exemplaires étiquetés, prêt avec bon et date de retour, parent prévenu, rappels, livre perdu ou abîmé facturé à l'élève.
- **Ateliers — V1.6** (écoles techniques) : stock de matières d'œuvre et d'outillage, demande de matériel → validation → achat → réception → retrait à l'atelier, outils prêtés aux élèves ; évaluations d'atelier en V2.
- **V2 et plus tard** : cantine, transport (itinéraires, suivi GPS), internat, boutique (uniformes, fournitures), orientation scolaire, anciens élèves, paiement en ligne Mobile Money.

## 9. Exigences non fonctionnelles

### 9.1 Hors-ligne

- L'application Gestion s'installe (PWA) sur Windows, Android et iPhone et continue de fonctionner sans internet pour : consulter les élèves, encaisser, imprimer les reçus, voir la situation d'un élève, (plus tard) prendre les présences et saisir les notes.
- La synchronisation est automatique au retour du réseau, sans perte ni doublon.
- Chaque appareil voit clairement son état : « à jour », « X opérations en attente », « dernière synchronisation il y a… ».
- La configuration (frais, classes, rôles) se fait en ligne.

### 9.2 Performance et légèreté

- Utilisable sur un téléphone Android d'entrée de gamme et une connexion 3G.
- Portail parents : première visite légère, visites suivantes servies depuis le cache.
- Plus de 5 postes simultanés par école, écoles de 3 000 élèves.

### 9.3 Sécurité et confidentialité

- Isolation stricte des données entre écoles.
- HTTPS partout, mots de passe hachés (Argon2), limitation des tentatives de connexion.
- Journal de toutes les actions sensibles ; historique des modifications financières et des notes ; alertes sur actions suspectes (ex : nombreuses annulations, modification de note après verrouillage).
- Sauvegarde automatique quotidienne, copie hors du serveur principal, restauration à une date donnée ; l'école peut télécharger une copie de ses données.
- Conditions d'utilisation, politique de confidentialité, contrat de traitement des données avec chaque école, consentement photo, suppression des données sur demande.

### 9.4 Expérience utilisateur

- Français et anglais.
- Guide pas à pas à la première connexion de chaque rôle.
- Gros boutons, formulaires courts, recherche d'élève rapide (nom ou matricule).
- Impressions : A4, reçus thermiques 58 et 80 mm, petits reçus sur A4, cartes PVC.

### 9.5 Hébergement

Cloud international, un serveur au départ, budget inférieur à 20 $ par mois pour commencer. Détails dans `03-architecture-technique.md`.

## 10. Réponses aux points « conseille-moi »

| Question | Décision |
|---|---|
| Modèle de distribution | Plateforme en ligne unique + application Gestion installable qui marche hors-ligne. Pas de serveur local dans l'école. |
| Qui paie | Tarif par élève et par an, minimum par école, offre gratuite limitée, essai d'un trimestre. |
| Séparation des données | Une seule base, chaque donnée liée à son école, isolation garantie par le code et des tests (voir architecture). Indispensable pour les parents multi-écoles, les transferts et les réseaux. |
| Enseignant multi-écoles | Oui : un compte unique, un rôle par école. |
| Découpage de l'année | Configurable par école avec modèles prêts. |
| Où va l'argent en ligne | Directement sur le compte de l'école, via un agrégateur. |
| Agrégateur | Oui, le moment venu. |
| Qui paie les SMS | L'école, par crédits. Au début : notifications gratuites seulement. |
| Création du compte parent | Code famille remis par l'école + téléphone + mot de passe. |
| Ordre de développement | Gestion d'abord (c'est elle qui crée les données), portail parents juste après sur le même serveur, dans la même V1. |
| Technologies | Voir `03-architecture-technique.md`. |

## 11. Exemple : ce qu'une école saisit (l'ITIG)

**Rien n'est attendu de l'ITIG** (2026-09-26, redit le 2026-10-02) : Claude crée des données fictives réalistes, et chaque école, l'ITIG comprise, saisit elle-même ses vraies données dans l'application. La liste ci-dessous sert seulement d'exemple de ce qu'une école renseigne.

- Modèles actuels : reçu, fiche d'inscription, bulletin, liste de classe, palmarès.
- Grille des frais 2026-2027 : montants, devises, tranches, dates limites, réductions pratiquées.
- Liste des élèves (Excel si possible), classes, sections et options.
- Qui encaisse, combien de caisses, comment se fait la clôture aujourd'hui.
- Grille salariale, primes, fonctionnement de la motivation des enseignants, avances.
- Découpage de l'année et date de remise des bulletins de la 1re période.
- Logo, nom officiel, cachet, en-tête.
- Matériel disponible : ordinateurs, imprimantes (modèle de l'imprimante thermique), connexion internet, tablettes.

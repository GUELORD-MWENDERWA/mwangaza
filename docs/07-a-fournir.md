# Ce qui manque encore

Liste de tout ce qui manque pour aller jusqu'au bout : maquettes, informations de l'ITIG, décisions à prendre. Cocher au fur et à mesure (`/noter` ou `/document-ecole` le font). Établie le 2026-09-26.

**En attendant, le travail continue avec des données de test** (voir la dernière section) : aucun point ci-dessous ne bloque les tâches 0.2 à 1.7.

## 1. Maquettes manquantes

30 maquettes existent (`maquettes/`). Les écrans ci-dessous n'en ont pas. **Si une maquette n'est pas fournie avant sa tâche, Claude la dessine lui-même dans le système de design (`maquettes/<app>/<nom>.html`, même style) et la montre avant de coder.**

### V1.0 — nécessaires pour le pilote

| # | Écran | App | Réf. | Tâche | Fournie |
|---|---|---|---|---|:-:|
| M1 | Activation de la double authentification : QR code à scanner + 8 codes de secours à imprimer | Gestion | B4 | 1.3 | [ ] |
| M2 | Choix de l'école après connexion (compte dans plusieurs écoles) + changement d'école dans l'en-tête | Gestion | B3 | 1.2, 1.6 | [ ] |
| M3 | Personnel : liste des comptes, créer un compte, attribuer des rôles, désactiver, réinitialiser le mot de passe | Gestion | B1–B3 | 1.2 | [ ] |
| M4 | Mon compte : mot de passe, PIN, double authentification, langue | Gestion | B4–B5, I2 | 1.3 | [ ] |
| M5 | Paramètres de l'école : nom officiel, logo, couleur, en-tête des reçus, devises, seuils d'alerte | Gestion | A1, cahier § 8.1 | 1.5, 1.7 | [ ] |
| M6 | Journal d'audit : qui a fait quoi, filtres par personne, action, date | Gestion | I1 | 1.4 | [ ] |
| M7 | Menu de la Gestion sur téléphone et tablette (moins de 900 px) | Gestion | cahier § 9.4 | 1.6 | [ ] |
| M8 | Pages d'état : accès refusé, page introuvable, école suspendue, session expirée, nouvelle version disponible, stockage local refusé | Gestion, Portail | — | 1.6 | [ ] |
| M9 | Fiche élève : onglets Identité, Famille, Historique (seul l'onglet Finances est dessiné) + modification | Gestion | D2–D4 | 2.2 | [ ] |
| M10 | Fiche famille : code famille, tuteurs, enfants de toutes les écoles, état d'activation du portail, réimprimer le code | Gestion | D4, H1 | 2.2 | [ ] |
| M11 | Fiche d'inscription imprimable (A4, avec code famille) et liste de classe (PDF) | Impression | D5 | 2.4 | [ ] |
| M12 | Accorder une réduction à un élève ; échéancier particulier | Gestion | E3, E4 | 2.5, 2.6 | [ ] |
| M13 | Ouvrir une session de caisse (choix de la caisse) ; caisse avant de choisir un élève ; paiements du jour et recherche d'un reçu à réimprimer | Gestion | F1, F6 | 3.1 | [ ] |
| M14 | Crédits d'élèves (surpaiements après synchronisation) à traiter par le comptable | Gestion | — | 3.6 | [ ] |
| M15 | Reçu d'annulation (80 mm et A4) | Impression | F7 | 3.8 | [ ] |
| M16 | Clôtures de caisse vues par le comptable : historique, écarts, détail | Gestion | F8 | 3.8 | [ ] |
| M17 | Situation financière d'un élève imprimable ; export des impayés (PDF, Excel) | Impression | G1, G2 | 4.1 | [ ] |
| M18 | Changements de coordonnées faits par les parents, à prendre en compte par le secrétariat | Gestion | H5 | 4.4 | [ ] |
| M19 | Portail : se connecter, mot de passe oublié, installer l'application | Portail | H1, H6 | 4.4 | [ ] |
| M20 | Guides de première connexion : caissier, comptable, parent | Gestion, Portail | I3 | 4.5 | [ ] |

### V1.1 — à prévoir avant la semaine 5

Dépenses et rapports entrées / sorties (5.1) · dossier employé et contrats (5.2) · fiche de paie PDF (5.3) · réglages des notifications et relances (5.4) · carte d'élève PDF (5.5) · pénalités, validation d'inscription, documents téléversés (5.6) · messages à une classe, calendrier, circulaires, convocations (5.8) · espace enseignant (5.9). Existent déjà : paie, pointage QR.

### V1.2 — à prévoir avant la semaine 9

Cours, maxima, attribution des enseignants (6.1) · délibération et palmarès (6.4) · présences RFID et du personnel (6.5) · absences et justification par le parent (6.6) · discipline, messagerie, rendez-vous (6.7) · portail élève et espace titulaire (6.8) · transfert et attestations (6.9) · portail parents complet (6.10) · congés, sondages (6.11). Existent déjà : saisie des notes, bulletin (gabarit provisoire), scolarité d'un enfant.

### V2

À dessiner tâche par tâche (7.1 à 7.15) au moment de les commencer.

## 2. Informations de l'ITIG

Déposer les fichiers dans `docs/ecole-pilote/depot/` puis `/document-ecole`. Pour une réponse sans fichier : `/noter …`.

### Pour la V1.0

| # | Information | Tâche | Quand | En attendant | Reçue |
|---|---|---|---|---|:-:|
| I1 | Classes 2026-2027 : sections par niveau (7e A, B, C…), options et sections de la 1re à la 4e | 1.7 | semaine 1 | structure publique + sections inventées | [ ] |
| I2 | Format actuel du matricule | 1.7 | semaine 1 | `ITIG-{AAAA}-{0000}` (maquettes) | [ ] |
| I3 | Calendrier 2026-2027 : périodes, examens, dates ; date de proclamation de la P1 | 1.7, Q6 | semaine 1 | modèle secondaire : 2 semestres, 4 périodes, 2 examens | [ ] |
| I4 | Qui fait quoi : préfet, directeurs des études, directeur de discipline, économe / comptable, caissiers, secrétaires, promoteur ; liste des comptes à créer | 1.2, 4.8 | semaine 1 | un compte fictif par rôle | [ ] |
| I5 | Grille des frais 2026-2027 : types, devise de chaque frais, montants par niveau / option, tranches et dates limites, frais mensuels | 2.5 | semaine 2 | grille des maquettes (minerval en tranches USD, fonctionnement, atelier, motivation mensuelle en FC) | [ ] |
| I6 | Réductions pratiquées (enfants du personnel, fratrie, bourses) et qui les accorde | 2.5 | semaine 2 | modèles du cahier des charges | [ ] |
| I7 | Liste des élèves en Excel (même partielle, pour voir les colonnes) | 2.3 | semaine 2 | ~1 200 élèves fictifs | [ ] |
| I8 | Fiche d'inscription et liste de classe actuelles | 2.4 | semaine 2 | maquettes M11 | [ ] |
| I9 | La caisse aujourd'hui : combien de caisses et de caissiers, qui valide une annulation, comment se fait la clôture, qui fixe le taux du jour et quand | 3.1, 3.8 | semaine 3 | 2 caisses, règles des maquettes, taux 1 $ = 2 850 FC | [ ] |
| I10 | Modèle de reçu actuel (photo) et formulation du montant en lettres | 3.2, Q5 | semaine 3 | reçu des maquettes | [ ] |
| I11 | Imprimante thermique (marque, modèle, papier 80 ou 58 mm) ; ordinateurs, tablettes, navigateur ; connexion internet | 3.2, 4.8 | semaine 3 | 80 mm, Chrome | [ ] |
| I12 | Logo haute qualité (vectoriel si possible) + version noir et blanc ; nom officiel exact ; cachet ; en-tête | 1.5, 3.2 | semaine 3 | logo du site web | [ ] |
| I13 | Code de l'école dans l'adresse : `itig` ? | 1.5 | semaine 1 | `itig` | [ ] |

### Pour la V1.1 et la V1.2

| # | Information | Tâche | Reçue |
|---|---|---|:-:|
| I14 | Grille salariale, primes, règle de répartition de la motivation des enseignants, statut SECOPE, avances, retenues | 5.2, 5.3 | [ ] |
| I15 | Bulletin officiel vierge et rempli (photo ou scan), branches et maxima par classe et option | 6.1, 6.3 | [ ] |
| I16 | Règles de délibération (réussite, repêchage, passage), palmarès | 6.4 | [ ] |
| I17 | Cote de conduite et sanctions pratiquées | 6.7 | [ ] |

## 3. Décisions et comptes (toi)

| # | Sujet | Quand | Fait |
|---|---|---|:-:|
| T1 | **Nom et domaine** (question Q9 de `06-suivi.md`) : `mwangaza.cd` est déjà enregistré, `mwangaza.com` est en vente chez un revendeur. Recommandation : garder **Mwangaza** et prendre **`mwangaza.africa`**, qui semble libre (à confirmer chez le registrar) | maintenant ; domaine acheté avant 4.6 | [ ] |
| T2 | Valider les propositions Q1 à Q8 de `06-suivi.md` (un « OK » suffit, ou corriger) | avant 1.2 | [ ] |
| T3 | Maquettes : les fournir, ou laisser Claude les dessiner (défaut) | maintenant | [ ] |
| T4 | Comptes : VPS, Cloudflare, stockage objet, suivi d'erreurs (Sentry ou GlitchTip) | avant 4.6 | [ ] |
| T5 | Conditions d'utilisation, politique de confidentialité, contrat de traitement des données avec l'ITIG (Claude peut rédiger un brouillon) | avant 4.8 | [ ] |
| T6 | Tarif du pilote ITIG (gratuit pendant l'essai ?) | avant 4.8 | [ ] |

## 4. Données de test utilisées en attendant

Commande `make demo` (créée avec la tâche 1.5, enrichie à chaque tâche) : elle efface et recrée des données **entièrement fictives**, remplacées par les vraies à la tâche 4.8.

- **École `itig`** « ITIG Don Bosco Goma (démo) » : structure publique réelle (7e–8e EB, 1re–4e, 4 options), environ 1 200 élèves et leurs familles aux noms inventés, grille de frais des maquettes, taux 1 $ = 2 850 FC, 2 caisses, historique de paiements pour le tableau de bord.
- **École `volcans`** « Complexe scolaire Les Volcans (fictif) » : petite école pour prouver l'isolation entre écoles et tester une famille qui a des enfants dans les deux écoles.
- **Un compte par rôle** (directeur, comptable, caissier, secrétaire, promoteur, parent, super-admin) avec un mot de passe de développement connu, jamais utilisé en production.

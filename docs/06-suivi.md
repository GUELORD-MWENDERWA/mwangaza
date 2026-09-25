# Suivi du projet

Ce fichier dit **où en est le projet**. Il est mis à jour à chaque étape (début et fin de tâche, décision, document reçu, blocage). Les cases à cocher restent dans `05-plan-de-travail.md` ; ici on garde l'état, l'avancement et le journal.

## État actuel

| | |
|---|---|
| Phase | Préparation terminée — démarrage de la tâche 0.1 |
| Lot | V1.0 — semaine 1 (Socle) |
| Tâche en cours | aucune |
| Prochaine tâche | **0.1** — monorepo, Docker Compose de développement, commandes — plan écrit (`docs/claude/plans/tache-0.1.md`), **en attente de validation** |
| Issue GitHub | #5 |
| Branche | `main`, synchronisée avec GitHub (`GUELORD-MWENDERWA/mwangaza`, privé) |
| Dernière mise à jour | 2026-09-25 |

## Avancement

| Bloc | Fait | Total |
|---|:-:|:-:|
| Avant de coder (toi) | 0 | 4 |
| Semaine 1 — Socle | 0 | 9 |
| Semaine 2 — Élèves et frais | 0 | 7 |
| Semaine 3 — Caisse et hors-ligne | 0 | 8 |
| Semaine 4 — Rapports, portail, production | 0 | 8 |
| **V1.0** | **0** | **32** |
| V1.1 — semaines 5 à 8 | 0 | 9 |
| V1.2 — semaines 9 à 14 | 0 | 11 |
| V2 | 0 | 15 |

Sur GitHub : onglet *Milestones* — V1.0 (36 issues, dont les 4 « avant de coder »), V1.1 (9), V1.2 (11), V2 (15).

## Bloquants et en attente

| Sujet | Attendu de | Bloque |
|---|---|---|
| Documents ITIG (cahier des charges § 11) : grille des frais, liste des élèves Excel, modèle de reçu | ITIG | 2.3, 2.5, 3.2, 4.8 |
| Modèle de l'imprimante thermique | ITIG | 3.2 |
| Date de remise des bulletins de la 1re période 2026-2027 (indice : 8 novembre en 2025) | ITIG | ordre V1.1 / V1.2 — voir Q6 |
| Nom définitif et domaine | toi | 4.6 |
| Comptes VPS, Cloudflare, stockage objet (GitHub : fait) | toi | 4.6, 4.7 |
| Docker absent de la machine (Redis aussi) | toi (installation avec sudo) | mode Docker de 0.1 ; en attendant, développement local sur le PostgreSQL 16 installé |
| Logo haute qualité + version noir et blanc pour le reçu thermique | ITIG | 3.2 |

## Questions ouvertes

À trancher au plus tard pendant la tâche indiquée. Une fois tranchée : déplacer dans le journal.

| # | Question | Tâche | Proposition |
|---|---|---|---|
| Q1 | Le glossaire cite `PaymentSchedule` (échéancier) mais `04-modele-de-donnees.md` n'a pas cette entité : l'échéancier est porté par `FeeRule.schedule_kind`, `InstallmentTemplate` et `StudentCharge`. | 2.5 | Suivre `04` ; l'échéancier particulier = `StudentCharge` avec `source=custom`. |
| Q2 | Le glossaire cite `Receipt`, mais `04` ne définit pas de modèle `Receipt` (le numéro est sur `Payment` et `PaymentCancellation`). | 3.2 | Pas de modèle : le reçu est une vue imprimable du paiement. |
| Q3 | Codes des rôles système : seul `head` (directeur) et `promoter` sont fixés dans le glossaire. | 1.2 | `head`, `accountant`, `cashier`, `secretary`, `promoter`, `teacher`, `parent`. |
| Q4 | Paiement en FC d'un frais en USD : `allocation = received × rate_used` avec un taux à 6 décimales donne 1/2 850 ≈ 0,000351, soit jusqu'à ~10 centimes d'erreur par million de FC. | 2.5, 3.1 | Toujours enregistrer le taux dans le sens USD → CDF (tel que saisi) et diviser en `Decimal` pour FC → USD, arrondi demi supérieur au centime. |
| Q5 | Montant en lettres sur le reçu : formulation des centimes et de la devise. | 3.2 | Reprendre la formulation du reçu actuel de l'ITIG. |
| Q6 | En 2025, l'ITIG a proclamé les résultats de la P1 le 8 novembre. Si 2026 est pareil, la P1 tombe en semaine 7 du projet, avant la V1.2 (semaines 9 à 14). | ordre V1.1 / V1.2 | Garder la caisse (V1.0) en priorité ; P1 2026 encore sur papier ; viser les bulletins de la P2 / 1er semestre avec Mwangaza ; confirmer les dates avec l'ITIG. |
| Q7 | L'organigramme ITIG a 2 directeurs des études, 1 directeur de discipline et 2 chefs d'atelier ; « chef d'atelier » n'est pas dans la liste des rôles du cahier des charges, et on ne sait pas qui joue le rôle de promoteur (communauté salésienne ?). | 1.2 | Rôles système V1.0 inchangés ; chef d'atelier = rôle personnalisé créé par l'école (B2) en attendant le module ateliers (V2) ; demander à l'ITIG qui est « promoteur ». |
| Q8 | Couleur de l'ITIG pour la personnalisation (`School.primary_color`). | 1.5 | `#003C6C` (bleu marine du logo). |

## Journal

Entrée la plus récente en haut. Format : date — titre, puis fait / tests / décisions / suite.

### 2026-09-25 — GitHub, découpage par versions, dossier ITIG, espace de travail de Claude

- **Fait** : premier commit et dépôt GitHub privé `GUELORD-MWENDERWA/mwangaza` ; jalons V1.0, V1.1, V1.2, V2 et 71 issues (une par tâche, #1 à #4 = « avant de coder », #5 = tâche 0.1) ; plan de travail complété jusqu'à la fin : 4 tâches ajoutées pour couvrir tout le cahier des charges (5.8, 5.9, 6.10, 6.11) et section V2 (7.1 à 7.15, ordre à valider) ; dossier ITIG réorganisé (`depot/`, `documents/`, `prive/`, `fiche-itig.md`) ; recherche web sur l'ITIG (logo, adresse, contacts, 4 options, niveaux 7e–8e EB + 1re–4e, organigramme, date de la P1 2025, dégâts de janvier 2025) ; espace de travail `docs/claude/` (plans, recherches, revues) ; skills `tache`, `etat`, `noter`, `document-ecole` reliées à GitHub et à ces dossiers ; plan de la tâche 0.1 écrit.
- **Décisions** : un jalon GitHub par version, une issue par tâche, PR avec `Closes #n` ; `depot/` et `prive/` hors Git ; noms de personnes seulement dans `prive/`.
- **Nouvelles questions** : Q6 (date des bulletins P1), Q7 (rôles réels de l'ITIG), Q8 (couleur de l'école).
- **Suite** : validation du plan 0.1 (Docker, gestionnaire Python, autorisation de commit), puis tâche 0.1.

### 2026-09-25 — Organisation du dossier avant de coder

- **Fait** : dossier réorganisé selon `03-architecture-technique.md` § 3 — `docs/` et `maquettes/` à la racine ; doublons supprimés (anciennes copies des documents, 4 captures identiques, ancien `CLAUDE.md`) ; `CLAUDE.md` fusionné (lien vers les maquettes, règles de suivi, liste des skills) ; `README.md` du projet ; `.gitignore` ; `docs/ecole-pilote/` ; ce fichier de suivi ; 10 skills Claude Code dans `.claude/skills/` ; dépôt Git initialisé sur `main`.
- **Tests** : sans objet (aucun code).
- **Décisions** : suivi dans `docs/06-suivi.md` ; données personnelles réelles de l'ITIG dans `docs/ecole-pilote/prive/`, hors Git.
- **Suite** : premier commit, puis plan de la tâche 0.1.

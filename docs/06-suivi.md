# Suivi du projet

Ce fichier dit **où en est le projet**. Il est mis à jour à chaque étape (début et fin de tâche, décision, document reçu, blocage). Les cases à cocher restent dans `05-plan-de-travail.md` ; ici on garde l'état, l'avancement et le journal.

## État actuel

| | |
|---|---|
| Phase | Préparation — avant la première ligne de code |
| Lot | V1.0 — semaine 1 (Socle) |
| Tâche en cours | aucune |
| Prochaine tâche | **0.1** — monorepo, Docker Compose de développement, commandes (plan à valider avant de créer des fichiers) |
| Branche | `main` — dépôt Git initialisé, aucun commit |
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
| V1.1 — semaines 5 à 8 | 0 | 7 |
| V1.2 — semaines 9 à 14 | 0 | 9 |

## Bloquants et en attente

| Sujet | Attendu de | Bloque |
|---|---|---|
| Documents ITIG (cahier des charges § 11) : grille des frais, liste des élèves Excel, modèle de reçu | ITIG | 2.3, 2.5, 3.2, 4.8 |
| Modèle de l'imprimante thermique | ITIG | 3.2 |
| Date de remise des bulletins de la 1re période | ITIG | ordre V1.1 / V1.2 |
| Nom définitif et domaine | toi | 4.6 |
| Comptes VPS, Cloudflare, stockage objet, GitHub | toi | 0.2 (CI), 4.6, 4.7 |

## Questions ouvertes

À trancher au plus tard pendant la tâche indiquée. Une fois tranchée : déplacer dans le journal.

| # | Question | Tâche | Proposition |
|---|---|---|---|
| Q1 | Le glossaire cite `PaymentSchedule` (échéancier) mais `04-modele-de-donnees.md` n'a pas cette entité : l'échéancier est porté par `FeeRule.schedule_kind`, `InstallmentTemplate` et `StudentCharge`. | 2.5 | Suivre `04` ; l'échéancier particulier = `StudentCharge` avec `source=custom`. |
| Q2 | Le glossaire cite `Receipt`, mais `04` ne définit pas de modèle `Receipt` (le numéro est sur `Payment` et `PaymentCancellation`). | 3.2 | Pas de modèle : le reçu est une vue imprimable du paiement. |
| Q3 | Codes des rôles système : seul `head` (directeur) et `promoter` sont fixés dans le glossaire. | 1.2 | `head`, `accountant`, `cashier`, `secretary`, `promoter`, `teacher`, `parent`. |
| Q4 | Paiement en FC d'un frais en USD : `allocation = received × rate_used` avec un taux à 6 décimales donne 1/2 850 ≈ 0,000351, soit jusqu'à ~10 centimes d'erreur par million de FC. | 2.5, 3.1 | Toujours enregistrer le taux dans le sens USD → CDF (tel que saisi) et diviser en `Decimal` pour FC → USD, arrondi demi supérieur au centime. |
| Q5 | Montant en lettres sur le reçu : formulation des centimes et de la devise. | 3.2 | Reprendre la formulation du reçu actuel de l'ITIG. |

## Journal

Entrée la plus récente en haut. Format : date — titre, puis fait / tests / décisions / suite.

### 2026-09-25 — Organisation du dossier avant de coder

- **Fait** : dossier réorganisé selon `03-architecture-technique.md` § 3 — `docs/` et `maquettes/` à la racine ; doublons supprimés (anciennes copies des documents, 4 captures identiques, ancien `CLAUDE.md`) ; `CLAUDE.md` fusionné (lien vers les maquettes, règles de suivi, liste des skills) ; `README.md` du projet ; `.gitignore` ; `docs/ecole-pilote/` ; ce fichier de suivi ; 10 skills Claude Code dans `.claude/skills/` ; dépôt Git initialisé sur `main`.
- **Tests** : sans objet (aucun code).
- **Décisions** : suivi dans `docs/06-suivi.md` ; données personnelles réelles de l'ITIG dans `docs/ecole-pilote/prive/`, hors Git.
- **Suite** : premier commit, puis premier prompt de `PROMPT-DEMARRAGE.md` (résumé + questions), puis plan de la tâche 0.1.

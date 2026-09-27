# Tâche 2.5.1 — Frais, barèmes, taux de l'année (E1, E2, E5, M5, C1)

**Serveur** — nouvelle app `finance` : `FeeType`, `FeeRule` (portée : école, niveau, option ou classe ; devise parmi celles de l'école ; `schedule_kind`), `InstallmentTemplate` (au moins une tranche, somme = total ; unique = une tranche ; mensuel = une tranche par mois, proposée par l'écran), `ExchangeRate` [I] (nouvelle ligne à chaque correction, motif obligatoire après la première ; déclencheur SQL comme `AuditLog`).
- Services dans `finance/services.py`, audit `finance.*` dans la transaction ; tranches mises à jour par position (identifiants stables pour les `StudentCharge` de la 2.6).
- API : `/api/fee-types/`, `/api/fee-rules/?academic_year=`, `/api/exchange-rates/?academic_year=` ; lecture avec `configure_fees`, `set_exchange_rate` ou `grant_discount` (droits du menu « Frais »), écriture : `configure_fees` / `set_exchange_rate`. Listes de configuration non paginées.
- M5 : `update_school` refuse de retirer une devise utilisée par un barème (`currency_in_use`, 409) ; les paiements s'ajouteront en 3.1.
- C1 : `copy_fees` à la création d'une année (avec `copy_classes_from`, droit `configure_fees` en plus) : barèmes repris, dates décalées d'autant d'années, barème d'une classe rattaché à la classe reprise.
- `make demo` : grille fictive (I5 en attendant) + taux 2 850 FC.

**Écran** `/app/fees` (maquette `frais-baremes`) : types de frais, barèmes du type choisi, éditeur (portée, devise, total, tranches / mensuel / unique, contrôle de la somme), carte « Taux de l'année » avec historique. Case « Reprendre aussi les barèmes » dans « Nouvelle année ». Pas la carte « Réductions types » (2.5.2).

**Décisions** : barème applicable = le plus précis (classe > niveau > option > école), un seul par frais et par portée dans l'année ; écarts avec la maquette tranchés par les documents (devise dans le barème, taux fixe de l'année et non « du jour »).

**Tests** : isolation (liste, détail, modification, lien vers le niveau d'une autre école), 403, somme des tranches, devise non activée, doublon de portée, audit, taux immuable (code et base), M5, copie d'année. Front : somme, découpage mensuel, motif de correction.

**Hors tâche** : `ChangeLog` (3.3), recalcul des dus (2.6), réductions (2.5.2).

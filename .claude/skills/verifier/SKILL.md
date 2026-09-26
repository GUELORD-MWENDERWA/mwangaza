---
name: verifier
description: Contrôler les changements en cours de Mwangaza contre les 9 règles non négociables de CLAUDE.md (isolation des écoles, argent en entiers, paiements immuables, UUID v7 et idempotence, audit, permissions serveur, i18n, pas de nouvelle dépendance, rien en dur pour une école), les conventions de code et le suivi. À utiliser avant chaque commit ou PR, à la fin de chaque tâche, ou quand l'utilisateur demande une vérification, une relecture ou « est-ce que c'est conforme ».
---

# Vérifier la conformité

Périmètre : `git diff main...HEAD` + `git status` (fichiers non suivis compris). Lire les fichiers modifiés, pas seulement le diff, quand le contexte est nécessaire.

## Contrôles

| # | Règle | Comment vérifier |
|---|---|---|
| 1 | **Isolation des écoles** | Tout nouveau modèle hérite de `TenantModel`, sauf entité [G] de `docs/04`. Aucune requête qui contourne le manager scopé ; `all_schools` seulement super-admin / portail. Chaque nouveau modèle, écran ou point d'API a un test à deux écoles qui prouve qu'une école ne peut **ni lire ni modifier** les données de l'autre (exports, rapports, recherche et portail compris). Rien de propre à une école (nom, logo, couleur, options, frais, formats de reçu, codes `itig`) écrit dans le code hors données de démonstration et tests. |
| 2 | **Argent en entiers** | `grep -nE 'FloatField|float\(|parseFloat|Number\(' ` sur les fichiers modifiés touchant des montants → aucun. Champs `*_minor` + `currency`. `rate_used` enregistré sur le paiement. |
| 3 | **Paiements immuables** | Pas d'`UpdateModelMixin` / `DestroyModelMixin`, de `.update(` ni de `.delete(` sur `Payment`, `PaymentAllocation`, `PaymentCancellation`, `CashClosing`, `AuditLog`. Annulation = nouvel enregistrement lié avec motif et permission. |
| 4 | **UUID v7 et idempotence** | Données créables hors-ligne : UUID généré côté client. Écritures de synchronisation : test « même `op_id` deux fois ». |
| 5 | **Audit** | Création / modification / annulation sur finances, notes, paie, rôles, élèves → `AuditLog` écrit et testé. |
| 6 | **Permissions serveur** | Chaque endpoint a une classe de permission avec un code de `docs/04` § 8 ; test 403. Le front ne fait que masquer. |
| 7 | **i18n** | Aucun texte d'interface en dur dans les `.tsx` / `.ts` d'interface (chercher les chaînes françaises entre balises et dans les props `label`, `placeholder`, `title`). Clés présentes en `fr` **et** `en`. Messages d'erreur serveur destinés à l'interface traduisibles. |
| 8 | **Pas de nouvelle dépendance** | Diff de `pyproject.toml` / `requirements*` / `package.json` / `pnpm-lock.yaml` : toute nouvelle dépendance a été expliquée et acceptée par l'utilisateur. |
| 9 | Conventions | Code en anglais, noms du glossaire ; logique dans `services.py` ; front par fonctionnalité (`features/…`) ; client API régénéré si l'OpenAPI a changé. |
| 10 | Périmètre | Rien de V1.1 / V1.2 / V2 codé pendant une tâche V1.0. |
| 11 | Design | Jetons et composants de la skill `design` ; pas de couleur ou taille inventée ; formats de montants via `packages/money`. |
| 12 | Secrets | Aucun `.env`, mot de passe, clé ou jeton ajouté. Aucune donnée personnelle réelle de l'ITIG hors de `docs/ecole-pilote/prive/`. |
| 13 | Tests et qualité | Lint et tests lancés, résultat réel montré. |
| 14 | Suivi | Tâche cochée dans `docs/05`, `docs/06-suivi.md` à jour (état, avancement, journal), décision notée dans `docs/03` § 11 si besoin. |

## Réponse

Tableau `# · règle · ✔ / ✘ / sans objet · preuve (fichier:ligne)`. Pour chaque ✘ : la correction proposée ; corriger directement si c'est mécanique et sans ambiguïté, sinon demander. Ne jamais déclarer « conforme » sans avoir lancé les tests.

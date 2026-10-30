---
name: verifier
description: Contrôler les changements en cours de Mwangaza contre les 9 règles non négociables de CLAUDE.md (isolation des écoles, argent en entiers, paiements immuables, UUID v7 et idempotence, audit, permissions serveur, i18n, pas de nouvelle dépendance, rien en dur pour une école), les conventions de code et le suivi. À utiliser avant chaque commit ou PR, à la fin de chaque tâche, ou quand l'utilisateur demande une vérification, une relecture ou « est-ce que c'est conforme ».
---

# Vérifier la conformité

Périmètre : `git diff main...HEAD --stat` + `git status`, puis les passages utiles (`git diff main...HEAD -- <fichier>`, `grep -n`) ; pas de lecture intégrale des fichiers déjà vus pendant la tâche (« Économie de tokens » de `CLAUDE.md`).

## Contrôles

| # | Règle | Comment vérifier |
|---|---|---|
| 1 | **Isolation des écoles** | Tout nouveau modèle hérite de `TenantModel`, sauf entité [G] de `docs/04`. Aucune requête qui contourne le manager scopé ; `all_schools` seulement super-admin / portail, dans sa portée de base (`use_all_schools` seulement console, administration, tâches de la plateforme et lecture filtrée qui doit voir toutes les écoles : unicité, recherche par code, rôles d'un compte ; Row Level Security, S.6). Toute tâche Celery pose sa portée. Chaque nouveau modèle, écran ou point d'API a un test à deux écoles qui prouve qu'une école ne peut **ni lire ni modifier** les données de l'autre (exports, rapports, recherche et portail compris). Rien de propre à une école (nom, logo, couleur, options, frais, formats de reçu, codes `itig`) écrit dans le code hors données de démonstration et tests. |
| 2 | **Argent en entiers** | `grep -nE 'FloatField|float\(|parseFloat|Number\(' ` sur les fichiers modifiés touchant des montants → aucun. Champs `*_minor` + `currency`. `rate_used` enregistré sur le paiement. |
| 3 | **Paiements immuables** | Pas d'`UpdateModelMixin` / `DestroyModelMixin`, de `.update(` ni de `.delete(` sur `Payment`, `PaymentAllocation`, `PaymentCancellation`, `CashClosing`, `AuditLog`. Annulation = nouvel enregistrement lié avec motif et permission. Seule exception : `apps/schools/deletion.py` (espace d'essai ou de démonstration supprimé, jamais un espace réel : la base elle-même le refuse). |
| 4 | **UUID v7 et idempotence** | Données créables hors-ligne : UUID généré côté client. Écritures de synchronisation : test « même `op_id` deux fois ». |
| 5 | **Audit** | Création / modification / annulation sur finances, notes, paie, rôles, élèves → `AuditLog` écrit et testé. |
| 6 | **Permissions serveur** | Chaque endpoint a une classe de permission avec un code de `docs/04` § 8 ; test 403. Le front ne fait que masquer. |
| 7 | **i18n** | Aucun texte d'interface en dur dans les `.tsx` / `.ts` d'interface (chercher les chaînes françaises entre balises et dans les props `label`, `placeholder`, `title`). Clés présentes en `fr` **et** `en`. Messages d'erreur serveur destinés à l'interface traduisibles. Textes du serveur : `django.po` complet et compilé (`make messages`, test `core/tests/test_translations.py`). |
| 8 | **Pas de nouvelle dépendance** | Diff de `pyproject.toml` / `requirements*` / `package.json` / `pnpm-lock.yaml` : toute nouvelle dépendance a été expliquée et acceptée par l'utilisateur. |
| 9 | Conventions | Code en anglais, noms du glossaire ; logique dans `services.py` ; front par fonctionnalité (`features/…`) ; client API régénéré si l'OpenAPI a changé. |
| 10 | Périmètre | Rien d'une version suivante (`05`) codé pendant la tâche. |
| 11 | Design | Jetons et composants de la skill `design` (bleu uniforme, brume, soleil levant rare ; aucun beige ni gris chaud ; livre de marque) ; pas de couleur ou taille inventée (`apps/gestion/design.test.ts` vert) ; chaque écran nouveau ou changé a sa maquette (390 et 1440 px, `captures.mjs` sans ✘) et marche vraiment aux trois tailles dans l'application (`make apercu ecran=…` : 390, 820, 1440 px, `rapport.json` vide, mise en page qui s'adapte) ; formats de montants via `packages/money`. |
| 12 | Secrets | Aucun `.env`, mot de passe, clé ou jeton ajouté. Aucune donnée personnelle réelle de l'ITIG hors de `docs/ecole-pilote/prive/`. |
| 13 | Tests et qualité | Lint et tests lancés une fois à la fin, résultat réel montré. Tests utiles seulement (isolation, permissions, argent, audit, règles métier) ; aucun test d'isolation, de permission, d'argent ou d'audit supprimé. Pas de N+1 dans les nouvelles listes, listes paginées. |
| 14 | Suivi | Tâche cochée dans `docs/05`, `docs/06-suivi.md` à jour (état, compteur, journal de 3 à 5 lignes), décision notée dans `docs/03` seulement si c'en est une vraie. |
| 15 | Autres `.md` | Chaque nouvel écran, API, commande ou donnée de `make demo` du diff figure dans `docs/claude/reference.md` (commandes en détail, adresses), le tableau « Commandes » de `CLAUDE.md` pour une commande, **et** `A-FAIRE.md` § 11 ; `07` § 4 décrit ce que crée `make demo` ; écart à une maquette noté dans `maquettes/README.md` ; action de l'utilisateur dans `A-FAIRE.md` « Maintenant » ; skills et README à jour si une façon de faire a changé (liste complète : `CLAUDE.md`, « Suivi du projet »). Un `.md` oublié = ✘, à corriger dans la PR. |

## Réponse

Quelques lignes, reprises telles quelles dans la section « Tests » de la PR : les règles concernées en une ligne (✔ avec la preuve la plus parlante, ex. le test d'isolation), puis chaque ✘ avec sa correction ; les règles sans objet ne sont pas listées. Corriger directement ce qui est mécanique et sans ambiguïté, sinon demander. Ne jamais déclarer « conforme » sans avoir lancé les tests.

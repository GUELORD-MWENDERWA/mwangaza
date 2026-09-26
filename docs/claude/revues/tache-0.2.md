# Revue — Tâche 0.2 (2026-09-26)

Périmètre : branche `tache/0.2-qualite` par rapport à `docs/decisions-q1-q11` (PR #78) : configuration ruff, ESLint, Prettier, Vitest, pre-commit, GitHub Actions, `Makefile`, documents. Aucun modèle, aucun écran, aucune fonction métier.

| # | Règle | Résultat | Preuve |
|---|---|---|---|
| 1 | Isolation des écoles | sans objet | aucun modèle ni point d'API ; les tests Vitest vérifient que le proxy de développement garde le sous-domaine de l'école (`changeOrigin: false`) |
| 2 | Argent en entiers | sans objet | aucun montant |
| 3 | Paiements immuables | sans objet | — |
| 4 | UUID v7 et idempotence | sans objet | — |
| 5 | Audit | sans objet | — |
| 6 | Permissions serveur | sans objet | aucun endpoint ajouté |
| 7 | i18n | sans objet | aucun texte d'interface ; les titres de tests sont en français (pas affichés à l'utilisateur) |
| 8 | Pas de nouvelle dépendance non acceptée | à valider par la fusion | outils de développement seulement, prévus par la stack (ruff, pre-commit, ESLint, Prettier, Vitest) ou nécessaires à leur fonctionnement (`typescript-eslint`, `@eslint/js`, `globals`, `eslint-config-prettier`, `eslint-plugin-react-hooks`, `typescript@~6.0` pour ESLint) ; chacun expliqué dans `docs/claude/plans/tache-0.2.md` et la PR ; `eslint-plugin-react-refresh`, `jsdom`, Testing Library écartés |
| 9 | Rien en dur pour une école | ✔ | seul `itig.localhost` apparaît, dans des commentaires de développement déjà existants |
| 10 | Conventions | ✔ | commits en français ; commandes derrière `make` ; configuration dans `pyproject.toml` et `frontend/` |
| 11 | Périmètre | ✔ | rien au-delà de 0.2 ; tests de composants (jsdom) reportés en 1.6 |
| 12 | Design | sans objet | — |
| 13 | Secrets | ✔ | aucun secret ajouté ; les mots de passe de la CI (`mwangaza`) sont ceux de la base jetable de GitHub Actions, identiques à `docker-compose.dev.yml` ; hooks `no-env-file` et `no-private-key` testés (échec attendu) |
| 14 | Tests et qualité | ✔ | `make lint` OK ; `make test` : 7 pytest passés, types OK, 8 Vitest passés ; `make build` OK ; `make api` sans différence ; fautes volontaires détectées par ESLint (variable inutilisée, hook conditionnel), ruff (import inutilisé) et Vitest (`changeOrigin: true` → 2 échecs) ; `pre-commit run --all-files` : tout passe, aucun fichier modifié |
| 15 | Suivi | ✔ | 0.2 cochée dans `docs/05` ; `docs/06-suivi.md` (état, avancement, journal) ; 3 lignes au journal des décisions de `docs/03` ; `CLAUDE.md` et `A-FAIRE.md` § 11–12 |

## Points relevés pendant la revue

- `pre-commit run --all-files` a d'abord reformaté `maquettes/outils/maquettes.py` avec les réglages par défaut de ruff (hors du `backend`, sans sa configuration) : changement annulé, hooks Python limités à `backend/` comme `make lint-back`.
- `make help` affichait « make Makefile » sur chaque ligne depuis que le `Makefile` inclut `.env` (`grep` recevait deux fichiers) : corrigé avec `grep -h`.
- Résultat de GitHub Actions : vérifié sur la PR (voir le journal de `docs/06-suivi.md`).

# Revue — Tâche 1.1 (2026-09-26)

Périmètre : branche `tache/1.1-core-tenant` par rapport à `main` : apps `core` (UUID v7, `BaseModel`, `TenantModel`, `TenantManager`, école courante, `TenantMiddleware`, `Money`, erreurs de l'API, `make demo`) et `schools` (`School` minimal, admin, `GET /api/school/`) ; app de test `tests.sample` ; règles de travail avec GitHub (documents et skills).

| # | Règle | Résultat | Preuve |
|---|---|---|---|
| 1 | Isolation des écoles | ✔ | `School` est [G] (`04` § 1). `TenantModel` : lecture limitée à l'école courante, erreur sans école, écriture / suppression / déplacement / lien vers une autre école refusés (`apps/core/models.py`, `tenancy.py`) ; 25 tests à deux écoles (`apps/core/tests/test_tenancy.py`) et 27 pour le middleware (`test_middleware.py` : 10 requêtes, 17 lectures du sous-domaine), dont « l'école B ne voit jamais les données de A ». `/api/school/` : chaque école voit la sienne, `POST` refusé (`apps/schools/tests/test_api.py`). `all_schools` : seulement pour lire l'école d'une ligne liée dans `_check_links` (`apps/core/models.py:94`). Aucun code d'école dans le code hors `apps/schools/demo.py` et les tests |
| 2 | Argent en entiers | ✔ | `Money` refuse `float`, `bool`, `Decimal`, texte (`test_money.py`) ; taux `Decimal` obligatoire ; conversion Q4 (division pour CDF → USD, arrondi demi supérieur) testée dans les deux sens ; aucun `FloatField` / `float(` |
| 3 | Paiements immuables | sans objet | aucun modèle de paiement |
| 4 | UUID v7 et idempotence | ✔ | `uuid7()` (RFC 9562, croissant, 32 bits aléatoires) pour toutes les clés ; `is_uuid7()` prêt pour valider les identifiants des appareils (3.3) ; pas encore d'écriture de synchronisation |
| 5 | Audit | sans objet | `AuditLog` arrive en 1.4 ; aucune donnée financière, de notes, de paie ou de rôles |
| 6 | Permissions serveur | ✔ (exception justifiée) | `/api/school/` est public comme `/api/health/` : il ne donne que le code et le nom de l'école du sous-domaine, affichés sur l'écran de connexion avant toute authentification ; `GET` seulement (test 405). Le reste de l'API reste fermé par défaut (`IsAuthenticated`) |
| 7 | i18n | ✔ (à suivre) | aucun écran ; messages d'erreur du serveur en `gettext` avec un `code` stable que l'interface traduira ; libellés des modèles en `gettext_lazy`. Pas encore de fichiers de traduction du serveur (outils `gettext` absents de la machine) : l'admin Django affiche les libellés des modèles en anglais ; prévu avec les premiers textes du serveur montrés tels quels (2.4) |
| 8 | Pas de nouvelle dépendance | ✔ | `pyproject.toml` : seulement `ignore = ["RUF012"]` (réglage de ruff) ; `uv.lock` et `pnpm-lock.yaml` inchangés |
| 9 | Rien en dur pour une école | ✔ | `itig` et `volcans` seulement dans `apps/schools/demo.py` (données de démonstration) ; domaine de la plateforme dans `SCHOOL_BASE_DOMAINS` (réglage) |
| 10 | Conventions | ✔ | code en anglais, glossaire (`School`) ; pas de logique métier dans les vues ; schéma OpenAPI régénéré (`make api`) ; commits en français |
| 11 | Périmètre | ✔ | rien au-delà de 1.1 ; `/api/school/` (utile à 1.6) et `make demo` (prévu en 1.5) avancés pour pouvoir essayer le middleware |
| 12 | Design | sans objet | aucun écran |
| 13 | Secrets | ✔ | aucun secret ; noms des écoles de démonstration publics ou inventés |
| 14 | Tests et qualité | ✔ | `make lint` OK ; `make test` : 160 pytest passés (153 nouveaux), types et 8 Vitest OK ; `make build` OK ; `make api` à jour. Erreurs volontaires détectées : manager sans filtre (9 échecs), liens non vérifiés (4), suppression sans contrôle (1), changement d'école (1), école suspendue servie (1), `bulk_create` sans contrôle (3), sous-domaines réservés (4), arrondi bancaire (2), CDF → USD par 1/taux (1), UUID v7 sans compteur (3). Essai réel : `make migrate`, `make demo`, `make dev-local` ; `itig.localhost:5173/api/school/` → itig, `volcans…` → volcans, `inconnue…` → 404, école suspendue → 403 |
| 15 | Suivi | ✔ | 1.1 cochée dans `docs/05` ; `docs/06-suivi.md` (état, avancement, journal) ; journal des décisions de `docs/03` ; `CLAUDE.md` et `A-FAIRE.md` (`make demo`, adresse de test) ; `07` § 4 |

## Points relevés pendant la revue

- ruff RUF012 signalait les listes de configuration de Django (`Meta.ordering`, admin, serializers) : règle désactivée dans `pyproject.toml`, avec la raison.
- `tests.sample` a besoin d'une migration : Django ne sait pas créer sans migration un modèle qui pointe vers une app migrée (`schools`).
- À la tâche 1.2 : le modèle d'utilisateur change (`AUTH_USER_MODEL`), la base de développement devra être recréée (aucune vraie donnée) ; à annoncer dans `A-FAIRE.md` à ce moment-là.

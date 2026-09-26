# Revue — Tâche 1.2 : app `accounts` (skill `verifier`)

Périmètre : `git diff main...tache/1.2-accounts` et fichiers nouveaux. Date : 2026-09-26.

| # | Règle | Résultat | Preuve |
|---|---|:-:|---|
| 1 | Isolation des écoles | ✔ | `Role` hérite de `TenantModel` ; `User` et `Membership` sont [G] comme dans `04` (toujours lus avec l'école explicite : `views.py` `StaffViewSet.get_queryset`, `services.get_school_access`). Rôle d'une autre école refusé jusque dans la base de code (`signals.py`, `test_models.py::test_role_of_another_school_is_refused`). Tests à deux écoles pour chaque point d'API : `test_roles_api.py` (liste, détail, modification, suppression → invisibles / 404), `test_staff_api.py` (liste, détail, modification → 404 ; rôle d'une autre école refusé ; numéro connu ailleurs : rien de l'autre école dans la réponse, rien modifié là-bas), `test_me.py` (droits seulement dans l'école de l'adresse), `test_permissions.py` (directeur d'une école sans droit dans l'autre). Rien de propre à une école dans le code : « Chef d'atelier », `itig`, `volcans` seulement dans `demo.py` et les tests. |
| 2 | Argent en entiers | sans objet | aucun montant |
| 3 | Paiements immuables | sans objet | |
| 4 | UUID v7 et idempotence | ✔ / sans objet | `User`, `Role`, `Membership` héritent de `BaseModel` (UUID v7) ; rien de créable hors ligne |
| 5 | Audit | reporté (1.4) | changements de rôles et de comptes : `AuditLog` n'existe qu'en 1.4 ; les services (`create_role`, `update_role`, `delete_role`, `add_staff_member`, `update_staff_member`) y seront branchés en 1.4 (noté dans `services.py` et le journal) |
| 6 | Permissions serveur | ✔ | `HasSchoolPermission` + `required_permission = "roles.manage"` sur `/api/roles/` et `/api/staff/` ; `/api/me/` : compte connecté, ses propres données. Tests 403 pour chaque méthode sans le code (`test_*_api.py::test_without_roles_manage_everything_is_refused`), sans connexion, appartenance ou compte désactivé, super-admin sans rôle (`test_permissions.py`) |
| 7 | i18n | ✔ | messages du serveur en `gettext` (texte source anglais, codes stables `last_role_manager`, `role_in_use`… traduits par l'interface) ; rôles système sans nom en base, traduits par l'interface ; aucun écran |
| 8 | Pas de nouvelle dépendance | ✔ | `pyproject.toml`, `uv.lock`, `package.json`, `pnpm-lock.yaml` inchangés ; Argon2 (nouvelle dépendance) reporté à 1.3 |
| 9 | Conventions | ✔ | code en anglais, glossaire (`head`, `study_director`…) ; logique dans `services.py` ; schéma OpenAPI régénéré (`make api`, `--fail-on-warn`) |
| 10 | Périmètre | ✔ | rien de V1.1 et plus ; TOTP, mot de passe oublié, limitation des tentatives laissés à 1.3 |
| 11 | Design | ✔ | pas d'écran ; maquette M3 corrigée (plus d'« Autres écoles », `03` § 4 prime), capture refaite |
| 12 | Secrets | ✔ | aucun `.env`, aucune clé ; mot de passe `mwangaza-demo` des comptes fictifs de développement (pas un secret, `make demo` refusé hors `DEBUG`, comme le mot de passe de la base de développement) : signalé dans « À valider » ; numéros `+243 0…` jamais attribués à une vraie personne ; noms inventés, absents de `prive/` |
| 13 | Tests et qualité | ✔ | `make lint` OK ; `make test` : 305 pytest passés (145 nouveaux), types et 8 Vitest OK ; 12 erreurs glissées volontairement (permission toujours accordée, appartenance désactivée acceptée, rôle d'une autre école, dernier gestionnaire, personnel de toutes les écoles, noms d'un compte existant écrasés, permission en trop pour le caissier, longueur des numéros, rôle système supprimable, écoles désactivées listées, rôles de toutes les écoles, super-admin avec droits) : toutes détectées. Essai réel `make dev-local` à travers Vite : connexion `0000001001`, `/api/me/`, `/api/roles/`, `/api/staff/`, ajout d'un compte, caissière 403, directeur de l'ITIG 403 sur Volcans |
| 14 | Suivi | ✔ | `05` coché (1.7 : écrans M3 et rôles ajoutés), `06` (état, avancement, journal), `03` (7 décisions), `04` § 1 et § 8, `07` (M2, M3, § 4), `CLAUDE.md`, `A-FAIRE.md` (ligne 10, `make reset-db`, adresses, dépannage), skill `backend` |

## Points relevés pendant la tâche

- `00` était lu comme un préfixe international même devant `0` : les numéros fictifs `000…` étaient refusés. `00` n'est international que suivi d'un chiffre non nul (aucun indicatif ne commence par 0) ; test ajouté.
- Le comptage des membres (GROUP BY) faisait perdre l'ordre des rôles (avertissement de pagination) : ordre redonné.
- Le schéma OpenAPI ne disait pas qu'un rôle de l'école a un `code` vide : champ déclaré (énumération + vide) pour le futur client TypeScript.
- API navigable : après « Log in » sans `next`, Django renvoyait vers `/accounts/profile/` (inexistant) → `/api/me/` en développement ; le formulaire HTML de `/api/staff/` montre maintenant les champs d'ajout.

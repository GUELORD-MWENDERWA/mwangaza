# Plan — Tâche 1.4 : app `audit` (journal d'audit)

Issue #10 · branche `tache/1.4-audit` · date : 2026-09-26.

Références : I1 (`02`), `01` § 9.3, `03` § 8, `04` § 1 (`AuditLog [T] [I]`), règle 5 de
`CLAUDE.md`, maquette M6 `gestion/journal-audit` (à valider). Skill : `backend`. Aucune nouvelle
dépendance.

## Ce qui est construit (API ; l'écran M6 arrive avec les écrans des paramètres, en 1.7)

### Modèle `AuditLog` [T] [I]

| Champ | Contenu |
|---|---|
| `school` | école du journal (`TenantModel`) |
| `action` | code stable `<domaine>.<événement>` (`roles.updated`, `staff.password_reset`…) ; liste unique dans `apps/audit/actions.py` |
| `actor` | qui ; vide pour une action du système |
| `impersonated_by` | super-admin connecté « en tant qu'école » : champ créé maintenant, rempli en 1.5 |
| `entity_type`, `entity_id`, `entity_label` | sur quoi : `accounts.role`, `accounts.membership`… ; nom de l'objet **au moment de l'action** (un renommage ne réécrit pas l'histoire) |
| `before`, `after` | champs changés seulement (JSON) |
| `ip`, `user_agent` | adresse et navigateur de la requête (colonne « Appareil » de M6) |
| `created_at` | quand (UUID v7 : l'ordre des `id` suit l'ordre des entrées) |

- `device` (appareil de caisse) et l'heure de l'appareil pour les actions faites hors ligne :
  ajoutés en 3.3, avec `Device`.
- **Immuable** : `save()` d'une ligne existante, `delete()`, `QuerySet.update()` et `.delete()`
  lèvent une erreur ; en plus, un déclencheur PostgreSQL refuse `UPDATE` et `DELETE` sur la
  table (même par SQL direct ou par erreur de code). Admin en lecture seule, API en lecture
  seule.
- **Jamais de secret** : `record()` refuse les clés `password`, `totp_secret`,
  `recovery_codes`… dans `before` / `after` (erreur de programmation, vue par les tests) ; les
  actions sur le mot de passe et la double authentification ne portent aucune valeur.

### Utilitaire d'enregistrement

- `apps.audit.services.record(action, entity, *, actor, before=None, after=None, label=None)` :
  une entrée dans l'école courante, dans la transaction de l'action (l'action annulée n'a pas
  d'entrée ; l'action faite a toujours la sienne).
- `apps.audit.services.changes(before, after)` : ne garde que les champs qui ont changé ; rien
  de changé → pas d'entrée.
- Adresse IP et navigateur : lus une fois par requête par `AuditMiddleware` (variable de
  contexte, comme l'école courante) ; vides dans une commande ou une tâche Celery.
  `client_ip()` passe dans `apps/core/http.py`, partagé avec la limitation des tentatives (un
  seul endroit à changer en 4.6 pour l'adresse réelle derrière le proxy).

### Où va une entrée

- **Ce qui se passe dans une école** (rôles, comptes du personnel, connexion à son adresse) :
  dans cette école.
- **Ce qui change un compte** (mot de passe, double authentification, codes de secours, par la
  personne ou par le support) : dans **chaque école où la personne a une appartenance active**
  — le compte est unique et donne accès à chacune. L'entrée ne dit jamais où l'action a été
  faite (rien sur les autres écoles).

### Actions enregistrées dès maintenant (services de 1.2 et 1.3)

| Domaine | Actions |
|---|---|
| `auth` | `auth.login` (dans l'école de l'adresse, si la personne y est active ; `after.second_factor` : `totp`, `recovery_code`, `trusted_device` ou vide) |
| `account` | `password_changed`, `totp_enabled`, `totp_changed` (nouveau téléphone), `totp_disabled`, `recovery_codes_renewed`, `totp_reset` (support, administration Django) |
| `roles` | `created`, `updated` (nom, permissions avant / après), `deleted` |
| `staff` | `added` (rôles, nouveau compte ou non), `roles_changed`, `deactivated`, `reactivated`, `account_changed` (noms, téléphone), `password_reset` (mot de passe provisoire, sans valeur), `totp_reset` |

Pas d'entrée : `make demo` (préparation du système, pas l'action d'une personne), changement de
langue, déconnexion, essais ratés (déjà dans `LoginFailure`, hors des écoles).

### API

- `GET /api/audit/` : liste paginée (50), la plus récente en premier ; filtres `actor`,
  `action`, `domain`, `entity` (historique d'un objet), `since`, `until` (dates, heure de Goma),
  `search` (nom de l'objet). `GET /api/audit/{id}/` : détail.
- Permission `audit.view` (directeur, promoteur) + double authentification (déjà dans
  `TOTP_PERMISSIONS`).
- Acteur : `{id, last_name, middle_name, first_name}` ; pour le support Mwangaza, `actor` vide et
  `by_support: true` (M6 affiche « Support Mwangaza »).
- Pas d'export maintenant : l'export Excel (M6, « l'export lui-même est tracé ») demande une
  bibliothèque Excel, qui arrive en 2.4 (listes de classe) → ajouté à la 2.4.

## Tests prévus

- Modèle : immuable (save, delete, update, delete en masse, SQL direct), école obligatoire,
  isolation (lecture limitée à l'école courante), clés secrètes refusées.
- Utilitaire : école courante, acteur, IP et navigateur de la requête, `changes`, transaction
  annulée = pas d'entrée.
- Chaque service de 1.2 / 1.3 écrit la bonne entrée, avec avant / après ; compte : une entrée par
  école active, pas dans une école où la personne est désactivée ; connexion : méthode du second
  facteur.
- Aucun secret dans tout le journal après tous les parcours (mot de passe provisoire, nouveau
  mot de passe, clé TOTP, codes de secours).
- API : `audit.view` exigé (403), double authentification exigée, isolation (liste et détail
  d'une autre école → rien / 404), filtres, ordre, pagination, support masqué, pas d'écriture
  (POST, PATCH, DELETE → 405).
- Admin : lecture seule.

## Documents

`03` (§ 8, journal des décisions), `04` (§ 1 `AuditLog`), `05` (1.4 cochée ; 1.7 écran M6 ;
2.4 export ; 3.3 appareil et heure de l'appareil ; 1.5 `impersonated_by`), `06`, `07` (M6),
`CLAUDE.md` (adresse `/api/audit/`), `A-FAIRE.md`, skill `backend` (comment écrire une entrée),
note de la maquette M6 si besoin.

## Risques

- Oublier une action sensible dans une tâche suivante : la skill `backend` et `verifier` le
  rappellent ; chaque tâche teste son audit.
- Le déclencheur empêche aussi de nettoyer la base à la main : voulu. `make reset-db` efface le
  volume entier, les tests utilisent des transactions : pas touchés.

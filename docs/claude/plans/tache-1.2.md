# Plan — Tâche 1.2 : app `accounts` (User, Role, Membership, permissions)

Issue GitHub : #8 · Branche : `tache/1.2-accounts` (partie de `main`) · Statut : en cours depuis le 2026-09-26

Références : `02` B1–B3 ; `01` § 6.2, § 8.2 ; `03` § 4 (multi-écoles), § 8 (sécurité) ; `04` § 1 (`User`, `Membership`, `Role`), § 8 (permissions) ; maquettes `gestion/personnel-comptes` (M3), `gestion/roles-permissions`, `gestion/choix-ecole` (M2). Skill `backend`. Rien ne bloque (`06`, `07` : I4 → comptes fictifs, un par rôle).

## But

Savoir **qui** se connecte (un compte par numéro de téléphone, valable dans toutes les écoles) et **ce qu'il a le droit de faire dans chaque école** (rôles de l'école, codes de permissions), vérifié par le serveur sur chaque point d'API.

## Ce qui est construit

| Élément | Où | Détail |
|---|---|---|
| `User` [G] | `apps/accounts/models.py` | remplace l'utilisateur de Django (`AUTH_USER_MODEL`). `phone` (identifiant, E.164, unique), `last_name` (nom), `middle_name` (post-nom), `first_name` (prénom), `language` (`fr` / `en`), `is_active`, `is_platform_admin` (super-admin : seul accès à l'administration Django), `must_change_password` (mot de passe provisoire ; changement imposé à la connexion en 1.3). E-mail et TOTP arrivent avec leur usage (1.3) |
| Numéro de téléphone | `apps/accounts/phone.py` | `0971234567`, `+243 97 123 45 67`, `00243…` → `+243971234567` ; indicatif par défaut `243` (réglage de la plateforme) ; 9 chiffres après `+243` (et pays voisins) ; sans nouvelle dépendance |
| `created_by` | `apps/core/models.py` (`BaseModel`) | sur tous les modèles, comme prévu dans `04` ; rempli par les services |
| Codes de permissions et rôles système | `apps/accounts/roles.py` | les 16 codes et les 9 rôles de `04` § 8, dans le code (pas d'école) |
| `Role` [T] | `apps/accounts/models.py` | `code` (rôle système : `head`… ; vide pour un rôle créé par l'école), `name` (vide pour un rôle système : l'interface affiche son nom traduit ; l'école peut le renommer, ex. « Préfet des études »), `permissions` (liste de codes). Unicité par école du code et du nom |
| `Membership` [G] | `apps/accounts/models.py` | `user`, `school`, `roles`, `is_active` ; unique (`user`, `school`). Refus en base de code d'un rôle d'une autre école (signal `m2m_changed`) |
| 9 rôles système copiés à la création d'une école | `apps/accounts/services.py`, signal | toute création (admin, `make demo`, tests, super-admin en 1.5) |
| Permission serveur | `apps/accounts/permissions.py` | `HasSchoolPermission` : connecté, école du sous-domaine, appartenance active, un rôle qui porte le code demandé. Le super-admin n'a aucun droit dans une école sans rôle (connexion « en tant qu'école » tracée en 1.5) |
| `GET /api/me/` | `apps/accounts/views.py` | le compte, ses écoles (choix de l'école, M2) et, dans l'école de l'adresse, ses rôles et permissions (menu de la 1.6) |
| `/api/roles/` | idem | `roles.manage` : liste (avec nombre de comptes), création d'un rôle de l'école, renommer, changer les permissions ; suppression d'un rôle de l'école seulement s'il n'est plus attribué ; rôle système jamais supprimé |
| `/api/staff/` | idem | `roles.manage` : liste des comptes de l'école, ajout par téléphone (nouveau numéro → compte + mot de passe provisoire affiché une fois ; numéro connu → ajouté à l'école sans nouveau mot de passe, sans rien révéler des autres écoles), changer les rôles, désactiver / réactiver. Pas de suppression |
| Règle de sécurité | `services.py` | aucun changement ne peut laisser l'école sans un compte actif qui gère les rôles (M3 : « impossible de se retirer soi-même le dernier rôle de directeur ») |
| Erreurs de l'API | `apps/core/errors.py` | toutes les erreurs non liées à un champ au format `{code, detail}` (`permission_denied`, `not_authenticated`, `not_found`…) ; erreurs métier des services (`BusinessError`) |
| Connexion de l'API navigable | `config/urls.py` | en `DEBUG` seulement : pour essayer `/api/me/`, `/api/roles/`, `/api/staff/` avant l'écran de connexion (1.3 : vraie connexion, limitation des tentatives, TOTP) |
| Admin Django | `apps/accounts/admin.py` | comptes (création, modification) ; rôles et appartenances en lecture seule (les changements passent par l'API et ses règles) |
| `make demo` | `apps/accounts/demo.py` | un compte par rôle à l'ITIG, 3 à Volcans, un enseignant dans les deux écoles, un super-admin ; rôle personnalisé « Chef d'atelier » à l'ITIG ; mot de passe de développement commun |
| `make reset-db` | `Makefile` | nouveau modèle d'utilisateur → la base de développement déjà migrée doit être recréée : efface la base (et celle des tests), puis migrations et données fictives |

## Tests prévus (pytest)

- **Téléphone** : formats locaux et internationaux, espaces et tirets, `00`, refus (lettres, trop court, trop long, 8 ou 10 chiffres après `+243`).
- **User** : création, super-admin, identifiant unique, recherche par numéro local, droits d'administration seulement pour le super-admin.
- **Rôles système** : une école créée → 9 rôles avec exactement les permissions du tableau de `04` § 8 (tableau recopié dans le test) ; relançable ; copies indépendantes d'une école à l'autre.
- **Isolation** (écoles `alpha` et `beta`) : liste, détail, modification, suppression des rôles et comptes de l'autre école → invisibles / 404 ; rôle d'une autre école refusé dans une appartenance (API et base) ; un directeur d'une école n'a aucun droit dans l'autre ; ajout d'un numéro connu ailleurs : aucune donnée de l'autre école dans la réponse, rien de modifié là-bas.
- **Permissions** : sans connexion, sans rôle, rôle sans le code, appartenance ou compte désactivé, super-admin sans rôle → refus ; avec le code → accès ; adresse sans école → 404.
- **Règles** : dernier gestionnaire des rôles (se retirer le rôle, désactiver, retirer la permission au rôle) ; rôle système non supprimable ; rôle attribué non supprimable ; nom de rôle en double ; permission inconnue ; compte déjà dans l'école ; noms exigés pour un nouveau numéro ; mot de passe provisoire affiché une fois et changement imposé.
- **Erreurs** : format `{code, detail}` pour 403 / 404 / 405.
- **Admin** : pages des comptes, rôles et appartenances ouvertes par le super-admin.
- **`make demo`** : comptes et rôles, enseignant dans les deux écoles, mot de passe valide, relançable sans doublon.

## Décisions (à faire valider par la fusion)

- Un rôle système n'a pas de nom en base : l'interface le traduit à partir de son code ; l'école peut le renommer.
- Une école ne voit jamais les autres écoles d'une personne (la maquette M3 montrait « Autres écoles » et « déjà un compte à C.S. Les Volcans ») : `03` § 4 prime sur la maquette.
- Une école ne modifie pas le compte lui-même (nom, téléphone, mot de passe) : il peut être partagé avec une autre école. Nom et téléphone : 1.3 (Mon compte, M4) ; « Nouveau mot de passe » et « Réinitialiser la double auth. » : 1.3.
- Gérer les comptes du personnel = `roles.manage` (pas de code à part).
- Aucun changement ne laisse l'école sans gestionnaire des rôles.
- Écrans « Comptes du personnel » et « Rôles et permissions » : aucune tâche ne les prévoit ; proposés en 1.7 avec les autres écrans d'administration de l'école.
- Mots de passe : hachage par défaut de Django pour l'instant ; Argon2 (nouvelle dépendance à demander) avec la connexion en 1.3 ; les mots de passe existants seront convertis à la connexion suivante.

## Risques

- Nouveau modèle d'utilisateur : `make migrate` échoue sur une base déjà migrée (`InconsistentMigrationHistory`) → `make reset-db` une fois (données fictives seulement). Idem pour la base de test réutilisée par `make test`.
- Audit des changements de rôles : `AuditLog` n'existe qu'en 1.4 ; les services de 1.2 y seront branchés en 1.4.

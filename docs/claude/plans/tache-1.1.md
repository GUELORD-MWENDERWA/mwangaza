# Plan — Tâche 1.1 : app `core` (TenantModel, TenantManager, TenantMiddleware, UUID v7, Money)

Issue GitHub : #7 · Branche : `tache/1.1-core-tenant` (partie de `main`) · Statut : en cours depuis le 2026-09-26

Références : `03` § 4 (multi-écoles), § 5.2 (UUID v7), § 6 (argent) ; `04` conventions, § 1 (`School`), § 4 (`Currency`, règle Q4) ; skills `backend` et `argent`. Aucun écran, aucune maquette. Rien ne bloque (`06`, `07`).

## But

Le socle de l'isolation des écoles et de l'argent, sur lequel toutes les tâches suivantes s'appuient : une donnée d'école ne peut être ni lue, ni modifiée, ni reliée depuis une autre école, même par erreur de code.

## Ce qui est construit

| Élément | Où | Détail |
|---|---|---|
| `uuid7()`, `is_uuid7()` | `apps/core/ids.py` | RFC 9562 : horodatage en millisecondes, compteur de 42 bits (ordre croissant dans la même milliseconde), 32 bits aléatoires. Même algorithme que `uuid.uuid7()` de Python 3.14 ; Python 3.12 ne l'a pas → écrit ici, sans dépendance. `is_uuid7()` servira à valider les identifiants créés hors ligne (3.3) |
| `BaseModel` (abstrait) | `apps/core/models.py` | `id` UUID v7, `created_at`, `updated_at`. `created_by` arrive en 1.2 avec `User` |
| `TenantModel` (abstrait) | `apps/core/models.py` | `school` (FK `schools.School`, `PROTECT`, sans accès inverse depuis l'école) ; managers `objects` (`TenantManager`) et `all_schools` |
| `TenantManager` | `apps/core/tenancy.py` | filtre sur l'école courante ; **lève `SchoolNotSetError`** sans école |
| Garde-fous d'écriture | `TenantModel.save()`, `delete()`, `bulk_create()` | école remplie depuis l'école courante ; refus (`CrossSchoolError`) : écrire ou supprimer une ligne d'une autre école, changer l'école d'une ligne (un transfert = une copie, Q10), relier une ligne à une ligne d'une autre école (clé étrangère) |
| École courante | `apps/core/tenancy.py` | `contextvars` ; `get_current_school()`, `use_school(school)` pour les tâches Celery, les commandes et les tests |
| `TenantMiddleware` | `apps/core/middleware.py` | sous-domaine de `SCHOOL_BASE_DOMAINS` (`mwangaza.school` en production, `localhost` en dev et en test) → école ; sous-domaines réservés (`www`, `parents`, `admin`, `api`…) et hôte sans sous-domaine → pas d'école (portail, super-admin, santé) ; école inconnue → 404 `school_not_found` ; suspendue → 403 `school_suspended` |
| `Money`, `Currency` | `apps/core/money.py` | montant entier + devise (`USD` 2 décimales, `CDF` 0) ; refus de `float`, `bool`, `Decimal` ; opérations seulement entre mêmes devises ; `convert()` selon Q4 (taux USD → CDF ; CDF → USD par division en `Decimal`) ; arrondi demi supérieur ; `from_major("150.25", USD)` refuse les décimales en trop |
| `School` (minimal) | `apps/schools/models.py` | `code` (sous-domaine : minuscules, chiffres, tirets, 2 à 30 caractères, pas un nom réservé ; contrôlé aussi par la base), `name`, `status` (`trial`, `active`, `suspended`). Les autres champs de `04` § 1 arrivent avec leur tâche (1.5 : logo, couleur, suspension ; 1.7 : matricule ; 2.5 : devises) |
| Admin `School` | `apps/schools/admin.py` | pour le super-admin en développement (liste, recherche, statut) |
| `GET /api/school/` | `apps/schools/views.py` | public : code et nom de l'école du sous-domaine ; servira à l'écran de connexion (1.6) ; 404 sans école |
| `make demo` | `apps/core/management/commands/demo.py`, `apps/schools/demo.py` | écoles `itig` « ITIG Don Bosco Goma (démo) » et `volcans` « Complexe scolaire Les Volcans (fictif) » ; relançable ; refusé hors `DEBUG`. Prévu en 1.5 dans `07` § 4 : avancé pour que l'utilisateur puisse essayer le middleware |

Format des erreurs de l'API : `{"code": "…", "detail": "…"}` ; le `code` est stable, l'interface affiche son propre texte traduit à partir du `code` (i18next). `detail` passe par `gettext` (texte source en anglais) ; les fichiers de traduction du serveur arriveront avec les premiers textes du serveur montrés tels quels (PDF, 2.4).

## Tests prévus (pytest)

- **UUID v7** : version et variante, horodatage ≈ maintenant, 10 000 valeurs uniques et croissantes, ordre gardé si l'horloge recule, débordement du compteur, `is_uuid7`.
- **Money** : construction (refus de `float`, `bool`, devise inconnue), addition / soustraction / comparaison, refus entre devises, `from_major` / `to_major`, conversion USD → CDF et CDF → USD avec arrondi demi supérieur (cas limites 0,5), taux `float` ou nul refusé, conversion vers la même devise.
- **Isolation** (modèles de test `Note` et `Comment` dans une app réservée aux tests) : lecture sans école → erreur ; école B ne voit pas les lignes de A (liste, `get`, `count`, relation inverse) ; B ne peut ni modifier (`save`, `update`), ni supprimer (`delete`), ni déplacer, ni relier une ligne de A (objet chargé ou seulement son identifiant), ni en créer pour A, y compris par `bulk_create` ; `all_schools` voit tout ; école remplie automatiquement.
- **Middleware** : `itig.localhost` → école itig ; `volcans.localhost` → volcans (jamais les données d'itig) ; hôte inconnu → 404 ; école suspendue → 403 ; `localhost`, `testserver`, `parents.localhost` → pas d'école ; port ignoré ; majuscules ignorées ; école courante remise à zéro après la requête.
- **School** : code valide / invalide / réservé, unicité, contrainte en base.
- **`/api/school/`** : chaque école voit la sienne, 404 sans école, schéma OpenAPI valide.
- **`make demo`** : deux écoles, relançable sans doublon, refusée hors `DEBUG`.

## Décisions prises (couvertes par les documents)

- Contrôle « l'utilisateur a un rôle dans cette école » : pas dans le middleware (DRF authentifie dans la vue) ; permission DRF en 1.2 / 1.3.
- Pas de `Model.objects.all()` au niveau d'une classe (exécuté au chargement, sans école → erreur) : `get_queryset()` dans les vues, `queryset=Model.objects` (le manager) dans les champs DRF. Noté dans la skill `backend`.
- `QuerySet.update()` ne passe pas par `save()` : il reste limité à l'école courante, mais ne vérifie pas les clés étrangères ; les services utilisent `save()` pour les liens.

## Risques

- 1.2 remplacera le modèle d'utilisateur de Django (`AUTH_USER_MODEL`) : la base de développement déjà migrée devra être recréée à ce moment-là (aucune vraie donnée). À annoncer dans `A-FAIRE.md` en 1.2.
- Vérification des clés étrangères : une requête par lien non chargé à chaque `save()` ; négligeable à l'échelle d'une école.

---
name: backend
description: Créer ou modifier un modèle, un service, un serializer, un endpoint ou une migration Django dans Mwangaza en respectant l'isolation des écoles (TenantModel), les UUID v7, l'audit, les permissions serveur, l'OpenAPI et les tests obligatoires (isolation entre deux écoles, permission refusée). À utiliser pour tout travail dans backend/ — apps core, accounts, schools, students, finance, portal, notifications, sync, audit.
---

# Backend Django conforme

Références : `docs/04-modele-de-donnees.md` (entités, [T] / [G] / [I], permissions § 8), `docs/03-architecture-technique.md` § 4 (multi-écoles), § 6 (argent), § 8 (sécurité). Emplacements et commandes : « Commandes » de `CLAUDE.md`, détail dans `docs/claude/reference.md`.

## Modèle

- Vérifier dans `04` si l'entité est **[T]** (hérite de `TenantModel`, champ `school`), **[G]** (globale : `User`, `School`, `Membership`, `PushSubscription`, `SchoolNetwork` — `Student`, `Family`, `Guardian` sont **[T]** : une copie par école, décision Q10) ou **[I]** (immuable).
- Hériter de `apps.core.models.TenantModel` ([T]) ou `BaseModel` ([G]) : clé primaire UUID v7 (`apps.core.ids.uuid7`), `created_at`, `updated_at`, `created_by` (rempli par le service avec `actor`).
- Index composés **commençant par `school`** ; unicité portée par école (ex. `matricule`, `receipt_number`, `Device.prefix`) via `UniqueConstraint(fields=["school", …])`.
- Argent : `*_minor` en `BigIntegerField` + `currency` (`CharField(3)`) ; taux en `DecimalField(…, decimal_places=6)`. Jamais `FloatField`. Voir skill `argent`.
- **[I]** (`Payment`, `PaymentAllocation`, `PaymentCancellation`, `CashClosing`, `AuditLog`) : `save()` refuse la mise à jour d'une ligne existante, `delete()` lève une erreur, `QuerySet.update()` et `.delete()` aussi (modèle : `apps/audit/models.py`) ; déclencheur PostgreSQL qui refuse `UPDATE` et `DELETE` (migration `audit.0001`) ; admin en lecture seule ; aucun endpoint de modification ni de suppression.
- Noms en anglais, selon le glossaire de `CLAUDE.md`.

## Requêtes

- Manager par défaut `TenantManager` : filtre sur l'école courante, **lève `SchoolNotSetError`** sans école. Ne jamais le contourner.
- École courante : posée par `TenantMiddleware` (sous-domaine) dans `request.school` ; ailleurs (tâche Celery, commande, test), `with use_school(school):` (`apps.core.tenancy`).
- `TenantModel.save()`, `delete()` et `bulk_create()` remplissent l'école et lèvent `CrossSchoolError` pour une ligne d'une autre école, un changement d'école (transfert = copie) ou une clé étrangère vers une ligne d'une autre école. `QuerySet.update()` ne vérifie pas les clés étrangères : passer par `save()` pour un lien.
- **Jamais `Model.objects.all()` au niveau d'une classe** (s'exécute au chargement, sans école → erreur) : `get_queryset()` dans les vues, `queryset=Model.objects` (le manager, sans `.all()`) dans les champs DRF.
- Réponse en flux (`StreamingHttpResponse`, gros export) : l'école courante n'existe plus quand le flux est lu ; construire les lignes avant, ou `use_school` dans le générateur.
- `all_schools` seulement pour le super-admin et l'API du portail familles, et toujours filtré explicitement (ex. enfants de la famille de l'utilisateur).
- `Membership` est [G] : toujours filtré avec l'école explicite (`school=request.school`). Un M2M d'un modèle [G] vers un modèle [T] passe par le manager de l'école courante (lecture) ; refuser un lien vers une autre école par un signal `m2m_changed` (exemple : `apps/accounts/signals.py`). Un refus levé dans ce signal annule la transaction en cours.
- Portail : un compte parent peut être relié à des familles de plusieurs écoles (`Family.primary_user`) ; ne renvoyer que ces familles et leurs enfants, chacun avec les données de son école.
- Rien de propre à une école dans le code (l'ITIG n'est que l'école d'exemple) : ce qui varie d'une école à l'autre vient de `School` ou de `School.settings`.
- Rien de propre à la plateforme non plus : son nom, son logo, ses couleurs et son contact viennent de `PlatformSettings.load()` (`apps/core/models.py`) ; dans un gabarit (PDF, page servie par Django) : `{{ platform.name }}`, déjà dans le contexte ; dans un texte traduit : `_("%(platform)s support") % {"platform": …}` ou une formule neutre (« le support de la plateforme »). `core/tests/test_platform.py` refuse le nom dans les traductions et les gabarits.

## Service (`services.py`)

- Toute la logique métier ici, pas dans les vues ni les serializers. Fonctions avec arguments explicites (`school`, `actor`, `device`…).
- `transaction.atomic` ; `select_for_update` pour les séquences (matricule, numéro de reçu côté serveur, `ChangeLog.seq`).
- **Audit** : toute création / modification / annulation sur finances, notes, paie, rôles et élèves écrit un `AuditLog`, **dans la transaction de l'action** :
  - nouvelle action → `apps/audit/actions.py` (code `<domaine>.<événement>`) ;
  - `apps.audit.services.record(Action.X, objet, actor=actor, before=…, after=…, label=…)` : journal de l'école courante ; adresse IP et navigateur viennent de la requête (`AuditMiddleware`) ;
  - `before` / `after` : seulement ce qui a changé (`audit.changes(avant, après)` ; rien de changé → pas d'entrée) ; jamais de mot de passe, de code ni de clé (`record` refuse les clés `password`, `secret`…) ;
  - `label` : nom de l'objet au moment de l'action (un renommage ne réécrit pas l'histoire) ;
  - changement du compte d'une personne (mot de passe, double authentification) : `accounts.services._audit_account` (journal de chaque école où elle est active) ; par le support (console, administration) : `accounts.services.support_*`, qui écrivent aussi au journal de la plateforme (`_audit_support`) ;
  - session support « en tant qu'école » (A3) : rien à faire, `record()` remplit `impersonated_by` d'après la requête (`AuditMiddleware`), seulement dans le journal de l'école de la session ;
  - identité de l'école (noms, couleur, logo, fuseau, devises, suspension) : passer par `apps.schools.services.update_school` / `save_school`, jamais `school.save()` dans une vue.
  - action du super-admin sur la plateforme, hors de toute école (console : identité, écoles, comptes, appareils ; écran « Journal » de la console) : `audit.record_platform(PlatformAction.X, objet, actor=…, before=…, after=…)` → `PlatformAuditLog` (journal de la plateforme, mêmes règles) ; identité de la plateforme : `apps.core.services.update_platform`.
- Entité descendue sur les appareils (élèves, classes, frais, échéances, soldes) : écrire une ligne `ChangeLog` (voir skill `hors-ligne`).
- Entité créable hors-ligne : accepter l'UUID fourni par le client, opération idempotente par `op_id`.

## Endpoint

- ViewSet DRF fin : queryset issu du manager scopé, serializer, appel du service. `get_queryset()` renvoie `Model.all_schools.none()` si `getattr(self, "swagger_fake_view", False)` (génération du schéma, sans école).
- Permission serveur **sur chaque endpoint** avec un code de `04` § 8 (ex. `finance.collect_payment`) : hériter de `apps.accounts.views.SchoolViewSet` (ou `permission_classes = [HasSchoolPermission]`) et poser `required_permission = "…"`. Droits de l'utilisateur dans l'école : `apps.accounts.permissions.school_access(request)`. Lecture ouverte à tout le personnel de l'école, sans code (annonces de la plateforme) : `HasSchoolAccess` ; console de la plateforme : `IsPlatformAdmin` (404 ailleurs qu'à `admin.<domaine>`). Nouveau code → `apps/accounts/roles.py` (+ rôles système qui doivent l'avoir, migration de données pour les écoles existantes, tableau de `04` § 8 et de `test_system_roles.py`) et le signaler ; code sensible (argent, notes, réglages, audit) → aussi dans `TOTP_PERMISSIONS` (double authentification exigée, vérifiée par `HasSchoolPermission` : `totp_required`).
- Droits pendant une session support : `school_access(request)` les donne déjà (tous sauf la caisse, `accounts/support.py`) ; un nouveau droit qui déplace de l'argent → aussi dans `SUPPORT_EXCLUDED_PERMISSIONS`.
- Connexion : jamais de `login()` hors de `apps/accounts/login.py` (connexion en étapes ; administration Django : `admin_site.py`, mêmes fonctions) ; un point d'API qui vérifie un code ou un mot de passe passe par `login.counting_failures(request, user)` (limitation des tentatives). Vue sans compte connecté qui écrit : hériter de `AuthView` (CSRF vérifié).
- Annoter pour drf-spectacular (`extend_schema`, types de réponse), puis régénérer le client `frontend/packages/api`. Nouveau point d'API → « Adresses en développement » de `docs/claude/reference.md` et § 11 de `A-FAIRE.md` ; nouveau modèle dans `make demo` → ligne `make demo` de `reference.md`, de `A-FAIRE.md` § 11 et `docs/07-a-fournir.md` § 4 (même PR).
- Pagination sur les listes ; recherche élève < 2 s sur 3 000 élèves (index adaptés, pas de N+1 : `select_related` / `prefetch_related`).
- Erreur sur un champ (règle métier d'un service) : lever la `ValidationError` de Django avec le chemin du champ (`ValidationError({"terms.0.ends_on": ValidationError(msg, code="outside_year")})`) : l'API répond comme pour une saisie refusée. **Vérifier avant de modifier l'objet** (un refus ne doit pas laisser un objet à moitié changé).
- Listes de configuration (années, niveaux, options, classes d'une année) : `pagination_class = None` ; les autres listes restent paginées (50) avec des filtres côté serveur.
- Erreurs métier : le service lève `apps.core.errors.BusinessError(ApiError(code, detail, statut))` ; l'API répond `{"code": …, "detail": …}` (`ErrorSerializer` pour le schéma), comme pour 403 / 404 / 405. `code` stable, traduit par l'interface ; `detail` en `gettext`. **Tout nouveau texte du serveur** (`detail`, `verbose_name`, admin, PDF, Excel) : `make messages`, traduire dans `backend/locale/fr/LC_MESSAGES/django.po` (rien de vide ni « fuzzy »), `make messages` de nouveau pour compiler ; sinon `core/tests/test_translations.py` échoue. Erreurs de saisie : format DRF `{champ: [messages]}`.

## Migrations

- `makemigrations <app> --name <description>` ; ne jamais modifier une migration déjà appliquée ailleurs.
- Données de référence (rôles système, modèles d'année) : migration de données ou service appelé à la création de l'école.

## Tests (factory_boy, pytest-django) — obligatoires

1. **Isolation** : fixtures `school` (`alpha.localhost`) et `other_school` (`beta.localhost`) de `backend/conftest.py`, fabriques `tests.factories` (`SchoolFactory`, `UserFactory`, `MembershipFactory(school=…, roles=["head"])`) ; comptes `head`, `cashier` (école alpha), `other_head` (beta) ; appels `api(user, host="beta.localhost").get/post/patch/delete(…)` (session passée par la double authentification ; `api(user, mfa=False)` : sans elle) ; `platform_admin` et `admin_client` (administration Django, double authentification comprise) ; fichiers des tests dans un dossier temporaire (`MEDIA_ROOT`, automatique) ; `enable_totp(user)` et `totp_code(secret)` de `tests.factories` ; depuis l'école B (`HTTP_HOST="beta.localhost"`), la ressource de A n'apparaît pas dans la liste et renvoie 404 en détail, modification et action. Modèles d'essai du socle : app `tests.sample` (tests seulement).
2. **Permission** : sans le code → 403 ; avec → succès.
3. **Règles métier** du service (cas nominal, limites, erreurs).
4. **Audit** écrit quand l'action est sensible : action, acteur, objet, avant / après ; aucune entrée si l'action est refusée ou ne change rien (exemples : `apps/accounts/tests/test_audit.py`).
5. **Immutabilité** pour les modèles [I] ; **idempotence** (même `op_id` deux fois → une seule écriture, même réponse) pour les écritures de synchronisation.

Avant de rendre la main : lancer ruff et pytest, puis la skill `verifier`.

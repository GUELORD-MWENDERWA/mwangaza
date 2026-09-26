---
name: backend
description: Créer ou modifier un modèle, un service, un serializer, un endpoint ou une migration Django dans Mwangaza en respectant l'isolation des écoles (TenantModel), les UUID v7, l'audit, les permissions serveur, l'OpenAPI et les tests obligatoires (isolation entre deux écoles, permission refusée). À utiliser pour tout travail dans backend/ — apps core, accounts, schools, students, finance, portal, notifications, sync, audit.
---

# Backend Django conforme

Références : `docs/04-modele-de-donnees.md` (entités, [T] / [G] / [I], permissions § 8), `docs/03-architecture-technique.md` § 4 (multi-écoles), § 6 (argent), § 8 (sécurité). Emplacements et commandes : sections « Commandes » de `CLAUDE.md` (fixées en tâche 0.1).

## Modèle

- Vérifier dans `04` si l'entité est **[T]** (hérite de `TenantModel`, champ `school`), **[G]** (globale : `User`, `School`, `Membership`, `PushSubscription`, `SchoolNetwork` — `Student`, `Family`, `Guardian` sont **[T]** : une copie par école, décision Q10) ou **[I]** (immuable).
- Clé primaire UUID v7 (utilitaire de `apps/core`) ; `created_at`, `updated_at`, `created_by`.
- Index composés **commençant par `school`** ; unicité portée par école (ex. `matricule`, `receipt_number`, `Device.prefix`) via `UniqueConstraint(fields=["school", …])`.
- Argent : `*_minor` en `BigIntegerField` + `currency` (`CharField(3)`) ; taux en `DecimalField(…, decimal_places=6)`. Jamais `FloatField`. Voir skill `argent`.
- **[I]** (`Payment`, `PaymentAllocation`, `PaymentCancellation`, `CashClosing`, `AuditLog`) : `save()` refuse la mise à jour d'une ligne existante, `delete()` lève une erreur ; admin en lecture seule ; aucun endpoint de modification ni de suppression.
- Noms en anglais, selon le glossaire de `CLAUDE.md`.

## Requêtes

- Manager par défaut `TenantManager` : filtre sur l'école courante, **lève une erreur** sans école. Ne jamais le contourner.
- `all_schools` seulement pour le super-admin et l'API du portail familles, et toujours filtré explicitement (ex. enfants de la famille de l'utilisateur).
- Portail : un compte parent peut être relié à des familles de plusieurs écoles (`Family.primary_user`) ; ne renvoyer que ces familles et leurs enfants, chacun avec les données de son école.
- Rien de propre à une école dans le code (l'ITIG n'est que l'école d'exemple) : ce qui varie d'une école à l'autre vient de `School` ou de `School.settings`.

## Service (`services.py`)

- Toute la logique métier ici, pas dans les vues ni les serializers. Fonctions avec arguments explicites (`school`, `actor`, `device`…).
- `transaction.atomic` ; `select_for_update` pour les séquences (matricule, numéro de reçu côté serveur, `ChangeLog.seq`).
- **Audit** : toute création / modification / annulation sur finances, notes, paie, rôles et élèves écrit un `AuditLog` (acteur, appareil, action, entité, avant / après, IP, `impersonated_by`).
- Entité descendue sur les appareils (élèves, classes, frais, échéances, soldes) : écrire une ligne `ChangeLog` (voir skill `hors-ligne`).
- Entité créable hors-ligne : accepter l'UUID fourni par le client, opération idempotente par `op_id`.

## Endpoint

- ViewSet DRF fin : queryset issu du manager scopé, serializer, appel du service.
- Permission serveur **sur chaque endpoint** avec un code de `04` § 8 (ex. `finance.collect_payment`). Nouveau code → l'ajouter aux rôles système et le signaler.
- Annoter pour drf-spectacular (`extend_schema`, types de réponse), puis régénérer le client `frontend/packages/api`.
- Pagination sur les listes ; recherche élève < 2 s sur 3 000 élèves (index adaptés, pas de N+1 : `select_related` / `prefetch_related`).
- Erreurs métier : codes stables et messages traduisibles (i18n), pas de texte en dur destiné à l'interface.

## Migrations

- `makemigrations <app> --name <description>` ; ne jamais modifier une migration déjà appliquée ailleurs.
- Données de référence (rôles système, modèles d'année) : migration de données ou service appelé à la création de l'école.

## Tests (factory_boy, pytest-django) — obligatoires

1. **Isolation** : deux écoles ; depuis l'école B, la ressource de A n'apparaît pas dans la liste et renvoie 404 en détail, modification et action.
2. **Permission** : sans le code → 403 ; avec → succès.
3. **Règles métier** du service (cas nominal, limites, erreurs).
4. **Audit** écrit quand l'action est sensible.
5. **Immutabilité** pour les modèles [I] ; **idempotence** (même `op_id` deux fois → une seule écriture, même réponse) pour les écritures de synchronisation.

Avant de rendre la main : lancer ruff et pytest, puis la skill `verifier`.

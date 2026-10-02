# Tâche 5.2.2 — Écran « Identité de la plateforme » dans la console

**Serveur**
- `apps/audit` : `PlatformAuditLog` [G] [I] (journal de la plateforme, sans école ; immuable comme `AuditLog`, déclencheur PostgreSQL) + `PlatformAction` (`platform.updated`, `platform.logo_changed`, `platform.icon_changed`) ; `record_platform()`. L'écran du journal de la plateforme viendra en 5.4.
- `apps/core/services.py` : `update_platform(actor, **champs)` — verrou, enregistrement, journal (seulement ce qui change), ancien fichier effacé après la transaction.
- `/api/console/platform/` (GET, PATCH), `…/logo/` et `…/icon/` (POST, DELETE) : `IsPlatformAdmin` (adresse de la console, super-admin, double authentification) ; GET avec les 5 dernières modifications.
- Administration Django : identité en lecture seule (dépannage), lien vers la console.

**Console** : entrée « Identité » du menu, `/identity` : nom, nom court, logo, icône, couleurs (aperçu : bouton, menu sombre, icône de l'écran d'accueil), support, mentions légales ; dernières modifications. Après enregistrement : identité relue (`["platform"]`).

**Maquette** : `maquettes/console/identite-plateforme.html` dessinée par Claude (règle « maquette manquante ») + captures.

**Tests** : API réservée (403 / 404 ailleurs / 200), PATCH journalisé (avant / après, rien si rien ne change), couleur illisible refusée, icône non carrée refusée, logo retiré → fichier effacé, journal immuable ; admin en lecture seule. Front : un test (enregistrement + erreur du serveur sous le champ).

**Risques** : `entity_id` texte (la ligne de la plateforme a la clé 1, pas un UUID).

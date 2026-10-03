# Tâche 5.4.1 — Console : comptes

**Serveur** (`apps/accounts`) : `console_serializers.py`, `ConsoleAccountViewSet` (`/api/console/accounts/`, `IsPlatformAdmin`) : liste paginée (recherche : chiffres du téléphone ou noms), fiche (écoles et rôles, familles du portail, double auth, dernières connexions, derniers changements), `PATCH` noms / téléphone / actif, `password/`, `totp-reset/`. Familles lues en une requête pour la page (pas de N+1).
**Journal** : `PlatformAction` `account.changed`, `account.deactivated`, `account.reactivated`, `account.password_reset`, `account.totp_reset`, écrits par les services du support (`services.support_*`, aussi pour l'administration Django) en plus du journal de chaque école.
**Console** : `features/accounts/AccountsPage.tsx` (`/accounts`), `AccountPage.tsx` (`/accounts/<id>`), menu « Comptes » ; maquette `maquettes/console/comptes.html` + captures.

**Règles** :
- un compte super-admin est listé mais ne se change pas dans la console (ligne de commande) : 400 ;
- mot de passe provisoire seulement pour un compte du personnel (au moins une école active) : le portail refuse un mot de passe provisoire ; un parent qui l'a oublié reçoit un nouveau code famille de son école (4.4) ;
- double auth réinitialisée seulement si activée ; désactiver = plus de connexion nulle part.

**Tests** (`apps/accounts/tests/test_console_accounts.py`) : 403 / 404 hors super-admin ou hors console ; recherche dans deux écoles sans N+1 ; mot de passe et double auth → journal de la plateforme et de chaque école ; refus super-admin et parent seul ; désactivation qui bloque la connexion. Front : un test de la fiche (actions masquées selon le compte).

**Risques** : changer le téléphone d'un compte = son identifiant de connexion (unicité vérifiée, journalisé).

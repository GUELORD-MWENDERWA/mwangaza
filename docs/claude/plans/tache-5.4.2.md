# Tâche 5.4.2 — Console : appareils, sessions support, journal de la plateforme

**Serveur** (super-admin seulement, `IsPlatformAdmin`, introuvable à l'adresse d'une école)
- `apps/sync` : `/api/console/devices/` (toutes les écoles, recherche appareil / compte / école, `state=active|revoked`, paginée) et `<id>/revoke/` → `services.revoke_device` dans l'école de l'appareil (journal de l'école) + `PlatformAction.DEVICE_REVOKED` (journal de la plateforme), verrou, idempotent.
- `apps/accounts/support.py` : `sessions()` reconstitue les sessions support depuis le journal des écoles (`support.started` / `support.ended`, même école et même super-admin, dans l'heure) : fin, état (ouverte, fermée, expirée), nombre d'actions de la session ; deux sous-requêtes, pas de N+1. Pas de nouveau modèle. `/api/console/support-sessions/` (recherche école, paginée).
- `apps/audit` : `/api/console/audit/` — journal de la plateforme, filtres `domain`, `since`, `until`, `search` (nom de l'objet), paginé.

**Console** : menu « Appareils » (`/devices`) et « Journal » (`/journal`, onglets « Actions de la console » et « Sessions support » `/journal/support`) ; « Déconnecter » après confirmation ; liens vers la fiche de l'école ou du compte.
**Maquettes** (manquantes, dessinées d'après `console/comptes`) : `console/appareils`, `console/journal` + captures.

**Tests** : 403 pour un directeur et sans double authentification, 404 à l'adresse d'une école (3 API) ; appareils des deux écoles listés, déconnexion → appareil révoqué, session fermée, une entrée au journal de **son** école seulement + journal de la plateforme, deuxième clic sans nouvelle entrée ; sessions : ouverte puis fermée, expirée (service, `now`), actions comptées seulement dans l'école de la session ; journal : filtres domaine, période, recherche ; requêtes bornées. Front : déconnexion après confirmation.

**Risques** : appariement ouverture / fermeture (réouverture dans l'heure : la fermeture précède la nouvelle ouverture) ; `make api` après les vues.

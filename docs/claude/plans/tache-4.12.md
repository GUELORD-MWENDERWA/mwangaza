# Tâche 4.12 — Portail : connexion fiable (issue #155)

**Causes trouvées dans le code** (Q13 ; pas de téléphone sous la main : essai réel dans « À tester toi-même ») :
1. « Rester connecté » décoché : cookie sans durée, perdu dès qu'on quitte l'application installée.
2. Coché : 30 jours après la connexion, jamais prolongés, même pour un parent qui vient chaque jour.
3. Réseau coupé au retour dans l'application : tout l'écran remplacé par une erreur, données déjà lues cachées.
4. Session finie en cours d'usage : erreur sur la page, pas d'écran de connexion ; numéro à retaper, retour à l'accueil.
5. Session finie sans déconnexion : les données de la famille restaient dans le téléphone (autre parent).
6. En développement seulement : `localhost:5174` (Portail) et `localhost:8000/admin/` partagent le cookie de session ; `make demo` recrée les comptes, donc ferme toutes les sessions.

**Serveur** (`accounts/login.py`, `portal/views.py`) : coché = 90 jours après la dernière visite ; décoché = 12 heures fixes, cookie daté. Prolongation dans `renew_portal_session`, appelée par `GET /api/portal/me/` seulement (lu à chaque ouverture et retour au premier plan) : le jour gardé dans la session, donc **une écriture par jour et par appareil au plus**, rien sur les autres points d'API.

**Portail** (`lib/account.ts`, `lib/queryClient.ts`, `routes.tsx`, `LoginPage`) : compte déjà lu gardé à l'écran si le réseau manque ; `not_authenticated` sur n'importe quel appel → relecture du compte → connexion ; trace locale d'une session ouverte (numéro seulement si « Rester connecté ») → message « session terminée », numéro rempli, retour à la page demandée ; fin de session = données de la famille effacées (mémoire et hors ligne) ; déconnexion = trace effacée aussi.

**Tests** : serveur — durée et cookie des deux cas, prolongation un jour après et pas deux fois le même jour, 12 heures dépassées refusées ; Vitest — réseau coupé garde la page, session finie en cours d'usage → connexion préremplie → retour à la page, déconnexion → rien de prérempli.

**Regard senior — retiré ou simplifié** : prolongation sur `/me/` seul, pas un middleware sur chaque requête ; pas de scénario Playwright (il faudrait un 3e serveur Vite dans la CI pour ce que les tests serveur et Vitest prouvent déjà) ; limite par adresse IP inchangée (aucun blocage reproduit ; 30 échecs en 15 min par adresse) ; délai de 10 s du service worker inchangé (à mesurer à la recette 4.21).

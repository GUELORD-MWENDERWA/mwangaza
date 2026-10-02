# Tâche 5.2.1 — Console de la plateforme : socle

**Découpage** : 5.2 → 5.2.1 (application, connexion, tableau de bord) et 5.2.2 (écran « Identité de la plateforme », API d'écriture).

**Serveur**
- `apps/core/middleware.py` : `is_console_host(request)` (sous-domaine `admin`). Connexion à cette adresse (`/api/auth/login/`) = `admin_only` (comme l'administration) : autre compte → même refus qu'un mauvais mot de passe ; code toujours demandé (pas d'appareil de confiance).
- Permission `IsPlatformAdmin` (`accounts/permissions.py`) : adresse de la console, super-admin actif, session passée par la double authentification.
- `apps/schools/console.py` + `GET /api/console/dashboard/` : écoles par statut (essais qui finissent sous 30 j), élèves (inscriptions actives de l'année en cours), paiements du jour par devise (annulés exclus ; jour du fuseau de la plateforme), 10 écoles les plus actives du jour, santé (base, Redis, Celery, disque, version) dans `apps/core/health.py`.
- Tests : refus (pas super-admin, adresse d'une école, sans double authentification), chiffres justes sur deux écoles (annulé exclu, devises séparées), connexion refusée à un caissier sur la console, santé avec Redis en panne.

**Front** `frontend/apps/console` (Vite, Tailwind, `@mwangaza/ui`, i18n `console.*`, sans service worker : console en ligne) : connexion (mot de passe, code ; étapes de première connexion → terminées dans l'administration de dépannage), barre du haut sombre (design propre), tableau de bord. Test Vitest du tableau de bord ; Playwright : connexion du super-admin.

**Infra** : port 5175 (`make dev`, `dev-local`, compose), Caddy `admin.<domaine>` → console + `/api`, `/admin`, `/static` vers Django ; Dockerfile.

**Maquette** dessinée par Claude : `maquettes/console/tableau-de-bord.html` (à valider).
**Risques** : cookie de session commun console / administration (même adresse) — voulu.

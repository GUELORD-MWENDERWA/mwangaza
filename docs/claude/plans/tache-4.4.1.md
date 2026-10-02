# Tâche 4.4.1 — Accès au portail (H1, M19)

**Serveur** — nouvelle app `portal` (`services.py`, `views.py`, `urls.py`) sous `/api/portal/`, refusée (404) sur l'adresse d'une école :
- `auth/activate/` : téléphone du tuteur principal + code famille + mot de passe → compte créé, famille reliée (`primary_user`, `activated_at`), connecté. Numéro déjà doté d'un compte : `account_exists` (relier une autre école : 4.4.2).
- `auth/login/` : numéro + mot de passe, sans double authentification (le portail ne montre que la famille ; la double authentification protège l'adresse de l'école) ; mot de passe provisoire refusé (`password_change_required`).
- `auth/reset/` (mot de passe oublié) : numéro du compte + nouveau code + nouveau mot de passe ; code consommé, autres sessions déconnectées, audit `portal.password_reset` ; refusé pour un compte du personnel (`03` § 4 : le compte sert ailleurs).
- `me/` ; « Rester connecté » : 30 jours, sinon fin à la fermeture. Mauvais numéro, code inconnu ou expiré : même erreur, essai compté (`attempts`).
- `students` : `Family.code_expires_at` ; `POST /api/families/{id}/new-code/` (`students.edit`, audit `students.family_code_renewed`) : nouveau code, l'ancien ne marche plus, valable 30 jours.

**Front** — Portail : Tailwind + `@mwangaza/ui`, `i18n`, `api`, routeur, TanStack Query, react-hook-form + zod (déjà dans la Gestion : pas de nouvelle dépendance) ; écrans `/login`, `/activate`, `/forgot-password`, accueil provisoire (nom, déconnexion ; vrai accueil : 4.4.2). Gestion, fiche famille : « Nouveau code » (confirmation) et état du portail (activé le…).

**Tests** — pytest : activation (succès, mauvais numéro = mauvais code, déjà activée, compte existant, code expiré), connexion, réinitialisation (code consommé, sessions, audit, compte du personnel refusé), 404 sur l'adresse d'une école, nouveau code (403, autre école 404, audit). Vitest : connexion et activation (envoi, erreur traduite).

**Reporté à 4.4.2** : « Suspendre l'accès » (par école, affiché sur la carte de l'enfant), installable, « Ajouter un enfant d'une autre école ».

**Risques** — sessions par adresse (cookie de `parents.`) ; aucune donnée de l'école lisible avant 4.4.2.

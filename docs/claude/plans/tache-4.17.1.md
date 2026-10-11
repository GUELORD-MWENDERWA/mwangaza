# Tâche 4.17.1 — Espaces de démonstration : règles du serveur et `make demo`

4.17 découpée (trop grosse : 7 modules de démonstration à généraliser + tâche de fond + 2 écrans + PDF) : **4.17.1** serveur (ici), **4.17.2** console (création avec avancement, fiche d'accès, remise à zéro).

## Fait ici
- `accounts/phone.py` : `is_demo_phone` (plage réservée `+243 0…`). `School.is_demo`.
- Pas de mélange (`03` § 4 bis) : `accounts.services.ensure_number_fits_space`, appelé par `add_staff_member` (donc la création d'un espace) et par le portail (`portal.services._family`) ; un numéro réservé n'entre que dans un espace de démonstration, qui n'accepte que lui.
- Double authentification pas demandée dans un espace de démonstration : `totp_required` ignore ses appartenances ; `HasSchoolPermission` n'y exige pas une session à deux étapes.
- Données de démonstration décrochées des codes `itig` / `volcans` : `DemoSpace` (école, profil, numéros, mot de passe) passé à chaque `create_demo_*` ; `core.demo.fill(spaces, on_step)` = le code commun à `make demo` et à la console (4.17.2), une transaction par étape.
- `make demo` : `itig` et `volcans` en `environment=demo` ; super-admin fictif seulement avec `DEBUG`, retiré ailleurs ; ne touche plus à rien de global hors développement (essais de connexion ratés, téléphones déjà pris).

## Regard senior
- Gardé en développement : la clé commune (directeur, comptable, caissière de l'ITIG), pour que les parcours Playwright vérifient toujours la connexion en deux étapes ; jamais ailleurs.
- Activation obligatoire (parcours du promoteur) : déplacée dans un espace d'essai créé par le parcours, où elle reste exigée.
- Repoussé en 4.17.2 : modèle d'état et avancement, limite, mot de passe par espace, API, écrans, PDF.

## Tests
`accounts` (numéro réservé refusé / exigé, 2FA), `portal` (activation refusée), `core/test_demo` (types, super-admin, second espace d'un autre bloc sans collision), parcours `connexion`.

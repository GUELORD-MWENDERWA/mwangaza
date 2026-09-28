# Tâche 3.2.1 — Paramètres des reçus (Refs #22)

**Serveur** (`apps/schools`) :
- `School.settings` (JSON, `04` § 1) avec `receipt` : `printer` (`thermal_58`, `thermal_80`, `sheet`), `sheet_size` (`a6`, `a5`, `small`), `copies` (1, 2), `header` (lignes d'en-tête : adresse, téléphone, e-mail ; 5 lignes au plus), `footer` (mention). Valeurs par défaut dans `receipts.py` (`receipt_settings(school)`), lues aussi par la 3.2.2.
- `School.logo_monochrome` (mêmes règles que le logo) : `POST/DELETE /api/school/settings/logo-monochrome/`, servi par `GET /api/school/logo-monochrome/` (public, comme le logo).
- `/api/school/settings/` : `receipt` (lecture, écriture partielle fusionnée) et `logo_monochrome` (adresse).
- Journal : réglages du reçu à plat (`receipt_printer`…) avant / après ; logo noir et blanc comme le logo.
- `make demo` : réglages fictifs pour `itig` (thermique 80 mm) et `volcans` (A6, 2 exemplaires).

**Écran** : carte « Reçus » des paramètres (aperçu de l'en-tête, lignes d'en-tête, mention, imprimante, taille sur A4 si feuille, exemplaires) dans le formulaire existant ; logo noir et blanc dans « Logo et couleur ».

**Écart** : pas de champs séparés adresse / téléphone / e-mail (la maquette les met dans « Identité ») : `04` les range dans le texte d'en-tête du reçu.

**Tests** : réglages enregistrés, fusionnés et journalisés ; valeurs refusées ; 403 sans `school.configure` (réglages et logo noir et blanc) ; logo noir et blanc servi seulement à l'adresse de son école ; écran : envoi des réglages, taille visible seulement sur feuille A4.

**Risque** : faible ; ne rien casser du logo existant (fonctions de chemin distinctes pour les migrations).

# Tâche 4.22 — `make demo` sans danger pour une plateforme qui a de vraies écoles

Issue #182 · branche `tache/4.22-make-demo-sur` · 2026-10-11 · serveur seulement, aucun écran, aucune migration.

**Constat.** Tous les espaces partagent une plateforme (`03` § 4 bis) ; seul le réglage `DEMO_DATA` sépare `make demo` des vraies écoles. Or la commande remet à zéro l'identité de la plateforme, retire ses droits au compte `0000000000` hors développement et, par `update_or_create(code=…)`, change en démonstration (donc rend supprimable) tout espace qui porte le code `itig` ou `volcans`.

**Fichiers.**
- `backend/apps/schools/demo.py` : `make_demo_refusal()` (un espace réel existe → refus ; code `itig` / `volcans` pris par un espace qui n'est pas de démonstration → refus) ; `create_demo_schools` cherche l'espace par code **et** type démonstration : le type n'est plus jamais écrit sur un espace existant.
- `backend/apps/core/management/commands/demo.py` : refus avant toute écriture, quel que soit `DEMO_DATA` ; message qui renvoie à l'onglet « Démonstration » de la console, et à `make reset-db` en développement seulement (`DEBUG`).
- `make deploy-demo` et `make reseau-demo` appellent la même commande : rien à y changer.

**Tests** (`apps/core/tests/test_demo.py`, rapides : le refus vient avant le remplissage).
1. École réelle avec un paiement, identité de plateforme personnalisée, super-admin au numéro `0000000000`, hors `DEBUG` → refus ; type de l'espace, paiement, identité, droits du super-admin inchangés, ni `itig` ni `volcans` créés.
2. Code `volcans` pris par un espace d'essai → refus, type et nom inchangés.
3. Test existant « base d'avant la 4.17 » (un espace réel redevenait démonstration) : cette partie est retirée, c'est désormais interdit.

**Regard senior.** Coût : deux requêtes `exists` par `make demo`, rien à l'usage. Pas de réglage pour passer outre (ce serait rouvrir la porte). Un espace d'essai seul ne bloque pas : il est supprimable et vide de vraies données. Pas de migration qui convertit les vieilles bases : `make reset-db`.

**Risque.** Base de développement où un espace réel a été créé à la main : `make demo` et `make test-e2e` refusent jusqu'à `make reset-db` (dit dans le message et dans `A-FAIRE.md` § 12).

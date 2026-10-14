# Tâche S.6.1 — Row Level Security : socle et tables de finance (#71)

**But** : les 15 tables de finance refusent, dans PostgreSQL même, toute ligne hors de la portée de la connexion (variables `mwangaza.school_ids` / `mwangaza.all_schools`). Deuxième barrière si un `filter` est oublié.

**Hors périmètre** : les autres tables d'école (S.6.2, #242) ; défense contre l'injection SQL (une requête glissée pourrait changer la variable : l'ORM paramétré et le compte réduit de S.5 s'en chargent).

**Critères d'acceptation**
- Portée posée sur la connexion par `use_school` (requête, Celery, commandes), `use_schools` (Portail : écoles des familles du parent), `use_all_schools` (console, administration Django, tâches de la plateforme) ; vide par défaut = aucune ligne.
- Règles créées après chaque `migrate` (`post_migrate`, rejouable), sans `FORCE` : le propriétaire (migrations, `pg_dump`) n'est pas concerné.
- Toute la suite de tests tourne avec un compte sans droits de contournement : un chemin sans portée échoue en test, pas en production.

**Simplification (regard senior)** : pas de second compte PostgreSQL pour la console (deux connexions, transactions coupées en deux, un mot de passe de plus) ; la console entre dans `use_all_schools()`, aussi explicite et cherchable que `.using("platform")`.

**Tests obligatoires** : filtre oublié (ORM et SQL brut) → seulement l'école courante ; sans portée → rien ; écrire ou modifier une ligne d'une autre école refusé par la base ; Portail limité aux écoles du parent ; chaque table de finance a sa règle.

**Documents** : `03` § 4 et journal des décisions, `05` (S.6.1 / S.6.2), `06`, skill `backend`, `docs/claude/reference.md` si besoin.

**Risques** : lien vers une ligne d'une autre école devenu invisible (`_check_links`) ; erreur SQL dans une transaction cassée en sortie de portée ; comptages de requêtes des tests (connexion brute, hors journal Django).

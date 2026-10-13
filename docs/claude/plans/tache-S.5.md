# Tâche S.5 — Base de données : droits minimaux (issue #236)

**But.** En production, Django et Celery se connectent à PostgreSQL avec `mwangaza_app` : ni superutilisateur, ni propriétaire des tables, lignes seulement (`SELECT`, `INSERT`, `UPDATE`, `DELETE`). Les migrations passent par le compte `mwangaza`, dans un conteneur `migrate` qui s'arrête ensuite : son mot de passe n'est plus dans les conteneurs ouverts au web.

**Regard senior.** Les déclencheurs demandés existent déjà sur 8 tables (paiements, répartitions, annulations, crédits, clôtures, taux, deux journaux ; `UPDATE` et `DELETE` refusés, `finance.0005` à `0011`) : rien à ajouter. Ce qui manquait : l'application, superutilisateur, pouvait les désactiver ou vider une table (`TRUNCATE`). Développement et tests gardent un seul compte (les tests créent et effacent des bases).

**Hors périmètre.** Row Level Security (S.6) ; droits table par table ; deux comptes en développement.

**Critères d'acceptation.**
- `manage.py setup_app_role` (rejouable, lancé après chaque `migrate`) crée ou remet d'aplomb le compte, mot de passe envoyé déjà haché ; refuse le compte des migrations lui-même.
- Avec ce compte : encaisser marche ; `TRUNCATE`, désactiver un déclencheur, `DROP`, `CREATE TABLE`, `session_replication_role` refusés ; effacer ou modifier un paiement refusé ; un espace d'essai se supprime toujours (4.16), un espace réel jamais.
- `make deploy` et `make prod-local` : service `migrate` puis `django` et `celery` avec le compte réduit ; `make deploy-init` ajoute `POSTGRES_APP_PASSWORD` à un `serveur.env` existant ; restauration : droits redonnés.

**Tests obligatoires.** `apps/core/tests/test_db_roles.py` (argent, chemin réservé, garde-fou) ; essai réel `make prod-local` sur une base existante.

**Documents.** `03` § 8 et journal, `05`, `06`, `A-FAIRE.md` (§ 9 ter, changement des clés), `infra/README.md`, `reference.md`, skills `deployer` et `backend`.

**Risques.** `docker compose up --wait` avec un service qui s'arrête ; restauration sur une machine sans le compte (`--no-privileges`) ; code qui exigerait des droits de propriétaire (aucun trouvé : pas de `TRUNCATE` ni d'`ALTER` hors migrations).

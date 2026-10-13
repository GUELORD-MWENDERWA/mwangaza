"""Compte PostgreSQL de l'application (S.5, `03` § 8).

En production, Django et Celery se connectent avec un compte qui n'est ni superutilisateur ni
propriétaire des tables : il lit et écrit des lignes, rien d'autre. Même si une requête SQL se
glissait dans l'application, elle ne pourrait ni désactiver les déclencheurs d'immuabilité
(paiements, clôtures, taux, journaux), ni vider une table (`TRUNCATE`), ni toucher à la structure.
Les migrations passent par l'autre compte, propriétaire des tables (service `migrate` de
`infra/docker-compose.yml`), qui lance `manage.py setup_app_role` après chaque `migrate`.
"""

from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from psycopg import sql

# `NOBYPASSRLS` : les règles par école de S.6 (Row Level Security) s'appliqueront à ce compte.
ATTRIBUTES = "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
ROWS = "SELECT, INSERT, UPDATE, DELETE"
# Les tables et séquences d'aujourd'hui, puis celles que les migrations suivantes créeront.
RIGHTS = (
    "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
    "GRANT USAGE ON SCHEMA public TO {role}",
    "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}",
    f"GRANT {ROWS} ON ALL TABLES IN SCHEMA public TO {{role}}",
    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}",
    f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT {ROWS} ON TABLES TO {{role}}",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {role}",
)


def setup_app_role(role: str, password: str) -> None:
    """Crée le compte `role` ou le remet d'aplomb : mot de passe, attributs, droits. Rejouable ;
    à lancer avec le compte des migrations, jamais sur lui (il y perdrait ses droits)."""
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_user, EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", [role]
        )
        owner, exists = cursor.fetchone()
        if role == owner:
            raise ImproperlyConfigured(
                f"Le compte de l'application ne peut pas être celui des migrations (« {role} »)."
            )
        # Haché ici (SCRAM), comme `\password` de psql : le mot de passe n'est en clair ni dans la
        # requête, ni dans un journal de PostgreSQL, ni dans le suivi d'erreurs.
        hashed = connection.connection.pgconn.encrypt_password(
            password.encode(), role.encode(), b"scram-sha-256"
        )
        name = sql.Identifier(role)
        cursor.execute(
            sql.SQL("{} ROLE {} {} PASSWORD {}").format(
                sql.SQL("ALTER" if exists else "CREATE"),
                name,
                sql.SQL(ATTRIBUTES),
                sql.Literal(hashed.decode()),
            )
        )
        for right in RIGHTS:
            cursor.execute(sql.SQL(right).format(role=name))

"""Row Level Security (S.6, `03` § 4) : chaque table d'une école refuse, dans PostgreSQL même,
toute ligne hors de la portée de la connexion, que posent `use_school`, `use_schools` et
`use_all_schools` (`apps/core/tenancy.py`). Deuxième barrière si un `filter` est oublié : un
`Model.all_schools.all()` ou une requête SQL brute ne voient que les écoles de la portée.

Les règles ne s'appliquent ni au propriétaire des tables (migrations, `pg_dump`), ni à un
superutilisateur (développement) : seulement au compte de l'application en production (S.5) et
au compte des tests (`conftest.py`). Elles ne protègent pas d'une injection SQL, qui pourrait
changer la portée : l'ORM paramétré et le compte réduit s'en chargent.

Posées après chaque `migrate` (signal `post_migrate`), sur chaque table de `TenantModel` : une
nouvelle table n'est jamais oubliée. Hors règle, les tables sans école ou partagées entre écoles
(`School`, `User`, `Membership`, `PushSubscription`, `PlatformAuditLog`…).
"""

from django.apps import apps
from django.db import connections
from psycopg import sql

# Changer l'expression : changer aussi le numéro, l'ancienne règle est remplacée.
POLICY = "school_isolation_v1"
POLICY_PREFIX = "school_isolation"
# Sous-requêtes : lues une fois par requête, pas à chaque ligne (la conversion en `uuid[]`
# comprise : à chaque ligne, elle triplait le temps d'un rapport). Le second `::uuid[]`, sans
# effet, fait lire `ANY (…)` comme un tableau et non comme une sous-requête.
VISIBLE = (
    "(SELECT current_setting('mwangaza.all_schools', true) = 'on')"
    " OR school_id = ANY ((SELECT coalesce(nullif("
    "current_setting('mwangaza.school_ids', true), ''), '{}')::uuid[])::uuid[])"
)


def tables() -> list[str]:
    from apps.core.models import TenantModel

    return sorted(
        model._meta.db_table
        for model in apps.get_models()
        if issubclass(model, TenantModel) and model._meta.managed and not model._meta.proxy
    )


def install(using: str) -> None:
    """Active la règle sur chaque table qui ne l'a pas encore ; rejouable, rien à faire sinon."""
    with connections[using].cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity,"
            " array_remove(array_agg(p.polname::text), NULL)"
            " FROM pg_class c LEFT JOIN pg_policy p ON p.polrelid = c.oid"
            " WHERE c.relnamespace = 'public'::regnamespace AND c.relname = ANY(%s)"
            " GROUP BY c.relname, c.relrowsecurity",
            [tables()],
        )
        for table, enabled, policies in cursor.fetchall():
            name = sql.Identifier(table)
            if not enabled:
                cursor.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(name))
            for old in policies:
                if old.startswith(POLICY_PREFIX) and old != POLICY:
                    cursor.execute(
                        sql.SQL("DROP POLICY {} ON {}").format(sql.Identifier(old), name)
                    )
            if POLICY not in policies:
                cursor.execute(
                    sql.SQL("CREATE POLICY {} ON {} USING ({})").format(
                        sql.Identifier(POLICY), name, sql.SQL(VISIBLE)
                    )
                )


def install_after_migrate(sender, using, **kwargs) -> None:
    """Signal `post_migrate` (envoyé une fois par application : on ne répond qu'à `core`)."""
    install(using)

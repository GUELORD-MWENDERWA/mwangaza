"""Suppression d'un espace d'essai ou de démonstration (4.16, `03` § 4 bis « Effacement »).

Le journal d'une école reste immuable (migration 0001), à une exception près : il part avec
l'espace d'essai ou de démonstration qu'on supprime. Le journal de la plateforme, lui, ne change
pas : il garde la trace de la suppression.
La règle est dans la base, pas seulement dans le code : une ligne d'un espace réel ne s'efface
jamais, même si l'espace était marqué « suppression en cours » par erreur, et rien ne se modifie.
"""

from django.db import migrations

# Seul cas où la base laisse partir une ligne : son école est un espace d'essai ou de
# démonstration en cours de suppression.
SPACE_BEING_DELETED = """
    IF TG_OP = 'DELETE' AND EXISTS (
        SELECT 1 FROM schools_school
        WHERE id = OLD.school_id AND status = 'deleting' AND environment <> 'live'
    ) THEN
        RETURN OLD;
    END IF;"""


def function(name: str, message: str, *, exception: str = "") -> str:
    return f"""
CREATE OR REPLACE FUNCTION {name}() RETURNS trigger AS $$
BEGIN{exception}
    RAISE EXCEPTION '{message}'
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;
"""


NAME = "audit_auditlog_immutable"
MESSAGE = "Le journal d''audit ne se modifie pas et ne s''efface pas."


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0004_platform_log"),
        ("schools", "0009_deleting_status"),
    ]

    operations = [
        migrations.RunSQL(
            function(NAME, MESSAGE, exception=SPACE_BEING_DELETED),
            reverse_sql=function(NAME, MESSAGE),
        ),
    ]

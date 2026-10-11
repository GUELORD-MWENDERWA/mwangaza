"""Suppression d'un espace d'essai ou de démonstration (4.16, `03` § 4 bis « Effacement »).

Paiements, répartitions, annulations, crédits utilisés, clôtures de caisse (migrations 0005,
0007, 0009) et taux de change (0001) restent immuables, à une exception près : ils partent avec
l'espace d'essai ou de démonstration qu'on supprime (seule exception à « paiements immuables »).
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


FUNCTIONS = {
    "finance_payment_immutable": "Un paiement ne se modifie pas et ne s''efface pas.",
    "finance_exchangerate_immutable": "Un taux enregistré ne se modifie pas et ne s''efface pas.",
}


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0010_verbose_names"),
        ("schools", "0009_deleting_status"),
    ]

    operations = [
        migrations.RunSQL(
            function(name, message, exception=SPACE_BEING_DELETED),
            reverse_sql=function(name, message),
        )
        for name, message in FUNCTIONS.items()
    ]

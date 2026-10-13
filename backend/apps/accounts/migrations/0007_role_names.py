"""Rôles entièrement libres (M.3.2), 1 sur 2 : chaque rôle système sans nom propre reçoit le nom
que l'école voyait à l'écran. La migration suivante retire le code."""

from django.db import migrations

# Noms que l'interface affichait, en français, pour un rôle système que l'école n'avait pas
# renommé. Écrits ici : une migration ne dépend pas du modèle de départ, qui peut changer.
NAMES = {
    "head": "Directeur",
    "study_director": "Directeur des études",
    "discipline_master": "Directeur de discipline",
    "accountant": "Comptable",
    "cashier": "Caissier",
    "secretary": "Secrétaire",
    "promoter": "Promoteur",
    "teacher": "Enseignant",
    "parent": "Parent",
}


def names_to_give(roles) -> dict:
    """`roles` : (identifiant, école, code, nom) de tous les rôles. Renvoie le nom à donner à
    chaque rôle système sans nom propre."""
    taken: dict = {}
    for _role_id, school_id, _code, name in roles:
        if name:
            taken.setdefault(school_id, set()).add(name.lower())
    given = {}
    for role_id, school_id, code, name in roles:
        if name or not code:
            continue
        names = taken.setdefault(school_id, set())
        # L'école a pu créer un rôle du même nom (unique dans l'école, sans casse) : « (2) ».
        new, rank = NAMES[code], 2
        while new.lower() in names:
            new, rank = f"{NAMES[code]} ({rank})", rank + 1
        names.add(new.lower())
        given[role_id] = new
    return given


def name_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    roles = Role._base_manager.order_by("id").values_list("id", "school_id", "code", "name")
    for role_id, name in names_to_give(list(roles)).items():
        Role._base_manager.filter(pk=role_id).update(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_purge_orphan_demo_accounts"),
    ]

    operations = [
        # Retour en arrière : les noms restent (un rôle système pouvait déjà en avoir un).
        migrations.RunPython(name_roles, migrations.RunPython.noop),
    ]

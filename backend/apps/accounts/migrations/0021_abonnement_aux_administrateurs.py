from django.db import migrations


def grant(apps, schema_editor):
    """Qui gère les comptes et les rôles (administrateur principal) voit aussi l'abonnement de
    l'école : les rôles d'écoles déjà ouvertes recopient les droits de départ à la création, ils
    n'ont donc pas `billing.view` (ABO.4)."""
    Role = apps.get_model("accounts", "Role")
    for role in Role._base_manager.filter(permissions__contains=["roles.manage"]).exclude(
        permissions__contains=["billing.view"]
    ):
        role.permissions = [*role.permissions, "billing.view"]
        role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0020_droit_abonnement")]
    operations = [migrations.RunPython(grant, migrations.RunPython.noop)]

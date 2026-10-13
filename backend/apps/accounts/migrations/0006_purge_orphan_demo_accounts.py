from django.db import migrations
from django.db.models import ProtectedError

# Comptes fictifs d'espaces de démonstration déjà supprimés : désactivés mais gardés jusqu'ici.
DEMO_PHONE_PREFIX = "+2430"


def purge(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Family = apps.get_model("students", "Family")
    from django.db import transaction

    in_use = Family.objects.filter(primary_user__isnull=False).values("primary_user")
    orphans = (
        User.objects.filter(
            phone__startswith=DEMO_PHONE_PREFIX,
            is_active=False,
            is_platform_admin=False,
            memberships__isnull=True,
        )
        .exclude(pk__in=in_use)
        .distinct()
    )
    for user in orphans:
        try:
            with transaction.atomic():
                user.delete()
        except ProtectedError:
            continue


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_permission_reprise"),
        ("students", "0009_import_cancellation"),
    ]
    operations = [migrations.RunPython(purge, migrations.RunPython.noop)]

"""L'espace de démonstration `itig` devient `itig-demo` (décision du 2026-10-27) : le code `itig`
reste libre pour la vraie école. Même espace (même identifiant), donc son logo, son cachet, ses
signatures, ses photos d'élèves et toutes ses données le suivent. Seulement un espace de
démonstration, et seulement si `itig-demo` n'existe pas encore."""

from django.db import migrations


def rename(apps, schema_editor):
    School = apps.get_model("schools", "School")
    if School.objects.filter(code="itig-demo").exists():
        return
    School.objects.filter(code="itig", environment="demo").update(
        code="itig-demo", name="ITIG-DEMO"
    )


def back(apps, schema_editor):
    School = apps.get_model("schools", "School")
    if not School.objects.filter(code="itig").exists():
        School.objects.filter(code="itig-demo", environment="demo").update(
            code="itig", name="ITIG DON BOSCO"
        )


class Migration(migrations.Migration):
    dependencies = [("schools", "0024_cotitulaire")]

    operations = [migrations.RunPython(rename, back)]

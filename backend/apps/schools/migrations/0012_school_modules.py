import django.contrib.postgres.fields
from django.db import migrations, models

# Les écoles qui existent déjà gardent toutes leurs fonctions (M.1) ; une école neuve n'en a aucune.
EXISTING_SCHOOLS_MODULES = ["students", "finance", "communication"]


def give_all_modules(apps, schema_editor):
    apps.get_model("schools", "School").objects.update(modules=EXISTING_SCHOOLS_MODULES)


class Migration(migrations.Migration):
    dependencies = [("schools", "0011_setup_completed_at")]

    operations = [
        migrations.AddField(
            model_name="school",
            name="modules",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=30), blank=True, default=list, size=None,
                verbose_name="modules",
            ),
        ),
        migrations.RunPython(give_all_modules, migrations.RunPython.noop),
    ]

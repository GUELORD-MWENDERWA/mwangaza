# Catégorie de chaque cours pour les règles de délibération (NB.4) : remplace « repêchage
# permis » ; un cours sans repêchage (atelier, laboratoire) devient « pratique ».

from django.db import migrations, models


def to_category(apps, schema_editor):
    Course = apps.get_model("academics", "Course")
    Course._base_manager.filter(resit_allowed=False).update(category="practical")


def to_resit_allowed(apps, schema_editor):
    Course = apps.get_model("academics", "Course")
    Course._base_manager.filter(category="practical").update(resit_allowed=False)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0014_report_cards_ready"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="category",
            field=models.CharField(
                choices=[
                    ("general", "General"),
                    ("main", "Main course"),
                    ("option", "Option course"),
                    ("practical", "Practical"),
                ],
                default="general",
                max_length=10,
                verbose_name="category",
            ),
        ),
        migrations.RunPython(to_category, to_resit_allowed),
        migrations.RemoveField(
            model_name="course",
            name="resit_allowed",
        ),
    ]

# Lot 10 ① c : N° de carte séquentiel par école (cartes déjà émises numérotées dans l'ordre
# d'émission) et empreinte de ce que la carte imprime.

from django.db import migrations, models
from django.db.models import F, Window
from django.db.models.functions import RowNumber


def number_cards(apps, schema_editor):
    IdCard = apps.get_model("attendance", "IdCard")
    numbered = IdCard.objects.annotate(
        rank=Window(RowNumber(), partition_by=[F("school_id")], order_by=[F("created_at"), F("id")])
    ).values_list("id", "rank")
    for card_id, rank in numbered:
        IdCard.objects.filter(pk=card_id).update(number=rank)


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0002_absencejustification_attendancecorrection"),
    ]

    operations = [
        migrations.AddField(
            model_name="idcard",
            name="face_hash",
            field=models.CharField(
                blank=True, max_length=16, verbose_name="printed data fingerprint"
            ),
        ),
        migrations.AddField(
            model_name="idcard",
            name="number",
            field=models.PositiveIntegerField(editable=False, null=True, verbose_name="card number"),
        ),
        migrations.RunPython(number_cards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="idcard",
            name="number",
            field=models.PositiveIntegerField(editable=False, verbose_name="card number"),
        ),
        migrations.AddConstraint(
            model_name="idcard",
            constraint=models.UniqueConstraint(
                fields=("school", "number"), name="idcard_number_per_school"
            ),
        ),
    ]

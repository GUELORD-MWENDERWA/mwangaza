from django.db import migrations

SIZES = {"a6": "half", "a5": "half", "small": "third"}


def to_strip(apps, schema_editor):
    """Reçus « plusieurs par feuille » → un reçu par feuille (DOC.2) ; plus d'exemplaires."""
    School = apps.get_model("schools", "School")
    for school in School.objects.exclude(settings={}).iterator():
        receipt = (school.settings or {}).get("receipt")
        if not receipt:
            continue
        receipt.pop("copies", None)
        if "sheet_size" in receipt:
            receipt["sheet_size"] = SIZES.get(receipt["sheet_size"], receipt["sheet_size"])
        school.save(update_fields=["settings"])


class Migration(migrations.Migration):
    dependencies = [("schools", "0016_signature_cachet")]

    operations = [migrations.RunPython(to_strip, migrations.RunPython.noop)]

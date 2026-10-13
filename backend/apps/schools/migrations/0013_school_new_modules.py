from django.db import migrations

# M.2.1 : le portail, les notifications et le hors-ligne deviennent des modules. Les écoles qui
# existent déjà les gardent (elles les avaient) ; une école neuve n'en a aucun. Seules celles qui
# ont déjà tous les modules d'alors sont concernées : les autres sont choisies par la plateforme.
OLD = {"students", "finance", "communication"}
ADDED = ["portal", "notifications", "offline"]


def give_new_modules(apps, schema_editor):
    School = apps.get_model("schools", "School")
    for school in School.objects.all():
        if not OLD <= set(school.modules):
            continue
        school.modules = [*school.modules, *(code for code in ADDED if code not in school.modules)]
        school.save(update_fields=["modules"])


class Migration(migrations.Migration):
    dependencies = [("schools", "0012_school_modules")]

    operations = [migrations.RunPython(give_new_modules, migrations.RunPython.noop)]

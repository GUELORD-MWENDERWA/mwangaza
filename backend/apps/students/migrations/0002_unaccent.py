# Recherche des élèves et des familles sans accents (« elie » trouve « Élie ») : extension
# PostgreSQL `unaccent`, livrée avec PostgreSQL et permise au propriétaire de la base.
from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("students", "0001_eleves_familles_inscriptions")]

    operations = [UnaccentExtension()]

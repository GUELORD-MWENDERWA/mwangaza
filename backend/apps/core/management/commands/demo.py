"""`make demo` : données fictives pour le développement et les démonstrations.

Chaque tâche qui ajoute un modèle enrichit cette commande (`docs/07-a-fournir.md` § 4).
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.schools.demo import create_demo_schools


class Command(BaseCommand):
    help = "Crée ou remet à jour les données fictives de démonstration (développement seulement)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Données de démonstration refusées hors développement (DEBUG).")
        schools = create_demo_schools()
        for school in schools.values():
            self.stdout.write(
                f"  {school.code:<8} {school.name} — http://{school.code}.localhost:5173/app/"
            )
        self.stdout.write(self.style.SUCCESS(f"{len(schools)} écoles de démonstration prêtes."))

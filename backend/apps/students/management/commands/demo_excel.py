"""`make demo-excel` : liste d'élèves fictive (~800 élèves, classes de l'ITIG de démonstration)
pour essayer l'import (D1). Aucune donnée réelle."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.students.demo import ITIG_CLASS_LABELS, import_rows, import_workbook


class Command(BaseCommand):
    help = "Écrit une liste d'élèves fictive au format Excel, pour essayer l'import."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default="eleves-fictifs.xlsx")
        parser.add_argument("--count", type=int, default=800)

    def handle(self, *args, path, count, **options):
        if not settings.DEBUG:
            raise CommandError("Données de démonstration refusées hors développement (DEBUG).")
        target = Path(path).resolve()
        target.write_bytes(import_workbook(import_rows(count, ITIG_CLASS_LABELS)))
        self.stdout.write(f"{count} élèves fictifs : {target}")

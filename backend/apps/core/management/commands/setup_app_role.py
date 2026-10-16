"""`python manage.py setup_app_role` : compte PostgreSQL de l'application (S.5), créé ou remis
d'aplomb après chaque `migrate` par le compte des migrations (`apps/core/db_roles.py`)."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core.db_roles import setup_app_role


class Command(BaseCommand):
    help = "Crée ou remet d'aplomb le compte PostgreSQL de l'application (lignes seulement)."

    def handle(self, *args, **options) -> None:
        role, password = settings.DATABASE_APP_USER, settings.DATABASE_APP_PASSWORD
        if not role or not password:
            raise CommandError("POSTGRES_APP_USER et POSTGRES_APP_PASSWORD manquent.")
        try:
            setup_app_role(role, password)
        except ImproperlyConfigured as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Compte PostgreSQL « {role} » : droits de l'application à jour.")
        # Requêtes les plus lentes (PERF.5a) : extension de PostgreSQL (contrib), chargée au
        # démarrage par `docker-compose.yml`. Sans elle, le site marche pareil.
        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
        except Exception as error:
            self.stderr.write(f"pg_stat_statements non activée : {error}")

"""Passage du planificateur lancé à la main (`make relances`) : relances aux parents et caisses
encore ouvertes, sans attendre l'heure, puis purge. Pour un essai, ou sans worker Celery
(`make dev-local`). Une école déjà servie aujourd'hui ne reçoit rien de plus."""

from django.core.management.base import BaseCommand

from apps.notifications import scheduled


class Command(BaseCommand):
    help = "Envoie maintenant les notifications à heure fixe du jour, puis purge les anciennes."

    def handle(self, *args, **options) -> None:
        created = scheduled.tick(force=True)
        for code, count in sorted(created.items()):
            self.stdout.write(f"{code} : {count}")
        self.stdout.write(f"Notifications créées : {sum(created.values())}")
        self.stdout.write(f"Anciennes notifications effacées : {scheduled.purge()}")

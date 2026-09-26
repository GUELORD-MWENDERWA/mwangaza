"""`make demo` : données fictives pour le développement et les démonstrations.

Chaque tâche qui ajoute un modèle enrichit cette commande (`docs/07-a-fournir.md` § 4).
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.demo import DEMO_PASSWORD, PLATFORM_ADMIN_PHONE, create_demo_accounts
from apps.schools.demo import create_demo_schools


def _local(phone: str) -> str:
    # Forme tapée en RDC (0 + 9 chiffres), acceptée à la connexion comme le +243.
    return f"0{phone.removeprefix('+243')}"


class Command(BaseCommand):
    help = "Crée ou remet à jour les données fictives de démonstration (développement seulement)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Données de démonstration refusées hors développement (DEBUG).")
        with transaction.atomic():
            schools = create_demo_schools()
            accounts = create_demo_accounts(schools)
        for school in schools.values():
            self.stdout.write(
                f"  {school.code:<8} {school.name} — http://{school.code}.localhost:5173/app/"
            )
        self.stdout.write(f"Comptes fictifs (mot de passe : {DEMO_PASSWORD}) :")
        self.stdout.write(f"  {_local(PLATFORM_ADMIN_PHONE)}  super-admin (administration Django)")
        for account in accounts:
            schools_text = " + ".join(account.roles)
            self.stdout.write(
                f"  {_local(account.phone)}  {schools_text:<14} {account.description}"
            )
        self.stdout.write(self.style.SUCCESS(f"{len(schools)} écoles de démonstration prêtes."))

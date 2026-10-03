"""`make demo` : données fictives pour le développement et les démonstrations.

Chaque tâche qui ajoute un modèle enrichit cette commande (`docs/07-a-fournir.md` § 4).
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.demo import (
    DEMO_PASSWORD,
    DEMO_TOTP_SECRET,
    PLATFORM_ADMIN_PHONE,
    create_demo_accounts,
)
from apps.accounts.models import User
from apps.core.demo import create_demo_platform
from apps.finance.demo import (
    create_demo_cancellations,
    create_demo_charges,
    create_demo_credits,
    create_demo_discounts,
    create_demo_fees,
    create_demo_payments,
)
from apps.notifications.demo import (
    create_demo_announcements,
    create_demo_platform_announcements,
)
from apps.portal.demo import (
    create_demo_activations,
    create_demo_contact_changes,
    create_demo_portal,
)
from apps.schools.demo import create_demo_organisation, create_demo_schools
from apps.students.demo import create_demo_students
from apps.sync.demo import create_demo_devices


def _local(phone: str) -> str:
    # Forme tapée en RDC (0 + 9 chiffres), acceptée à la connexion comme le +243.
    return f"0{phone.removeprefix('+243')}"


class Command(BaseCommand):
    help = "Crée ou remet à jour les données fictives de démonstration (développement seulement)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Données de démonstration refusées hors développement (DEBUG).")
        with transaction.atomic():
            create_demo_platform()
            schools = create_demo_schools()
            accounts = create_demo_accounts(schools)
            create_demo_organisation(schools)
            create_demo_fees(schools)
            create_demo_students(schools)
            create_demo_charges(schools)
            create_demo_discounts(schools)
            create_demo_payments(schools)
            create_demo_credits(schools)
            create_demo_cancellations(schools)
            create_demo_devices(schools)
            create_demo_announcements(schools)
            create_demo_platform_announcements(schools)
            portal = create_demo_portal(schools)
            create_demo_contact_changes(schools["itig"])
            for school in schools.values():
                create_demo_activations(school)
        for school in schools.values():
            self.stdout.write(f"  {school.code:<8} {school.name} — {school.url}/app/")
        self.stdout.write(f"Comptes fictifs (mot de passe : {DEMO_PASSWORD}) :")
        self.stdout.write(
            f"  {_local(PLATFORM_ADMIN_PHONE)}  super-admin (administration Django : "
            "http://localhost:8000/admin/) — code : make totp"
        )
        users = {
            user.phone: user for user in User.objects.filter(phone__in=[a.phone for a in accounts])
        }
        for account in accounts:
            schools_text = " + ".join(account.roles)
            totp_text = ""
            if users[account.phone].totp_enabled:
                totp_text = " — code : make totp"
            elif account.totp_to_enable:
                totp_text = " — double authentification à activer"
            self.stdout.write(
                f"  {_local(account.phone)}  {schools_text:<14} {account.description}{totp_text}"
            )
        if portal is not None:
            self.stdout.write(
                f"  {_local(portal.phone)}  portail        parent (http://localhost:5174/) : "
                f"enfants à l'ITIG ; ajouter ceux des Volcans avec le code {portal.code_to_add}"
            )
        key = " ".join(DEMO_TOTP_SECRET[i : i + 4] for i in range(0, len(DEMO_TOTP_SECRET), 4))
        self.stdout.write(
            f"Double authentification (« code ») : clé {key} dans une application "
            "(Google Authenticator, Aegis…), ou le code du moment avec `make totp`."
        )
        self.stdout.write(self.style.SUCCESS(f"{len(schools)} écoles de démonstration prêtes."))

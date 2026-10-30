"""`make demo` : données fictives pour le développement et les démonstrations.

Les deux écoles sont des espaces de démonstration, remplis par le même code que ceux de la
console (`apps/core/demo.py`, où chaque tâche qui ajoute un modèle ajoute son étape).
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.demo import (
    DEMO_TEAM,
    DEMO_TOTP_SECRET,
    PLATFORM_ADMIN_PHONE,
    create_demo_admin,
    demo_accounts,
    demo_password,
)
from apps.accounts.models import User
from apps.core.demo import (
    create_demo_articles,
    create_demo_platform,
    create_demo_requests,
    fill,
)
from apps.core.tenancy import use_all_schools
from apps.notifications.demo import create_demo_platform_announcements
from apps.portal.demo import demo_portal
from apps.schools import deletion
from apps.schools.demo import DEMO_CODES, create_demo_schools, make_demo_refusal
from apps.schools.models import School


def _local(phone: str) -> str:
    # Forme tapée en RDC (0 + 9 chiffres), acceptée à la connexion comme le +243.
    return f"0{phone.removeprefix('+243')}"


def _erase_demo_spaces() -> list[str]:
    """`--fresh` : les espaces de `make demo` (et l'ancien `itig`, s'il reste en démonstration)
    effacés entièrement avant d'être recréés à neuf, comme une suppression depuis la console
    (`deletion.run`), sans attendre la tâche de fond. Jamais un espace réel ni d'essai."""
    erased = []
    codes = {*DEMO_CODES.values(), "itig"}
    spaces = list(School.objects.filter(code__in=codes, environment=School.Environment.DEMO))
    if spaces:
        # Statistiques à jour d'abord : sur une base fraîche (essai, test), l'effacement des notes
        # par paquets tirait un plan de plusieurs minutes par paquet.
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE")
    for school in spaces:
        School.objects.filter(pk=school.pk).update(status=School.Status.DELETING)
        deletion.run(str(school.pk))
        erased.append(school.code)
    return erased


class Command(BaseCommand):
    help = "Crée ou remet à jour les données fictives (développement et essai seulement)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fresh",
            action="store_true",
            help="Efface d'abord les espaces de démonstration de make demo, puis les recrée à "
            "neuf (serveur en ligne : make deploy-demo).",
        )

    def handle(self, *args, **options):
        if not settings.DEMO_DATA:
            raise CommandError(
                "Données de démonstration refusées ici (seulement en développement et dans l'essai "
                "sur plusieurs appareils : DEMO_DATA)."
            )
        # Le réglage ne suffit pas : tous les espaces partagent une plateforme (`03` § 4 bis).
        refusal = make_demo_refusal()
        if refusal is not None:
            reset = (
                " Base de développement : `make reset-db` l'efface et la recrée."
                if settings.DEBUG
                else ""
            )
            raise CommandError(
                f"{refusal} `make demo` remettrait à zéro l'identité de la plateforme et ses "
                "espaces : refusé, rien n'a été modifié. Une démonstration se crée dans la "
                f"console (Écoles, onglet « Démonstration »).{reset}"
            )
        # Clé commune de double authentification : en développement seulement, jamais là où le
        # mot de passe est propre au serveur.
        shared_key = settings.DEBUG and not settings.DEMO_PASSWORD
        if options["fresh"]:
            with use_all_schools():
                for code in _erase_demo_spaces():
                    self.stdout.write(f"  {code} effacé")
        # Tâche de la plateforme : la base laisse voir toutes les écoles (S.6).
        with use_all_schools(), transaction.atomic():
            create_demo_platform()
            create_demo_articles()
            admin = create_demo_admin()
            spaces = create_demo_schools(password=demo_password(), shared_totp_key=shared_key)
            fill(spaces)
            if admin is not None:
                create_demo_platform_announcements(spaces)
                create_demo_requests()
        for space in spaces:
            school = space.school
            self.stdout.write(f"  {school.code:<8} {school.name} — {school.url}/app/")
        self.stdout.write(f"Comptes fictifs (mot de passe : {demo_password()}) :")
        if admin is not None:
            self.stdout.write(
                f"  {_local(PLATFORM_ADMIN_PHONE)}  administrateur principal de la plateforme "
                "(console http://admin.localhost:5175/ et administration Django "
                "http://localhost:8000/admin/) — code : make totp"
            )
            for phone, (role, _name) in DEMO_TEAM.items():
                self.stdout.write(
                    f"  {_local(phone)}  équipe : {role} (console) — code : make totp"
                )
        accounts = {a.phone: a for space in spaces for a in demo_accounts(space)}
        with_code = set(
            User.objects.filter(phone__in=accounts, totp_enabled_at__isnull=False).values_list(
                "phone", flat=True
            )
        )
        pool = [account for account in accounts.values() if not account.listed]
        for account in accounts.values():
            if not account.listed:
                continue
            schools_text = " + ".join(account.roles)
            totp_text = " — code : make totp" if account.phone in with_code else ""
            self.stdout.write(
                f"  {_local(account.phone)}  {schools_text:<14} {account.description}{totp_text}"
            )
        if pool:
            self.stdout.write(
                f"  {_local(pool[0].phone)} à {_local(pool[-1].phone)}  itig  {len(pool)} "
                "enseignants (un cours chacun ou plus, 24 h par semaine au plus)"
            )
        portal = demo_portal(spaces)
        if portal is not None:
            self.stdout.write(
                f"  {_local(portal.phone)}  portail        parent (http://localhost:5174/) : "
                f"enfants à l'ITIG ; ajouter ceux des Volcans avec le code {portal.code_to_add}"
            )
        if shared_key:
            key = " ".join(DEMO_TOTP_SECRET[i : i + 4] for i in range(0, len(DEMO_TOTP_SECRET), 4))
            self.stdout.write(
                f"Code à 6 chiffres (directeur, comptable, caissière) : clé {key} dans une "
                "application (Google Authenticator, Aegis…), ou le code du moment avec "
                "`make totp`. Les autres comptes se connectent sans code, comme dans tout espace "
                "de démonstration."
            )
        else:
            self.stdout.write(
                "Pas de double authentification : les espaces de démonstration ne la demandent pas."
            )
        if admin is None:
            self.stdout.write(
                "Pas de super-admin fictif hors développement : créer le vôtre (createsuperuser)."
            )
        self.stdout.write(self.style.SUCCESS(f"{len(spaces)} espaces de démonstration prêts."))

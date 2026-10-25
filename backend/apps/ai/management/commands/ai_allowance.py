"""`manage.py ai_allowance` : règle l'IA d'une école jusqu'à la console (IA.1.2) : usages affectés,
crédits par mois, pause, recharge. Passe par les services : chaque changement est au journal de
la plateforme, au nom du super-admin donné par `--by`."""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.ai import services, uses
from apps.ai.models import AiAllowance
from apps.core.errors import BusinessError
from apps.core.tenancy import use_all_schools, use_school
from apps.schools.models import School


class Command(BaseCommand):
    help = "Règle les usages, les crédits mensuels, la pause et les recharges de l'IA d'une école."

    def add_arguments(self, parser):
        parser.add_argument("school", help="Code de l'école (son sous-domaine).")
        parser.add_argument("--by", required=True, help="Téléphone du super-admin qui règle.")
        parser.add_argument(
            "--uses", help=f"Usages séparés par des virgules ({', '.join(uses.USES)})."
        )
        parser.add_argument("--credits", type=int, help="Crédits par mois (1 crédit = 0,001 $).")
        parser.add_argument("--pause", choices=["on", "off"])
        parser.add_argument("--top-up", type=int, help="Crédits ajoutés au mois en cours.")

    def handle(self, *args, **options):
        try:
            actor = User.objects.get_by_natural_key(options["by"])
        except User.DoesNotExist as error:
            raise CommandError("Compte inconnu.") from error
        if not actor.is_platform_admin:
            raise CommandError("Réservé à un super-admin de la plateforme.")
        with use_all_schools():
            school = School.objects.filter(code=options["school"]).first()
            if school is None:
                raise CommandError("École inconnue.")
        try:
            with use_school(school):
                current = AiAllowance.objects.filter(school=school).first()
            changed = any(options[key] is not None for key in ("uses", "credits", "pause"))
            if changed:
                services.set_allowance(
                    school,
                    actor=actor,
                    uses_=(
                        [u for u in options["uses"].split(",") if u]
                        if options["uses"] is not None
                        else (current.uses if current else [])
                    ),
                    monthly_credits=(
                        options["credits"]
                        if options["credits"] is not None
                        else (current.monthly_credits if current else 0)
                    ),
                    paused=(
                        options["pause"] == "on"
                        if options["pause"]
                        else (current.paused if current else False)
                    ),
                )
            if options["top_up"]:
                services.top_up(school, actor=actor, credits=options["top_up"])
        except BusinessError as error:
            raise CommandError(str(error)) from error
        with use_school(school):
            now = AiAllowance.objects.filter(school=school).first()
        self.stdout.write(
            f"{school.code} : usages {now.uses if now else []}, "
            f"{now.monthly_credits if now else 0} crédits par mois"
            f"{', en pause' if now and now.paused else ''}."
        )

"""Mise en route d'une école neuve (4.20.1, C4) : la liste du tableau de bord du directeur.

Chaque étape se coche seule, d'après ce que l'école a déjà saisi : une question « existe-t-il
au moins un… » par étape, rien de gardé. La liste n'est calculée que tant que l'école ne l'a pas
terminée (`School.setup_completed_at`) : ensuite `/api/school/` dit `setup_done` et plus aucun
écran ne la demande. Rien n'est écrit pendant la lecture."""

from dataclasses import dataclass

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Membership
from apps.accounts.roles import FINANCE_COLLECT_PAYMENT
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.errors import ApiError, BusinessError
from apps.finance.models import CashRegister, ExchangeRate, FeeRule, Payment
from apps.schools.models import AcademicYear, ClassGroup, School
from apps.students.models import Enrollment, Family
from apps.sync.models import Device

SETUP_INCOMPLETE = ApiError(
    "setup_incomplete", _("Some steps are still missing before the school can collect."), 409
)

# Facultatives : une école qui commence à la rentrée n'a rien à reprendre, et les parents
# s'invitent quand elle veut. Elles ne retiennent pas la fin de la liste.
OPTIONAL = ("prior", "invitations")
INVITED = (Action.STUDENTS_FAMILY_INVITATION_PRINTED, Action.STUDENTS_FAMILY_INVITATION_SHARED)


@dataclass(frozen=True)
class Step:
    key: str
    done: bool
    optional: bool


@dataclass(frozen=True)
class Setup:
    steps: list[Step]
    ready: bool
    finished_at: object | None


def _steps(school: School) -> dict[str, bool]:
    year = AcademicYear.objects.filter(is_current=True).first()
    # Comptes qui peuvent encaisser : le directeur ne le peut pas, il lui faut un caissier.
    collectors = Membership.objects.filter(
        school=school, is_active=True, roles__permissions__contains=[FINANCE_COLLECT_PAYMENT]
    )
    in_year = {"academic_year": year}
    return {
        "year": year is not None,
        "classes": year is not None and ClassGroup.objects.filter(**in_year).exists(),
        # Deux devises : sans le taux de l'année, la caisse ne peut pas convertir.
        "fees": year is not None
        and FeeRule.objects.filter(**in_year).exists()
        and (len(school.enabled_currencies) < 2 or ExchangeRate.objects.filter(**in_year).exists()),
        "staff": collectors.exists(),
        # Hors ligne, un caissier n'encaisse que sur un appareil déjà connu du serveur.
        "cash": CashRegister.objects.filter(is_active=True).exists()
        and Device.objects.filter(revoked_at=None, user__in=collectors.values("user")).exists(),
        "students": year is not None
        and Enrollment.objects.filter(**in_year, status=Enrollment.Status.ACTIVE).exists(),
        "prior": Payment.objects.filter(origin=Payment.Origin.PRIOR).exists(),
        "invitations": Family.objects.filter(activated_at__isnull=False).exists()
        or AuditLog.objects.filter(action__in=INVITED).exists(),
    }


def status(school: School) -> Setup:
    """La liste de l'école courante ; vide, sans rien lire, une fois terminée."""
    if school.setup_completed_at:
        return Setup(steps=[], ready=True, finished_at=school.setup_completed_at)
    steps = [Step(key, done, key in OPTIONAL) for key, done in _steps(school).items()]
    ready = all(step.done for step in steps if not step.optional)
    return Setup(steps=steps, ready=ready, finished_at=None)


def finish(school: School) -> Setup:
    """Le directeur ferme la liste : seule écriture de la mise en route, une fois par école.
    Refusé tant que l'école ne peut pas encaisser ; rejoué, la première date reste."""
    current = status(school)
    if current.finished_at:
        return current
    if not current.ready:
        raise BusinessError(SETUP_INCOMPLETE)
    School.objects.filter(pk=school.pk, setup_completed_at=None).update(
        setup_completed_at=timezone.now()
    )
    school.refresh_from_db(fields=["setup_completed_at"])
    return status(school)

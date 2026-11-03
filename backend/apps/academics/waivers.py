"""Bulletin retenu pour frais impayés et dérogations du préfet (8.4.6).

Règle : si l'école l'a choisi (`School.portal["report_requires_payment"]`) et a le module
`finance`, le PDF du bulletin n'est pas servi aux parents tant qu'un frais **échu** de l'élève
reste impayé, sauf dérogation active (élève ou famille). La décision de passage reste visible :
on ne chasse pas l'enfant. Calcul à la lecture, rien n'est stocké de plus ; la dérogation est une
ligne `FeeWaiver` qu'on lève mais ne modifie ni n'efface."""

from collections.abc import Iterable
from datetime import date

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import FeeWaiver
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.finance import services as finance
from apps.students.models import Enrollment, Family, Student

REASON_REQUIRED = ApiError("reason_required", _("Give the reason for this waiver."), 400)
PAST_DATE = ApiError("waiver_in_the_past", _("The waiver must end today or later."), 400)
ONE_TARGET = ApiError("waiver_one_target", _("Choose a family or a student, not both."), 400)
ALREADY_LIFTED = ApiError("waiver_lifted", _("This waiver is already lifted."), 409)
NO_FINANCE = ApiError("no_finance_module", _("This school has no fee module."), 400)


def is_required() -> bool:
    """L'école retient-elle le bulletin des élèves en retard de paiement ?"""
    school = require_current_school()
    return bool(school.portal["report_requires_payment"]) and school.has_module("finance")


def active_waivers(day: date | None = None) -> QuerySet[FeeWaiver]:
    day = day or finance.today()
    return FeeWaiver.objects.filter(lifted_at__isnull=True, until__gte=day)


def _overdue(enrollment_ids: list) -> set:
    """Inscriptions dont un frais dû est en retard (échéance passée, reste > 0)."""
    by_enrollment = finance.charges_by_enrollment(enrollment_ids, light=True)
    return {
        enrollment_id
        for enrollment_id, charges in by_enrollment.items()
        if any(charge.state == finance.OVERDUE for charge in charges)
    }


def withheld_ids(enrollments: Iterable[Enrollment]) -> set:
    """Inscriptions dont le bulletin est retenu. Trois requêtes quel que soit leur nombre."""
    enrollments = list(enrollments)
    if not enrollments or not is_required():
        return set()
    late = _overdue([e.pk for e in enrollments])
    if not late:
        return set()
    waivers = list(active_waivers().values_list("student_id", "family_id"))
    students = {student for student, _family in waivers if student}
    families = {family for _student, family in waivers if family}
    return {
        e.pk
        for e in enrollments
        if e.pk in late and e.student_id not in students and e.student.family_id not in families
    }


def is_withheld(enrollment: Enrollment) -> bool:
    return enrollment.pk in withheld_ids([enrollment])


def waiver_data(waiver: FeeWaiver) -> dict:
    return {
        "family": str(waiver.family_id) if waiver.family_id else None,
        "student": str(waiver.student_id) if waiver.student_id else None,
        "until": str(waiver.until),
        "reason": waiver.reason,
    }


def grant(
    *, actor: User, reason: str, until: date, family: Family | None, student: Student | None
) -> FeeWaiver:
    """Accorde une dérogation (droit `grades.waive_fees`, vérifié par l'API) : motif et date de
    fin obligatoires, pour une famille ou un élève de l'école."""
    reason = reason.strip()
    if not reason:
        raise BusinessError(REASON_REQUIRED)
    if (family is None) == (student is None):
        raise BusinessError(ONE_TARGET)
    if until < finance.today():
        raise BusinessError(PAST_DATE)
    if not require_current_school().has_module("finance"):
        raise BusinessError(NO_FINANCE)
    with transaction.atomic():
        waiver = FeeWaiver.objects.create(
            family=family, student=student, reason=reason, until=until, granted_by=actor
        )
        audit.record(
            Action.FEE_WAIVER_GRANTED,
            waiver,
            actor=actor,
            after=waiver_data(waiver),
            label=str(student or family),
        )
    return waiver


def lift(waiver: FeeWaiver, *, actor: User) -> FeeWaiver:
    """Lève une dérogation : le bulletin est de nouveau retenu s'il y a un retard."""
    with transaction.atomic():
        waiver = FeeWaiver.objects.select_for_update().get(pk=waiver.pk)
        if waiver.lifted_at:
            raise BusinessError(ALREADY_LIFTED)
        waiver.lifted_at, waiver.lifted_by = timezone.now(), actor
        waiver.save(update_fields=["lifted_at", "lifted_by", "updated_at"])
        audit.record(
            Action.FEE_WAIVER_LIFTED,
            waiver,
            actor=actor,
            before=waiver_data(waiver),
            after={"lifted": True},
            label=str(waiver.student or waiver.family),
        )
    return waiver


def listing(*, only_active: bool) -> QuerySet[FeeWaiver]:
    waivers = FeeWaiver.objects.select_related("family", "student", "granted_by", "lifted_by")
    if only_active:
        day = finance.today()
        waivers = waivers.filter(Q(lifted_at__isnull=True), until__gte=day)
    return waivers.order_by("-created_at")

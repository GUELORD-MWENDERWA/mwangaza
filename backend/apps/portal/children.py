"""Paiements d'un enfant sur le portail (H3) : frais dus de l'année et leur état, solde par
devise, paiements et leurs reçus, photo avec le consentement du parent.

Le portail n'a pas d'école : l'enfant est cherché parmi les familles reliées au compte
(`primary_user`), puis lu dans son école (`in_school`, son fuseau). Famille d'un autre compte,
accès suspendu par l'école ou école suspendue : 404, sans dire si l'enfant existe."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.models import Payment, PaymentCancellation, StudentCharge
from apps.schools.models import School
from apps.students.models import Enrollment, Student
from apps.students.photos import photo_version

# État d'un frais à l'écran : ceux de `finance`, plus « payé d'avance » (échéance pas encore
# arrivée) et « partiel » (entamé, pas encore échu).
PAID_EARLY, PARTIAL = "paid_early", "partial"
FEE_STATES = [finance.PAID, PAID_EARLY, PARTIAL, finance.OVERDUE, finance.UPCOMING]


@contextmanager
def in_school(school: School) -> Iterator[None]:
    with use_school(school), timezone.override(ZoneInfo(school.timezone)):
        yield


def linked_to(user: User, path: str) -> dict:
    """Filtres : la famille au bout de `path` (`family`, `enrollment__student__family`) est
    reliée à ce compte et l'école ne lui a pas suspendu l'accès."""
    return {f"{path}__primary_user": user, f"{path}__portal_suspended_at__isnull": True}


def find_student(user: User, student_id) -> Student:
    student = (
        Student.all_schools.filter(pk=student_id, **linked_to(user, "family"))
        .exclude(School.portal_closed("school__"))
        .select_related("school")
        .first()
    )
    if student is None:
        raise NotFound
    return student


def fee_label(charge: StudentCharge) -> str:
    """« Minerval · 1re tranche » ; le libellé seul quand il répète le type."""
    name = charge.fee_type.name
    return name if charge.label == name else f"{name} · {charge.label}"


def photo_url(student: Student) -> str | None:
    if not (student.photo and student.photo_consent):
        return None
    return f"/api/portal/children/{student.pk}/photo/?v={photo_version(student)}"


def homeroom_teacher(school: School, enrollment: Enrollment) -> dict | None:
    """Titulaire de la classe (5.7) : son nom ; son téléphone seulement si l'école a choisi de
    le montrer aux parents (`schools/portal.py`)."""
    teacher = enrollment.class_group.homeroom_teacher
    if teacher is None or not teacher.is_active:
        return None
    phone = teacher.phone if school.portal["teacher_phone"] else None
    return {"name": teacher.get_full_name(), "phone": phone}


@dataclass
class ChildPayments:
    school: School
    enrollment: Enrollment
    photo: str | None
    homeroom_teacher: dict | None
    balance: finance.Balance
    fees: list[StudentCharge]
    payments: list[Payment]


def _fee_state(charge: StudentCharge, day) -> str:
    if charge.state == finance.PAID:
        return PAID_EARLY if charge.due_on > day else finance.PAID
    if charge.state == finance.UPCOMING and charge.paid_minor:
        return PARTIAL
    return charge.state


def child_payments(user: User, student_id) -> ChildPayments:
    """Inscription de l'année en cours (sinon 404), frais dus qui comptent (`fee` : « Minerval ·
    1re tranche », `display_state`), paiements les plus récents d'abord (`cancelled`). Cinq
    requêtes."""
    student = find_student(user, student_id)
    with in_school(student.school):
        enrollment = (
            Enrollment.objects.filter(
                student=student,
                academic_year__is_current=True,
                status=Enrollment.Status.ACTIVE,
            )
            .select_related(
                "student",
                "academic_year",
                "class_group__level",
                "class_group__track",
                "class_group__homeroom_teacher",
            )
            .first()
        )
        if enrollment is None:
            raise NotFound
        charges = finance.charges_of(enrollment.pk)
        day = finance.today()
        fees = [charge for charge in charges if charge.state]
        for charge in fees:
            charge.fee = fee_label(charge)
            charge.display_state = _fee_state(charge, day)
            charge.due_minor = charge.amount_minor - charge.discount_minor
        payments = list(
            Payment.objects.filter(enrollment=enrollment)
            .annotate(cancelled=Exists(PaymentCancellation.objects.filter(payment=OuterRef("pk"))))
            .order_by("-paid_at", "-id")
        )
        return ChildPayments(
            student.school,
            enrollment,
            photo_url(student),
            homeroom_teacher(student.school, enrollment),
            finance.balance(charges),
            fees,
            payments,
        )

"""Accueil du portail (H2) : les familles reliées au compte, une par école, et leurs enfants
inscrits cette année avec leur situation de paiement (même calcul que la Gestion : par devise,
jamais additionnée, réductions déduites, paiements annulés exclus).

Le portail n'a pas d'école : chaque famille se lit dans la sienne (`children.in_school`, son
fuseau), seulement si elle est reliée à ce compte (`primary_user`). École suspendue ou accès
suspendu par l'école : la famille apparaît, sans aucune donnée de ses enfants. Cinq requêtes par
école reliée (un parent en a une ou deux)."""

from dataclasses import dataclass

from apps.accounts.models import User
from apps.finance import services as finance
from apps.finance.models import Payment
from apps.portal.children import fee_label, in_school, photo_url
from apps.schools.models import School
from apps.students.models import Enrollment, Family

ACTIVE, SUSPENDED, SCHOOL_UNAVAILABLE = "active", "suspended", "school_unavailable"


@dataclass
class Child:
    enrollment: Enrollment
    balance: finance.Balance
    first_overdue: str | None
    last_payment: Payment | None
    photo: str | None


@dataclass
class LinkedFamily:
    family: Family
    status: str
    children: list[Child]


def _children(family: Family) -> list[Child]:
    enrollments = list(
        Enrollment.objects.filter(
            student__family=family,
            academic_year__is_current=True,
            status=Enrollment.Status.ACTIVE,
        )
        .select_related("student", "class_group__level", "class_group__track")
        .order_by("student__last_name", "student__first_name")
    )
    ids = [enrollment.pk for enrollment in enrollments]
    charges = finance.charges_by_enrollment(ids, light=True)
    # Dernier paiement non annulé de chaque inscription (DISTINCT ON de PostgreSQL).
    last = {
        payment.enrollment_id: payment
        for payment in Payment.objects.filter(enrollment_id__in=ids, cancellation__isnull=True)
        .order_by("enrollment_id", "-paid_at", "-id")
        .distinct("enrollment_id")
    }
    children = []
    for enrollment in enrollments:
        items = charges[enrollment.pk]
        overdue = next((c for c in items if c.state == finance.OVERDUE), None)
        children.append(
            Child(
                enrollment=enrollment,
                balance=finance.balance(items),
                first_overdue=fee_label(overdue) if overdue else None,
                last_payment=last.get(enrollment.pk),
                photo=photo_url(enrollment.student),
            )
        )
    return children


def linked(family: Family) -> LinkedFamily:
    school = family.school
    if school.status == School.Status.SUSPENDED:
        return LinkedFamily(family, SCHOOL_UNAVAILABLE, [])
    if family.portal_suspended_at is not None:
        return LinkedFamily(family, SUSPENDED, [])
    with in_school(school):
        return LinkedFamily(family, ACTIVE, _children(family))


def linked_families(user: User) -> list[LinkedFamily]:
    """Les familles de ce compte, dans l'ordre où il les a reliées."""
    families = (
        Family.all_schools.filter(primary_user=user)
        .select_related("school")
        .order_by("activated_at", "id")
    )
    return [linked(family) for family in families]

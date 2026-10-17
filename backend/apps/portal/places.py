"""Places de l'année suivante au portail (8.4.5) : le parent voit, pour chacun de ses enfants,
la place que l'école lui garde, et répond « revient » ou « ne revient pas ». La réponse se change
tant que l'école n'a pas inscrit l'enfant ; elle ne crée rien (`academics/promotion.py`).

Comme ailleurs au portail : seulement les familles reliées au compte, accès non suspendu, école
ouverte ; une place d'une autre famille répond 404, sans dire qu'elle existe."""

from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.academics.models import PlaceConfirmation
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.portal.children import in_school, linked_to
from apps.schools.models import School
from apps.students.models import Enrollment


def _open_places(user: User) -> QuerySet[PlaceConfirmation]:
    """Places encore proposées aux enfants de ce compte, pour une année pas encore finie, sauf
    l'enfant déjà inscrit cette année-là."""
    already = Enrollment.all_schools.filter(
        student=OuterRef("enrollment__student"),
        academic_year=OuterRef("class_group__academic_year"),
    )
    return (
        PlaceConfirmation.all_schools.filter(
            status=PlaceConfirmation.Status.OFFERED,
            class_group__academic_year__ends_on__gte=timezone.localdate(),
            **linked_to(user, "enrollment__student__family"),
        )
        .exclude(School.portal_closed("school__"))
        .exclude(Exists(already))
    )


def places(user: User) -> list[PlaceConfirmation]:
    return list(
        _open_places(user)
        .select_related(
            "school",
            "enrollment__student",
            "class_group__academic_year",
            "class_group__level",
            "class_group__track",
        )
        .order_by("enrollment__student__last_name", "enrollment__student__first_name", "pk")
    )


def answer(user: User, place_id, value: str) -> PlaceConfirmation:
    """Réponse du parent ; la même réponse deux fois ne change rien."""
    place = (
        _open_places(user)
        .filter(pk=place_id)
        .select_related(
            "school",
            "enrollment__student",
            "class_group__academic_year",
            "class_group__level",
            "class_group__track",
        )
        .first()
    )
    if place is None:
        raise NotFound
    if place.answer == value:
        return place
    with in_school(place.school):
        before = place.answer
        place.answer, place.answered_at, place.answered_by = value, timezone.now(), user
        place.save(update_fields=["answer", "answered_at", "answered_by", "updated_at"])
        audit.record(
            Action.STUDENTS_PLACE_ANSWERED,
            place,
            actor=user,
            before={"answer": before} if before else None,
            after={"answer": value, "class": place.class_group.name},
            label=place.enrollment.student.full_name,
        )
    return place

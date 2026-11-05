"""Remplaçant d'un cours (8.2.5) : le directeur des études (`grades.validate`) désigne une
personne du personnel pour un cours, avec motif et date de fin facultative, et la retire.

Le remplaçant voit le cours dans ses notes (`grades.gradable_courses`) et n'y saisit qu'un total
par élève, comme la direction (`grades.SUBSTITUTE`) : jamais les devoirs ni les interrogations de
l'enseignant ; une feuille que l'enseignant a commencée lui reste fermée tant qu'elle n'est pas
envoyée (`grades.check_substitute`). Toute correction d'une note saisie par un autre demande un
motif, et l'enseignant du cours en est averti (`grades.save_sheet`).

Un cours commun (8.1.2a) se remplace pour le groupe entier. Une désignation par cours (ou par
groupe) : une encore en cours doit être retirée d'abord (409 `substitute_exists`) ; une échue est
remplacée. Désigner et retirer vont au journal et préviennent le remplaçant et l'enseignant."""

from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.courses import active_staff
from apps.academics.models import Course, CourseGroup, CourseSubstitute
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.notifications import events

SUBSTITUTE_EXISTS = ApiError(
    "substitute_exists", _("This course already has a substitute: remove them first."), 409
)


def _invalid(path: str, message, code: str) -> ValidationError:
    return ValidationError({path: ValidationError(message, code=code)})


def active() -> QuerySet[CourseSubstitute]:
    """Désignations en cours aujourd'hui (date de fin comprise) dans l'école courante."""
    today = timezone.localdate()
    return CourseSubstitute.objects.filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))


def replaced_courses(user: User) -> QuerySet[Course]:
    """Cours que `user` remplace aujourd'hui, directement ou par leur cours commun."""
    mine = active().filter(substitute=user)
    return Course.objects.filter(
        Q(pk__in=mine.filter(course__isnull=False).values("course_id"))
        | Q(course_group_id__in=mine.filter(course_group__isnull=False).values("course_group_id"))
    )


def with_details(rows: QuerySet[CourseSubstitute]) -> QuerySet[CourseSubstitute]:
    """Ce qu'il faut pour afficher une désignation (`label`, `teacher_of`), sans requête de plus."""
    return rows.select_related(
        "substitute",
        "course__class_group",
        "course__teacher",
        "course_group__level",
        "course_group__teacher",
    )


def listing(year=None) -> list[CourseSubstitute]:
    """Désignations en cours, d'une année au choix, avec ce qu'il faut pour les afficher."""
    rows = with_details(active())
    if year is not None:
        rows = rows.filter(
            Q(course__class_group__academic_year=year) | Q(course_group__academic_year=year)
        )
    return sorted(rows, key=lambda row: (label(row), row.created_at))


def label(row: CourseSubstitute) -> str:
    if row.course_group_id:
        return f"{row.course_group.name} · {row.course_group.level.name}"
    return f"{row.course.name} · {row.course.class_group.name}"


def teacher_of(row: CourseSubstitute) -> User | None:
    return row.course_group.teacher if row.course_group_id else row.course.teacher


def _snapshot(row: CourseSubstitute) -> dict:
    return {
        "course": label(row),
        "substitute": str(row.substitute),
        "reason": row.reason,
        "ends_on": row.ends_on.isoformat() if row.ends_on else None,
    }


def designate(
    course: Course,
    *,
    substitute_id: UUID,
    reason: str,
    ends_on: date | None,
    actor: User,
) -> CourseSubstitute:
    """Désigne le remplaçant de `course` (de son groupe s'il est commun) : une personne du
    personnel actif (400 `not_staff`), pas l'enseignant du cours (400 `is_teacher`), jusqu'à une
    date qui n'est pas passée (400 `ends_in_past`)."""
    substitute = active_staff().filter(pk=substitute_id).first()
    if substitute is None:
        raise _invalid("substitute_id", _("Choose a member of the school's staff."), "not_staff")
    group: CourseGroup | None = course.course_group
    teacher_id = group.teacher_id if group else course.teacher_id
    if substitute.pk == teacher_id:
        raise _invalid("substitute_id", _("This person already teaches this course."), "is_teacher")
    if ends_on is not None and ends_on < timezone.localdate():
        raise _invalid("ends_on", _("This date is already past."), "ends_in_past")
    target = {"course_group": group} if group else {"course": course}
    with transaction.atomic():
        # Verrou sur le cours : deux désignations en même temps n'en font pas deux.
        list(Course.objects.select_for_update().filter(pk=course.pk).order_by().values("pk"))
        existing = CourseSubstitute.objects.filter(**target).first()
        if existing is not None:
            if existing.ends_on is None or existing.ends_on >= timezone.localdate():
                raise BusinessError(SUBSTITUTE_EXISTS)
            existing.delete()
        row = CourseSubstitute(
            **target,
            substitute=substitute,
            reason=reason.strip(),
            ends_on=ends_on,
            created_by=actor,
        )
        try:
            with transaction.atomic():
                row.save()
        except IntegrityError:
            raise BusinessError(SUBSTITUTE_EXISTS) from None
        audit.record(
            Action.GRADES_SUBSTITUTE_SET, row, actor=actor, after=_snapshot(row), label=label(row)
        )
        events.course_substitute(
            label(row), substitute, teacher_id, reason=row.reason, removed=False, actor=actor
        )
    return row


def remove(row: CourseSubstitute, *, actor: User) -> None:
    """Retire le remplaçant : il perd l'accès au cours ; ses notes restent."""
    with transaction.atomic():
        audit.record(
            Action.GRADES_SUBSTITUTE_REMOVED,
            row,
            actor=actor,
            before=_snapshot(row),
            label=label(row),
        )
        teacher = teacher_of(row)
        events.course_substitute(
            label(row),
            row.substitute,
            teacher.pk if teacher else None,
            reason=row.reason,
            removed=True,
            actor=actor,
        )
        row.delete()

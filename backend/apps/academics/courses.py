"""Cours de chaque classe (8.1) : la grille d'une classe s'enregistre d'un seul bloc
(`set_courses`, que la proposition depuis un bulletin en PDF réutilisera, IA.5), se copie vers
d'autres classes, et donne la charge horaire de chaque enseignant.

Droit `courses.configure`, vérifié par l'API. Chaque grille changée va dans le journal de l'école
(domaine `courses`) : les cours ajoutés, retirés ou modifiés, dans la transaction de l'action.
"""

from collections import defaultdict
from dataclasses import dataclass, field, replace
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Course, Evaluation
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools.models import AcademicYear, ClassGroup, Term

COURSE_IN_USE = ApiError("course_in_use", _("A removed course is already used."), 409)
EXAM_GRADED = ApiError(
    "exam_graded", _("This course already has exam grades: it keeps its exam."), 409
)
MAX_GRADED = ApiError(
    "max_graded",
    _("This course already has grades: only whoever validates grades may change its maximum."),
    409,
)

# Au-delà, c'est une erreur de saisie (un bulletin en compte une vingtaine).
MAX_COURSES = 60
FIELDS = ("name", "domain", "period_max", "has_exam", "weekly_hours", "teacher_id")


@dataclass(frozen=True)
class CourseInput:
    """Un cours de la grille envoyée ; `id` : celui d'un cours de la classe à garder."""

    name: str
    period_max: int
    has_exam: bool = True
    domain: str = ""
    weekly_hours: int | None = None
    teacher_id: UUID | None = None
    id: UUID | None = None


def active_staff():
    """Enseignants possibles : le personnel actif de l'école courante (jamais celui d'une autre),
    quel que soit son rôle (les rôles sont libres)."""
    school = require_current_school()
    return User.objects.filter(
        is_active=True, memberships__school=school, memberships__is_active=True
    ).order_by("last_name", "middle_name", "first_name")


def _invalid(path: str, message, code: str) -> ValidationError:
    return ValidationError({path: ValidationError(message, code=code)})


def _check(group: ClassGroup, items: list[CourseInput]) -> dict[UUID, User]:
    """Tout est vérifié avant d'écrire : un refus ne laisse pas une grille à moitié changée.
    Renvoie les enseignants de la grille, lus d'un coup."""
    if len(items) > MAX_COURSES:
        raise _invalid(
            "courses",
            _("At most %(max)d courses per class.") % {"max": MAX_COURSES},
            "too_many_courses",
        )
    own = set(group.courses.values_list("pk", flat=True))
    names: set[str] = set()
    ids: set[UUID] = set()
    for index, item in enumerate(items):
        name = item.name.strip().casefold()
        if name in names:
            raise _invalid(
                f"courses.{index}.name",
                _("This class already has this course."),
                "duplicate_course",
            )
        names.add(name)
        if item.id is not None:
            if item.id not in own or item.id in ids:
                raise _invalid(f"courses.{index}.id", _("Unknown course."), "unknown_course")
            ids.add(item.id)
    staff = active_staff().in_bulk({item.teacher_id for item in items if item.teacher_id})
    for index, item in enumerate(items):
        if item.teacher_id is not None and item.teacher_id not in staff:
            raise _invalid(
                f"courses.{index}.teacher_id",
                _("Choose a member of the school's staff."),
                "not_staff",
            )
    return staff


def _snapshot(course: Course) -> dict:
    teacher = course.teacher
    return {
        "name": course.name,
        "domain": course.domain,
        "period_max": course.period_max,
        "has_exam": course.has_exam,
        "weekly_hours": course.weekly_hours,
        "teacher": str(teacher) if teacher else None,
    }


def courses_of(group: ClassGroup):
    return group.courses.select_related("teacher").order_by("order")


def set_courses(
    group: ClassGroup, items: list[CourseInput], *, actor: User, may_validate: bool = False
) -> list[Course]:
    """Remplace la grille de la classe : cours gardés (par `id`), ajoutés, modifiés, retirés,
    dans l'ordre reçu. Un cours retiré qui sert déjà (notes, 8.2) : 409 `course_in_use` ; un
    cours qui perd son examen alors qu'il y est noté : 409 `exam_graded` ; le maximum d'un cours
    déjà noté ne change qu'avec `may_validate` (droit `grades.validate`) : 409 `max_graded`."""
    staff = _check(group, items)
    with transaction.atomic():
        existing = {course.pk: course for course in courses_of(group)}
        no_more_exam = [
            item.id
            for item in items
            if item.id in existing and existing[item.id].has_exam and not item.has_exam
        ]
        exams = Evaluation.objects.filter(course_id__in=no_more_exam, term__kind=Term.Kind.EXAM)
        if no_more_exam and exams.exists():
            raise BusinessError(EXAM_GRADED)
        new_max = [
            item.id
            for item in items
            if item.id in existing and existing[item.id].period_max != item.period_max
        ]
        if (
            new_max
            and not may_validate
            and Evaluation.objects.filter(course_id__in=new_max).exists()
        ):
            raise BusinessError(MAX_GRADED)
        before = {pk: (_snapshot(course), course.order) for pk, course in existing.items()}
        wanted = {item.id for item in items}
        removed = [course for pk, course in existing.items() if pk not in wanted]
        try:
            for course in removed:
                course.delete()
        except ProtectedError:
            raise BusinessError(COURSE_IN_USE) from None
        created, updated, final = [], [], []
        now = timezone.now()
        for order, item in enumerate(items):
            course = existing.get(item.id) if item.id is not None else None
            if course is None:
                course = Course(class_group=group, created_by=actor)
                created.append(course)
            course.name = item.name.strip()
            course.domain = item.domain.strip()
            course.period_max = item.period_max
            course.has_exam = item.has_exam
            course.weekly_hours = item.weekly_hours
            course.teacher = staff.get(item.teacher_id) if item.teacher_id else None
            course.order = order
            final.append(course)
            if course.pk in before and before[course.pk] != (_snapshot(course), order):
                course.updated_at = now
                updated.append(course)
        Course.objects.bulk_create(created)
        Course.objects.bulk_update(updated, [*FIELDS, "order", "updated_at"])
        # Journal : ce qui change sur le bulletin, pas l'ordre des lignes.
        old_rows = {pk: row for pk, (row, _order) in before.items()}
        after = {course.pk: _snapshot(course) for course in final}
        old = [row for pk, row in old_rows.items() if row != after.get(pk)]
        new = [row for pk, row in after.items() if row != old_rows.get(pk)]
        if old or new:
            audit.record(
                Action.COURSES_CHANGED,
                group,
                actor=actor,
                before={"courses": old} if old else None,
                after={"courses": new} if new else None,
            )
    return final


def copy_courses(
    source: ClassGroup, targets: list[ClassGroup], *, actor: User, may_validate: bool = False
) -> int:
    """Donne la grille de `source` à chaque classe de `targets`, qui perd ses autres cours. Un
    cours du même nom garde son identifiant et son enseignant ; un cours nouveau n'en a pas."""
    grid = [
        CourseInput(
            name=course.name,
            domain=course.domain,
            period_max=course.period_max,
            has_exam=course.has_exam,
            weekly_hours=course.weekly_hours,
        )
        for course in courses_of(source)
    ]
    with transaction.atomic():
        for target in targets:
            if target.pk == source.pk:
                continue
            same = {course.name.casefold(): course for course in courses_of(target)}
            items = []
            for item in grid:
                kept = same.get(item.name.casefold())
                items.append(
                    replace(item, id=kept.pk, teacher_id=kept.teacher_id) if kept else item
                )
            set_courses(target, items, actor=actor, may_validate=may_validate)
    return len([target for target in targets if target.pk != source.pk])


def copy_year_courses(pairs: list[tuple[ClassGroup, ClassGroup]], *, actor: User) -> int:
    """Nouvelle année « avec les classes d'une autre année » : chaque nouvelle classe reçoit les
    cours de l'ancienne, sans les enseignants (comme les titulaires, ils changent d'une année à
    l'autre). Noté avec la création de l'année."""
    by_source = {old.pk: new for old, new in pairs}
    copies = [
        Course(
            class_group=by_source[course.class_group_id],
            created_by=actor,
            **{field: getattr(course, field) for field in FIELDS if field != "teacher_id"},
            order=course.order,
        )
        for course in Course.objects.filter(class_group__in=list(by_source))
    ]
    return len(Course.objects.bulk_create(copies))


@dataclass
class Load:
    teacher: User
    hours: int = 0
    courses: list[Course] = field(default_factory=list)


def teaching_loads(year: AcademicYear) -> tuple[list[Load], list[Course]]:
    """Charge horaire de chaque membre du personnel actif dans l'année (heures par semaine de ses
    cours ; 0 sans cours), la plus lourde d'abord ; puis les cours sans enseignant.
    Deux requêtes."""
    loads = {user.pk: Load(user) for user in active_staff()}
    unassigned: list[Course] = []
    courses = (
        Course.objects.filter(class_group__academic_year=year)
        .select_related("class_group__level", "class_group__track")
        .order_by(
            "class_group__level__order",
            "class_group__track__name",
            "class_group__section",
            "order",
        )
    )
    former: dict[UUID, list[Course]] = defaultdict(list)
    for course in courses:
        if course.teacher_id is None:
            unassigned.append(course)
        elif course.teacher_id in loads:
            load = loads[course.teacher_id]
            load.courses.append(course)
            load.hours += course.weekly_hours or 0
        else:
            # Parti de l'école depuis : ses cours sont à réattribuer.
            former[course.teacher_id].append(course)
    unassigned += [course for group in former.values() for course in group]
    ordered = sorted(loads.values(), key=lambda load: (-load.hours, str(load.teacher)))
    return ordered, unassigned

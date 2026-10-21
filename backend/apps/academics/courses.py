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

from apps.academics.models import ANY_TIME, GENERAL, Course, Evaluation
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools.models import AcademicYear, ClassGroup, Term
from apps.timetable import placement as placing
from apps.timetable.models import Room

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
FIELDS = (
    "name",
    "domain",
    "period_max",
    "has_exam",
    "is_taught",
    "grade_entry",
    "category",
    "weekly_hours",
    "teacher_id",
)
# Placement dans l'horaire (EDT.1b) : envoyé dans `CourseInput.placement`, avec le droit
# `timetable.manage` (vérifié par l'API) ; absent, gardé.
PLACEMENT = (
    "lesson_pattern",
    "max_per_day",
    "room_id",
    "room_kind",
    "can_span_break",
    "preferred_part",
)


@dataclass(frozen=True)
class CourseInput:
    """Un cours de la grille envoyée ; `id` : celui d'un cours de la classe à garder."""

    name: str
    period_max: int
    has_exam: bool = True
    is_taught: bool = True
    grade_entry: str = ""
    category: str = GENERAL
    domain: str = ""
    weekly_hours: int | None = None
    teacher_id: UUID | None = None
    id: UUID | None = None
    # Clés de `PLACEMENT` ; None : le placement du cours ne change pas.
    placement: dict | None = None


def active_staff():
    """Enseignants possibles : le personnel actif de l'école courante (jamais celui d'une autre),
    quel que soit son rôle (les rôles sont libres)."""
    school = require_current_school()
    return User.objects.filter(
        is_active=True, memberships__school=school, memberships__is_active=True
    ).order_by("last_name", "middle_name", "first_name")


def _invalid(path: str, message, code: str) -> ValidationError:
    return ValidationError({path: ValidationError(message, code=code)})


def _check(group: ClassGroup, items: list[CourseInput]) -> tuple[dict[UUID, User], dict]:
    """Tout est vérifié avant d'écrire : un refus ne laisse pas une grille à moitié changée.
    Renvoie les enseignants et les salles exigées de la grille, lus d'un coup."""
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
    return staff, _check_placement(group, items)


def _check_placement(group: ClassGroup, items: list[CourseInput]) -> dict[UUID, Room]:
    """Séances = heures, au plus par jour ≥ la plus longue séance, une salle de l'école en
    service (ou celle que le cours avait déjà) ou un type de salle, pas les deux."""
    placed = [(index, item) for index, item in enumerate(items) if item.placement is not None]
    kept = dict(group.courses.values_list("pk", "room_id"))
    wanted = {item.placement["room_id"] for _index, item in placed if item.placement["room_id"]}
    rooms = Room.objects.in_bulk(wanted)
    for index, item in placed:
        path = f"courses.{index}.placement"
        data = item.placement
        pattern = placing.parse_pattern(data["lesson_pattern"])
        if pattern is None:
            raise _invalid(
                f"{path}.lesson_pattern",
                _("Write the lessons as numbers joined by +, for example 2+2+1."),
                "bad_pattern",
            )
        if pattern and sum(pattern) != (item.weekly_hours or 0):
            raise _invalid(
                f"{path}.lesson_pattern",
                _("The lessons add up to %(sum)d h for %(hours)d h of this course.")
                % {"sum": sum(pattern), "hours": item.weekly_hours or 0},
                "pattern_hours",
            )
        if pattern and data["max_per_day"] and data["max_per_day"] < max(pattern):
            raise _invalid(
                f"{path}.max_per_day",
                _("A lesson lasts %(longest)d h: allow at least that much per day.")
                % {"longest": max(pattern)},
                "below_longest_lesson",
            )
        room_id = data["room_id"]
        if room_id and data["room_kind"]:
            raise _invalid(
                f"{path}.room_id", _("Choose a room or a type of room, not both."), "room_or_kind"
            )
        if room_id:
            room = rooms.get(room_id)
            if room is None:
                raise _invalid(f"{path}.room_id", _("This room does not exist."), "unknown_room")
            if not room.is_active and kept.get(item.id) != room_id:
                raise _invalid(
                    f"{path}.room_id", _("This room is no longer in use."), "room_retired"
                )
    return rooms


def _placement_row(course: Course) -> dict:
    """Ce que le journal garde du placement : seulement ce qui est réglé."""
    row = {
        "lesson_pattern": course.lesson_pattern,
        "max_per_day": course.max_per_day,
        "room": str(course.room) if course.room_id else None,
        "room_kind": course.room_kind,
        "can_span_break": course.can_span_break,
        "preferred_part": course.preferred_part if course.preferred_part != ANY_TIME else None,
    }
    return {key: value for key, value in row.items() if value not in ("", None)}


def _snapshot(course: Course) -> dict:
    teacher = course.teacher
    placement = _placement_row(course)
    return {
        "name": course.name,
        "domain": course.domain,
        "period_max": course.period_max,
        "has_exam": course.has_exam,
        "is_taught": course.is_taught,
        "grade_entry": course.grade_entry,
        "category": course.category,
        "weekly_hours": course.weekly_hours,
        "teacher": str(teacher) if teacher else None,
        **({"placement": placement} if placement else {}),
    }


def courses_of(group: ClassGroup):
    return group.courses.select_related("teacher", "room").order_by("order")


def set_courses(
    group: ClassGroup, items: list[CourseInput], *, actor: User, may_validate: bool = False
) -> list[Course]:
    """Remplace la grille de la classe : cours gardés (par `id`), ajoutés, modifiés, retirés,
    dans l'ordre reçu. Un cours retiré qui sert déjà (notes, 8.2) : 409 `course_in_use` ; un
    cours qui perd son examen alors qu'il y est noté : 409 `exam_graded` ; le maximum d'un cours
    déjà noté ne change qu'avec `may_validate` (droit `grades.validate`) : 409 `max_graded`."""
    staff, rooms = _check(group, items)
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
            course.is_taught = item.is_taught
            course.grade_entry = item.grade_entry
            course.category = item.category
            hours_changed = course.weekly_hours != item.weekly_hours
            course.weekly_hours = item.weekly_hours
            course.teacher = staff.get(item.teacher_id) if item.teacher_id else None
            if item.placement is not None:
                data = item.placement
                course.lesson_pattern = data["lesson_pattern"].replace(" ", "")
                course.max_per_day = data["max_per_day"]
                course.room = rooms.get(data["room_id"]) if data["room_id"] else None
                course.room_kind = data["room_kind"]
                course.can_span_break = data["can_span_break"]
                course.preferred_part = data["preferred_part"]
            elif hours_changed and course.lesson_pattern:
                # Heures changées sans le placement (droit ou module absent) : les séances
                # données ne tombent plus juste, elles redeviennent calculées.
                course.lesson_pattern = ""
            course.order = order
            final.append(course)
            if course.pk in before and before[course.pk] != (_snapshot(course), order):
                course.updated_at = now
                updated.append(course)
        Course.objects.bulk_create(created)
        Course.objects.bulk_update(updated, [*FIELDS, *PLACEMENT, "order", "updated_at"])
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
            is_taught=course.is_taught,
            grade_entry=course.grade_entry,
            category=course.category,
            weekly_hours=course.weekly_hours,
            placement={field: getattr(course, field) for field in PLACEMENT},
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
            **{
                field: getattr(course, field)
                for field in (*FIELDS, *PLACEMENT)
                if field != "teacher_id"
            },
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

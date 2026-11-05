"""Cours communs à plusieurs classes (8.1.2a) : un groupe relie les cours de même nom de classes
d'un même niveau et d'une même année ; il a un seul enseignant, donné à chacun de ses cours.
Les maxima, les notes et les bulletins restent ceux de chaque classe. Droit
`courses.configure`, vérifié par l'API ; chaque changement va dans le journal (`course_group.*`).
L'emploi du temps en fait un cours commun (un créneau pour toutes ses classes, 8.1.2b) : ses cours
ne sont pas aussi dans une règle de groupe de l'horaire.
"""

from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.courses import active_staff
from apps.academics.models import Course, CourseGroup
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.notifications import events
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment
from apps.timetable import constraints

MAX_CLASSES = 12


def _invalid(path: str, message, code: str) -> ValidationError:
    return ValidationError({path: ValidationError(message, code=code)})


def _teacher(teacher_id: UUID | None) -> User | None:
    if teacher_id is None:
        return None
    teacher = active_staff().filter(pk=teacher_id).first()
    if teacher is None:
        raise _invalid("teacher_id", _("Choose a member of the school's staff."), "not_staff")
    return teacher


def _snapshot(group: CourseGroup) -> dict:
    return {
        "name": group.name,
        "teacher": str(group.teacher) if group.teacher else None,
        "classes": sorted(
            course.class_group.name for course in group.courses.select_related("class_group")
        ),
    }


def groups_of(year=None, level=None):
    """Les cours communs de l'école courante, avec leurs cours (une requête de plus pour les
    classes et les effectifs)."""
    groups = CourseGroup.objects.select_related("teacher", "level", "academic_year")
    if year is not None:
        groups = groups.filter(academic_year=year)
    if level is not None:
        groups = groups.filter(level=level)
    return groups.prefetch_related(
        "courses__class_group__level",
        "courses__class_group__track",
    )


def _give_teacher(courses: list[Course], teacher: User | None, *, actor: User) -> None:
    changed = [course for course in courses if course.teacher_id != (teacher and teacher.pk)]
    if not changed:
        return
    before = [(course, course.teacher_id, teacher.pk if teacher else None) for course in changed]
    now = timezone.now()
    for course in changed:
        course.teacher = teacher
        course.updated_at = now
    Course.objects.bulk_update(changed, ["teacher", "updated_at"])
    events.course_teacher_changed(before, actor=actor)


def create_group(
    *, name: str, class_groups: list[ClassGroup], teacher_id: UUID | None, actor: User
) -> CourseGroup:
    """Relie le cours `name` de chaque classe de `class_groups` (deux au moins, même année et même
    niveau, chacune avec ce cours donné et pas déjà dans un cours commun)."""
    name = name.strip()
    unique = list(dict.fromkeys(class_groups))
    if not 2 <= len(unique) <= MAX_CLASSES:
        raise _invalid(
            "class_groups",
            _("Choose between 2 and %(max)d classes.") % {"max": MAX_CLASSES},
            "bad_classes",
        )
    year, level = unique[0].academic_year_id, unique[0].level_id
    if any(group.academic_year_id != year or group.level_id != level for group in unique):
        raise _invalid(
            "class_groups", _("The classes must share the same level and year."), "mixed_classes"
        )
    teacher = _teacher(teacher_id)
    with transaction.atomic():
        # Le verrou des règles de l'horaire d'abord : groupes disjoints exacts.
        constraints.lock_school()
        courses = list(
            Course.objects.select_for_update(of=("self",))
            .filter(class_group__in=unique, name__iexact=name, is_taught=True)
            .select_related("class_group", "teacher")
        )
        if len(courses) != len(unique):
            raise _invalid("name", _("Each class must give this course."), "missing_course")
        if any(course.course_group_id for course in courses):
            raise _invalid(
                "name",
                _("A class is already in a joint course for this course."),
                "already_grouped",
            )
        if constraints.in_rule_group({str(course.pk) for course in courses}):
            raise _invalid(
                "name",
                _(
                    "A class's course is already in a timetable group (parallel groups or joint "
                    "course): remove it from that rule first."
                ),
                "timetable_grouped",
            )
        if CourseGroup.objects.filter(
            academic_year_id=year, level_id=level, name__iexact=name
        ).exists():
            raise _invalid("name", _("This joint course already exists."), "duplicate_group")
        group = CourseGroup.objects.create(
            academic_year_id=year,
            level_id=level,
            name=courses[0].name,
            teacher=teacher,
            created_by=actor,
        )
        Course.objects.filter(pk__in=[course.pk for course in courses]).update(course_group=group)
        if teacher is not None:
            _give_teacher(courses, teacher, actor=actor)
        audit.record(Action.COURSE_GROUP_CHANGED, group, actor=actor, after=_snapshot(group))
    return group


def set_teacher(group: CourseGroup, teacher_id: UUID | None, *, actor: User) -> CourseGroup:
    """Change l'enseignant du groupe : il devient celui de chaque cours de ses classes."""
    teacher = _teacher(teacher_id)
    with transaction.atomic():
        before = _snapshot(group)
        group.teacher = teacher
        group.save(update_fields=["teacher", "updated_at"])
        courses = list(group.courses.select_related("class_group", "teacher"))
        _give_teacher(courses, teacher, actor=actor)
        after = _snapshot(group)
        if before != after:
            audit.record(
                Action.COURSE_GROUP_CHANGED, group, actor=actor, before=before, after=after
            )
    return group


def remove_class(group: CourseGroup, class_group: ClassGroup, *, actor: User) -> None:
    """Sort une classe du groupe : son cours reste, avec ses notes et son enseignant ; sous deux
    classes, le groupe est dissous."""
    with transaction.atomic():
        before = _snapshot(group)
        left = Course.objects.filter(course_group=group, class_group=class_group)
        if not left.exists():
            raise _invalid(
                "class_group", _("This class is not in the joint course."), "not_in_group"
            )
        left.update(course_group=None)
        if group.courses.count() < 2:
            dissolve(group, actor=actor, record=False)
            audit.record(Action.COURSE_GROUP_CHANGED, group, actor=actor, before=before)
        else:
            audit.record(
                Action.COURSE_GROUP_CHANGED,
                group,
                actor=actor,
                before=before,
                after=_snapshot(group),
            )


def dissolve(group: CourseGroup, *, actor: User, record: bool = True) -> None:
    """Défait le groupe : chaque cours redevient seul, avec ses notes et son enseignant."""
    with transaction.atomic():
        before = _snapshot(group)
        group.courses.update(course_group=None)
        if record:
            audit.record(Action.COURSE_GROUP_CHANGED, group, actor=actor, before=before)
        group.delete()


def present(groups: list[CourseGroup]) -> list[CourseGroup]:
    """Ajoute à chaque groupe ses classes (`class_courses`, avec l'effectif actif de chacune) et
    leur total (`students`) : une requête de comptage pour tous les groupes."""
    class_ids = {c.class_group_id for g in groups for c in g.courses.all()}
    counts = dict(
        Enrollment.objects.filter(class_group_id__in=class_ids, status=Enrollment.Status.ACTIVE)
        .values("class_group_id")
        .annotate(n=Count("pk"))
        .values_list("class_group_id", "n")
    )
    for group in groups:
        courses = sorted(group.courses.all(), key=lambda c: c.class_group.name)
        for course in courses:
            course.students = counts.get(course.class_group_id, 0)
        group.class_courses = courses
        group.students = sum(course.students for course in courses)
    return groups

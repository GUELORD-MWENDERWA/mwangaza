"""Contrôles avant le calcul de l'horaire (EDT.1b, spec emploi du temps § 6) : ce qui rend
l'horaire impossible (rouge, `error`) ou incomplet (orange, `warning`), vu avant tout calcul.

Calcul Python pur sur l'année en cours, sans solveur ni IA : sept requêtes quelle que soit la
taille de l'école. Chaque ligne dit quoi (`subject`), combien (`values`) et où corriger (la classe,
l'enseignant ou la salle) ; les chiffres viennent d'ici, jamais de l'IA. Contrôles 6 et 7
(verrous, règles qui se contredisent) : avec les règles (EDT.1c).
"""

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import time
from uuid import UUID

from apps.academics.courses import active_staff
from apps.academics.models import Course
from apps.core.tenancy import require_current_school
from apps.schools.models import AcademicYear, ClassGroup
from apps.timetable import placement as placing
from apps.timetable.models import Room, TeacherTimetableProfile, TimeGrid, TimeSlot
from apps.timetable.services import grids, rules_of

ERROR, WARNING = "error", "warning"
LEVELS = [ERROR, WARNING]
# Contrôles de la spec (§ 6) : 1 classes, 2 enseignants, 3 cours, 4 salles, 5 cours incomplets.
CLASSES, TEACHERS, COURSES, ROOMS, INCOMPLETE = 1, 2, 3, 4, 5
# Noms de cours montrés dans une ligne qui en regroupe plusieurs.
NAMES_SHOWN = 3

Slot = tuple[int, time, time]


@dataclass
class Issue:
    check: int
    code: str
    level: str
    subject: str
    values: dict = field(default_factory=dict)
    class_group: UUID | None = None
    teacher: UUID | None = None
    room: UUID | None = None


class Week:
    """Les heures de cours d'une grille, jour par jour, dans l'ordre."""

    def __init__(self, grid: TimeGrid) -> None:
        self.days: dict[int, list[TimeSlot]] = defaultdict(list)
        for slot in grid.slots.all():  # rangées par jour et heure (`services.grids`)
            self.days[slot.weekday].append(slot)
        self.lessons: list[Slot] = [
            (slot.weekday, slot.start, slot.end)
            for slots in self.days.values()
            for slot in slots
            if slot.kind == TimeSlot.Kind.LESSON
        ]

    def longest_run(self, span_break: bool) -> int:
        """La plus longue suite d'heures de cours d'une journée ; une récréation la coupe, sauf
        pour un cours qui peut la passer."""
        best = 0
        for slots in self.days.values():
            run = 0
            for slot in slots:
                if slot.kind == TimeSlot.Kind.LESSON:
                    run += 1
                    best = max(best, run)
                elif not span_break:
                    run = 0
        return best


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def is_blocked(unavailable: list[dict], slot: Slot) -> bool:
    """L'heure tombe-t-elle sur une absence (jour entier, ou plage qui la chevauche) ?"""
    weekday, start, end = slot
    for item in unavailable:
        if item["weekday"] != weekday:
            continue
        if "start" not in item or (_clock(item["start"]) < end and _clock(item["end"]) > start):
            return True
    return False


def _names(courses: list[Course]) -> dict:
    return {
        "count": len(courses),
        "names": ", ".join(course.name for course in courses[:NAMES_SHOWN]),
        "more": max(0, len(courses) - NAMES_SHOWN),
    }


def run(year: AcademicYear | None) -> dict:
    """Les contrôles 1 à 5 sur l'année : lignes rouges d'abord, puis orange."""
    school_rules = rules_of(require_current_school())
    weeks: dict[UUID, Week] = {}
    default = None
    for grid in grids():
        weeks[grid.pk] = Week(grid)
        if grid.is_default:
            default = weeks[grid.pk]
    groups = (
        list(ClassGroup.objects.filter(academic_year=year).select_related("level", "track"))
        if year
        else []
    )
    week_of = {group.pk: weeks.get(group.time_grid_id, default) for group in groups}
    courses = list(
        Course.objects.filter(class_group__academic_year=year, is_taught=True)
        .select_related("teacher")
        .order_by("class_group__level__order", "class_group__section", "order")
    )
    staff = set(active_staff().values_list("pk", flat=True))
    profiles = {profile.teacher_id: profile for profile in TeacherTimetableProfile.objects.all()}
    rooms = {room.pk: room for room in Room.objects.all()}
    by_group = {group.pk: group for group in groups}

    issues: list[Issue] = []
    issues += _classes(groups, courses, week_of)
    issues += _teachers(courses, staff, profiles, week_of, school_rules)
    issues += _courses(courses, profiles, week_of, by_group, school_rules)
    issues += _rooms(courses, rooms, week_of, by_group)
    issues += _incomplete(courses, staff, by_group)
    issues.sort(key=lambda issue: (issue.level != ERROR, issue.check))
    return {
        "errors": sum(issue.level == ERROR for issue in issues),
        "warnings": sum(issue.level == WARNING for issue in issues),
        "classes": len(groups),
        "teachers": len({course.teacher_id for course in courses if course.teacher_id}),
        "rooms": sum(room.is_active for room in rooms.values()),
        "issues": [asdict(issue) for issue in issues],
    }


def _classes(groups, courses, week_of) -> list[Issue]:
    """1. Classe surchargée : heures des cours > places de sa grille."""
    hours: dict[UUID, int] = defaultdict(int)
    for course in courses:
        hours[course.class_group_id] += course.weekly_hours or 0
    issues = []
    for group in groups:
        week = week_of[group.pk]
        if week is None:
            continue
        capacity = len(week.lessons)
        if hours[group.pk] > capacity:
            issues.append(
                Issue(
                    CLASSES,
                    "class_overloaded",
                    ERROR,
                    group.name,
                    {"hours": hours[group.pk], "capacity": capacity},
                    class_group=group.pk,
                )
            )
    return issues


def _teachers(courses, staff, profiles, week_of, school_rules) -> list[Issue]:
    """2. Enseignant au-delà de son maximum ; au-delà de ses heures libres (heures de cours des
    grilles de ses classes, absences retirées) ; au-delà de ce que ses jours permettent avec ses
    heures au plus par jour."""
    load: dict[UUID, int] = defaultdict(int)
    slots: dict[UUID, set[Slot]] = defaultdict(set)
    names: dict[UUID, str] = {}
    for course in courses:
        if course.teacher_id not in staff or not course.weekly_hours:
            continue
        load[course.teacher_id] += course.weekly_hours
        names[course.teacher_id] = str(course.teacher)
        week = week_of.get(course.class_group_id)
        if week is not None:
            slots[course.teacher_id].update(week.lessons)
    issues = []
    for teacher, hours in load.items():
        profile = profiles.get(teacher)
        unavailable = profile.unavailable if profile else []

        def issue(code, values, teacher=teacher):
            return Issue(TEACHERS, code, ERROR, names[teacher], values, teacher=teacher)

        if profile and profile.max_week_hours and hours > profile.max_week_hours:
            issues.append(
                issue("teacher_over_max", {"hours": hours, "max": profile.max_week_hours})
            )
        free = [slot for slot in slots[teacher] if not is_blocked(unavailable, slot)]
        if hours > len(free):
            issues.append(issue("teacher_over_free", {"hours": hours, "free": len(free)}))
            continue
        per_day = (profile.max_day_hours if profile else None) or school_rules[
            "teacher_max_day_hours"
        ]
        by_day: dict[int, int] = defaultdict(int)
        for weekday, _start, _end in free:
            by_day[weekday] += 1
        possible = sum(min(count, per_day) for count in by_day.values())
        if hours > possible:
            issues.append(
                issue(
                    "teacher_over_days",
                    {"hours": hours, "possible": possible, "per_day": per_day},
                )
            )
    return issues


def _courses(courses, profiles, week_of, by_group, school_rules) -> list[Issue]:
    """3. Séance plus longue que la plus longue suite d'heures d'un jour ; cours impossible à
    étaler : heures > au plus par jour, sur les jours où l'enseignant est libre."""
    issues = []
    for course in courses:
        week = week_of.get(course.class_group_id)
        if week is None or not course.weekly_hours:
            continue
        group = by_group[course.class_group_id]

        def issue(code, values, course=course, group=group):
            return Issue(
                COURSES,
                code,
                ERROR,
                course.name,
                {"class": group.name, **values},
                class_group=group.pk,
            )

        longest_lesson = max(placing.sessions(course))
        longest_run = week.longest_run(placing.spans_break(course))
        if longest_lesson > longest_run:
            issues.append(
                issue("lesson_too_long", {"length": longest_lesson, "longest": longest_run})
            )
            continue
        profile = profiles.get(course.teacher_id)
        unavailable = profile.unavailable if profile else []
        per_day = placing.max_per_day(course, school_rules["max_same_course_per_day"])
        by_day: dict[int, int] = defaultdict(int)
        for slot in week.lessons:
            if not is_blocked(unavailable, slot):
                by_day[slot[0]] += 1
        possible = sum(min(count, per_day) for count in by_day.values())
        if course.weekly_hours > possible:
            issues.append(
                issue(
                    "course_spread",
                    {
                        "hours": course.weekly_hours,
                        "per_day": per_day,
                        "days": len(by_day),
                        "possible": possible,
                    },
                )
            )
    return issues


def _rooms(courses, rooms, week_of, by_group) -> list[Issue]:
    """4. Salle demandée au-delà de ses heures (cours qui l'exigent et cours des classes dont
    c'est la salle habituelle) ; salle retirée encore exigée ; type de salle sans salle en
    service, ou demandé au-delà des heures de ses salles. Le sport reçoit plusieurs cours à la
    fois : pas de dépassement pour lui."""
    demand: dict[UUID, int] = defaultdict(int)
    slots: dict[UUID, set[Slot]] = defaultdict(set)
    retired: dict[UUID, list[Course]] = defaultdict(list)
    kind_demand: dict[str, int] = defaultdict(int)
    kind_slots: dict[str, set[Slot]] = defaultdict(set)
    for course in courses:
        hours = course.weekly_hours or 0
        group = by_group.get(course.class_group_id)
        week = week_of.get(course.class_group_id)
        lessons = week.lessons if week else []
        room_id = course.room_id or (group.home_room_id if group and not course.room_kind else None)
        if course.room_kind:
            kind_demand[course.room_kind] += hours
            kind_slots[course.room_kind].update(lessons)
        elif room_id:
            demand[room_id] += hours
            slots[room_id].update(lessons)
            if course.room_id and not rooms[room_id].is_active:
                retired[room_id].append(course)
    issues = []
    for room_id, hours in demand.items():
        room = rooms[room_id]
        if room.kind != Room.Kind.SPORTS and hours > len(slots[room_id]):
            issues.append(
                Issue(
                    ROOMS,
                    "room_overloaded",
                    ERROR,
                    room.name,
                    {"hours": hours, "slots": len(slots[room_id])},
                    room=room_id,
                )
            )
    for room_id, items in retired.items():
        issues.append(
            Issue(ROOMS, "room_retired", ERROR, rooms[room_id].name, _names(items), room=room_id)
        )
    for kind, hours in kind_demand.items():
        same = [room for room in rooms.values() if room.kind == kind and room.is_active]
        if not same:
            issues.append(Issue(ROOMS, "room_kind_missing", ERROR, kind, {"hours": hours}))
            continue
        if kind == Room.Kind.SPORTS:
            continue
        week = len(kind_slots[kind])
        free = sum(max(0, week - demand.get(room.pk, 0)) for room in same)
        if hours > free:
            issues.append(
                Issue(ROOMS, "room_kind_overloaded", ERROR, kind, {"hours": hours, "slots": free})
            )
    return issues


def _incomplete(courses, staff, by_group) -> list[Issue]:
    """5. Enseignant parti de l'école (rouge) ; cours sans enseignant, cours sans heures
    (orange) : une ligne par classe ou par enseignant."""
    left: dict[UUID, list[Course]] = defaultdict(list)
    no_teacher: dict[UUID, list[Course]] = defaultdict(list)
    no_hours: dict[UUID, list[Course]] = defaultdict(list)
    for course in courses:
        if not course.weekly_hours:
            no_hours[course.class_group_id].append(course)
        if course.teacher_id is None:
            no_teacher[course.class_group_id].append(course)
        elif course.teacher_id not in staff:
            left[course.teacher_id].append(course)
    issues = [
        Issue(
            INCOMPLETE,
            "teacher_left",
            ERROR,
            str(items[0].teacher),
            {**_names(items), "hours": sum(course.weekly_hours or 0 for course in items)},
            teacher=teacher,
        )
        for teacher, items in left.items()
    ]
    for code, rows in (("no_teacher", no_teacher), ("no_hours", no_hours)):
        issues += [
            Issue(
                INCOMPLETE,
                code,
                WARNING,
                by_group[group].name,
                _names(items),
                class_group=group,
            )
            for group, items in rows.items()
        ]
    return issues

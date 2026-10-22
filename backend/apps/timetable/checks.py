"""Contrôles avant le calcul de l'horaire (EDT.1b, spec emploi du temps § 6) : ce qui rend
l'horaire impossible (rouge, `error`) ou incomplet (orange, `warning`), vu avant tout calcul.

Calcul Python pur sur l'année en cours, sans solveur ni IA : huit requêtes quelle que soit la
taille de l'école. Chaque ligne dit quoi (`subject`), combien (`values`) et où corriger (la classe,
l'enseignant, la salle ou la règle) ; les chiffres viennent d'ici, jamais de l'IA. EDT.1c : les
règles (`constraints.py`) ajoutent les contrôles 6 (verrous en conflit) et 7 (règles qui se
contredisent ou sans objet) ; les groupes en parallèle et les cours communs comptent une fois dans
les heures d'une classe et la charge d'un enseignant.
"""

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import time
from itertools import combinations
from uuid import UUID

from apps.academics.courses import active_staff
from apps.academics.models import Course
from apps.core.tenancy import require_current_school
from apps.schools.models import AcademicYear, ClassGroup
from apps.timetable import placement as placing
from apps.timetable.constraints import HARD, MIDDAY, MORNING, matches
from apps.timetable.models import (
    Room,
    TeacherTimetableProfile,
    TimeGrid,
    TimeSlot,
    Timetable,
    TimetableEntry,
    TimetableRule,
)
from apps.timetable.services import grids, rules_of

ERROR, WARNING = "error", "warning"
LEVELS = [ERROR, WARNING]
# Contrôles de la spec (§ 6) : 1 classes, 2 enseignants, 3 cours, 4 salles, 5 cours incomplets,
# 6 verrous en conflit, 7 règles qui se contredisent ou sans objet.
CLASSES, TEACHERS, COURSES, ROOMS, INCOMPLETE, LOCKS, RULES = 1, 2, 3, 4, 5, 6, 7
Kind = TimetableRule.Kind
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
    rule: UUID | None = None
    entry: UUID | None = None


@dataclass
class Lock:
    """Heures verrouillées d'une règle `fixed_lesson`, ou séance d'un brouillon (`entry`), placées
    dans la grille de la classe."""

    rule: TimetableRule | None
    course: Course
    label: str
    weekday: int
    first: int
    last: int
    is_last: bool
    start: time
    end: time
    slots: list[Slot]
    room: UUID | None
    entry: UUID | None = None


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

    def span(self, weekday: int, first: int, last: int, span_break: bool) -> list[TimeSlot] | str:
        """Les cases de la `first`e à la `last`e heure d'un jour, récréations comprises ; sinon la
        raison : `outside_grid` (heure absente ce jour-là), `crosses_break` (récréation que le
        cours ne passe pas)."""
        day = self.days.get(weekday, [])
        position = {
            slot.index: place for place, slot in enumerate(day) if slot.kind == TimeSlot.Kind.LESSON
        }
        if any(index not in position for index in range(first, last + 1)):
            return "outside_grid"
        run = day[position[first] : position[last] + 1]
        if not span_break and any(slot.kind == TimeSlot.Kind.BREAK for slot in run):
            return "crosses_break"
        return run

    def lessons_on(self, weekday: int) -> int:
        return sum(slot.kind == TimeSlot.Kind.LESSON for slot in self.days.get(weekday, []))

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


@dataclass
class Context:
    """Ce que lisent les contrôles d'une année : huit requêtes, quelle que soit la taille."""

    school_rules: dict
    groups: list[ClassGroup]
    week_of: dict[UUID, Week | None]
    courses: list[Course]
    staff: set[UUID]
    profiles: dict[UUID, TeacherTimetableProfile]
    rooms: dict[UUID, Room]
    by_group: dict[UUID, ClassGroup]
    rules: list[TimetableRule]
    by_course: dict[UUID, Course]
    parallel: list
    joint: list


def context(year: AcademicYear | None) -> Context:
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
    rules = list(TimetableRule.objects.filter(active=True))
    by_course = {course.pk: course for course in courses}
    parallel = _groups(rules, Kind.PARALLEL_COURSES, by_course)
    joint = _groups(rules, Kind.JOINT_COURSES, by_course)
    return Context(
        school_rules,
        groups,
        week_of,
        courses,
        staff,
        profiles,
        rooms,
        by_group,
        rules,
        by_course,
        parallel,
        joint,
    )


def run(year: AcademicYear | None) -> dict:
    """Les contrôles 1 à 7 sur l'année : lignes rouges d'abord, puis orange."""
    ctx = context(year)
    groups, courses, rules, rooms = ctx.groups, ctx.courses, ctx.rules, ctx.rooms
    week_of, by_group, by_course, staff = ctx.week_of, ctx.by_group, ctx.by_course, ctx.staff
    profiles, school_rules, parallel, joint = (
        ctx.profiles,
        ctx.school_rules,
        ctx.parallel,
        ctx.joint,
    )
    issues: list[Issue] = []
    issues += _classes(groups, courses, week_of, parallel)
    issues += _teachers(courses, staff, profiles, week_of, school_rules, joint)
    issues += _courses(courses, profiles, week_of, by_group, school_rules)
    issues += _rooms(courses, rooms, week_of, by_group)
    issues += _incomplete(courses, staff, by_group)
    locks, found = _locks(rules, by_course, week_of, by_group, rooms)
    issues += _lock_conflicts(locks, parallel, joint, rooms, by_group, "locks_")
    issues += found
    issues += _against(rules, locks, profiles, rooms, "lock_")
    issues += _orphans(rules, rooms, staff, by_course)
    issues += _group_issues(parallel, joint, by_group)
    issues.sort(key=lambda issue: (issue.level != ERROR, issue.check))
    return {
        "errors": sum(issue.level == ERROR for issue in issues),
        "warnings": sum(issue.level == WARNING for issue in issues),
        "classes": len(groups),
        "teachers": len({course.teacher_id for course in courses if course.teacher_id}),
        "rooms": sum(room.is_active for room in rooms.values()),
        "rules": len(rules),
        "issues": [asdict(issue) for issue in issues],
    }


def _groups(rules, kind, by_course) -> list[tuple[TimetableRule, list[Course]]]:
    """Les groupes d'un kind (parallèles, cours communs) avec leurs cours de l'année ; un cours
    n'est que dans un groupe actif (`constraints._check_groups`)."""
    return [
        (rule, [by_course[UUID(pk)] for pk in rule.params["courses"] if UUID(pk) in by_course])
        for rule in rules
        if rule.kind == kind
    ]


def _shared_hours(members: list[Course]) -> int:
    """Heures données en même temps par un groupe : comptées une fois (la plus longue)."""
    hours = [course.weekly_hours or 0 for course in members]
    return sum(hours) - max(hours) if len(hours) > 1 else 0


def _class_hours(courses, parallel) -> dict[UUID, int]:
    """Heures dues de chaque classe ; des groupes en parallèle ne comptent qu'une fois."""
    hours: dict[UUID, int] = defaultdict(int)
    for course in courses:
        hours[course.class_group_id] += course.weekly_hours or 0
    for _rule, members in parallel:
        if members:
            hours[members[0].class_group_id] -= _shared_hours(members)
    return hours


def _teacher_loads(courses, staff, joint) -> tuple[dict[UUID, int], dict[UUID, str]]:
    """Charge de chaque enseignant du personnel, et son nom ; un cours commun compte une fois."""
    load: dict[UUID, int] = defaultdict(int)
    names: dict[UUID, str] = {}
    for course in courses:
        if course.teacher_id not in staff or not course.weekly_hours:
            continue
        load[course.teacher_id] += course.weekly_hours
        names[course.teacher_id] = str(course.teacher)
    for _rule, members in joint:
        mine = [course for course in members if course.teacher_id in load]
        if mine and len({course.teacher_id for course in mine}) == 1:
            load[mine[0].teacher_id] -= _shared_hours(mine)
    return load, names


def _classes(groups, courses, week_of, parallel) -> list[Issue]:
    """1. Classe surchargée : heures des cours > places de sa grille ; des groupes en parallèle
    ne comptent qu'une fois."""
    hours = _class_hours(courses, parallel)
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


def _teachers(courses, staff, profiles, week_of, school_rules, joint) -> list[Issue]:
    """2. Enseignant au-delà de son maximum ; au-delà de ses heures libres (heures de cours des
    grilles de ses classes, absences retirées) ; au-delà de ce que ses jours permettent avec ses
    heures au plus par jour. Un cours commun à plusieurs classes compte une fois."""
    load, names = _teacher_loads(courses, staff, joint)
    slots: dict[UUID, set[Slot]] = defaultdict(set)
    for course in courses:
        week = week_of.get(course.class_group_id)
        if course.teacher_id in load and week is not None:
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


def _orphan(rule: TimetableRule) -> Issue:
    """7. Règle sans objet : son cours, sa salle ou son enseignant n'est plus là cette année."""
    return Issue(RULES, "rule_without_object", WARNING, rule.kind, rule=rule.pk)


def _locks(rules, by_course, week_of, by_group, rooms) -> tuple[list[Lock], list[Issue]]:
    """Les verrous placés dans la grille de leur classe ; 7. verrou hors de la grille, sur une
    récréation que le cours ne passe pas, ou qui n'est pas une de ses séances."""
    locks: list[Lock] = []
    issues: list[Issue] = []
    left: dict[UUID, Counter] = {}
    for rule in rules:
        if rule.kind != Kind.FIXED_LESSON:
            continue
        params = rule.params
        course = by_course.get(UUID(params["course"]))
        room_id = UUID(params["room"]) if params.get("room") else None
        if course is None or (room_id and not (room_id in rooms and rooms[room_id].is_active)):
            issues.append(_orphan(rule))
            continue
        week = week_of.get(course.class_group_id)
        if week is None:
            continue
        group = by_group[course.class_group_id]
        label = f"{course.name} · {group.name}"
        weekday, first, last = params["weekday"], params["first"], params["last"]

        def issue(
            code,
            values=None,
            rule=rule,
            label=label,
            course=course,
            day=weekday,
            span=(first, last),
        ):
            return Issue(
                RULES,
                code,
                ERROR,
                label,
                {"day": day, "first": span[0], "last": span[1], **(values or {})},
                class_group=course.class_group_id,
                rule=rule.pk,
            )

        run = week.span(weekday, first, last, placing.spans_break(course))
        if isinstance(run, str):
            issues.append(issue(f"lock_{run}", {"lessons": week.lessons_on(weekday)}))
            continue
        sessions = placing.sessions(course)
        length = last - first + 1
        counter = left.setdefault(course.pk, Counter(sessions))
        if counter[length] > 0:
            counter[length] -= 1
        else:
            pattern = "+".join(str(item) for item in sessions) or "0"
            issues.append(issue("lock_not_a_session", {"length": length, "sessions": pattern}))
        if room_id is None:
            room_id = course.room_id or (None if course.room_kind else group.home_room_id)
        locks.append(
            Lock(
                rule,
                course,
                label,
                weekday,
                first,
                last,
                last == week.lessons_on(weekday),
                run[0].start,
                run[-1].end,
                [(weekday, slot.start, slot.end) for slot in run if slot.kind == "lesson"],
                room_id,
            )
        )
    return locks, issues


def _lock_conflicts(locks, parallel, joint, rooms, by_group, prefix: str) -> list[Issue]:
    """6. Deux verrous (`locks_…`) ou deux séances d'un brouillon (`same_…`, O1 à O3) en même
    temps pour une même classe (hors groupes en parallèle), un même enseignant ou une même salle
    (hors cours commun ; le sport en reçoit plusieurs)."""
    side_by_side = {course.pk: rule.pk for rule, members in parallel for course in members}
    together = {course.pk: rule.pk for rule, members in joint for course in members}
    by_day: dict[int, list[Lock]] = defaultdict(list)
    for lock in locks:
        by_day[lock.weekday].append(lock)
    issues = []
    for day_locks in by_day.values():
        for a, b in combinations(day_locks, 2):
            if not (a.start < b.end and b.start < a.end):
                continue

            def same(groups, a=a, b=b):
                return a.course.pk in groups and groups[a.course.pk] == groups.get(b.course.pk)

            pair = {"first": a.label, "second": b.label, "day": a.weekday}
            if a.entry:
                pair["entries"] = [str(a.entry), str(b.entry)]
            course_a, course_b = a.course, b.course
            if course_a.pk == course_b.pk or (
                course_a.class_group_id == course_b.class_group_id and not same(side_by_side)
            ):
                issues.append(
                    Issue(
                        LOCKS,
                        f"{prefix}same_class",
                        ERROR,
                        by_group[course_a.class_group_id].name,
                        pair,
                        class_group=course_a.class_group_id,
                        rule=b.rule.pk if b.rule else None,
                        entry=b.entry,
                    )
                )
            elif (
                course_a.teacher_id
                and course_a.teacher_id == course_b.teacher_id
                and not same(together)
            ):
                issues.append(
                    Issue(
                        LOCKS,
                        f"{prefix}same_teacher",
                        ERROR,
                        str(course_a.teacher),
                        pair,
                        teacher=course_a.teacher_id,
                        rule=b.rule.pk if b.rule else None,
                        entry=b.entry,
                    )
                )
            if (
                a.room
                and a.room == b.room
                and rooms[a.room].kind != Room.Kind.SPORTS
                and course_a.pk != course_b.pk
                and not same(together)
            ):
                issues.append(
                    Issue(
                        LOCKS,
                        f"{prefix}same_room",
                        ERROR,
                        rooms[a.room].name,
                        pair,
                        room=a.room,
                        rule=b.rule.pk if b.rule else None,
                        entry=b.entry,
                    )
                )
    return issues


def _forbids(rule: TimetableRule, lock: Lock) -> bool:
    """La règle obligatoire (heures ou moment interdits au cours) tombe-t-elle sur le verrou ?"""
    params = rule.params
    if params["weekday"] not in (None, lock.weekday):
        return False
    if rule.kind == Kind.COURSE_PART_OF_DAY:
        morning = params["part"] == MORNING
        return any((start >= MIDDAY) == morning for _day, start, _end in lock.slots)
    if not params["lessons"] and not params["last"]:
        return True
    hours = range(lock.first, lock.last + 1)
    return any(index in hours for index in params["lessons"]) or (params["last"] and lock.is_last)


def _against(rules, locks, profiles, rooms, prefix: str) -> list[Issue]:
    """7. Verrou (`lock_…`) ou séance d'un brouillon (`entry_…`, O7) sur une absence de
    l'enseignant, sur une salle fermée, contre une règle obligatoire (heures, moment, jour
    libre)."""
    hard = [rule for rule in rules if rule.strength == HARD]
    closed: dict[UUID, list[dict]] = defaultdict(list)
    for rule in hard:
        if rule.kind == Kind.ROOM_UNAVAILABLE:
            params = {key: value for key, value in rule.params.items() if key != "room"}
            closed[UUID(rule.params["room"])].append(params)
    issues = []
    for lock in locks:
        course, teacher = lock.course, lock.course.teacher_id

        def issue(code, values, lock=lock, **where):
            return Issue(
                RULES,
                code,
                ERROR,
                lock.label,
                {"day": lock.weekday, "first": lock.first, "last": lock.last, **values},
                class_group=lock.course.class_group_id,
                rule=lock.rule.pk if lock.rule else None,
                entry=lock.entry,
                **where,
            )

        profile = profiles.get(teacher)
        if profile and any(is_blocked(profile.unavailable, slot) for slot in lock.slots):
            issues.append(
                issue(f"{prefix}on_absence", {"teacher": str(course.teacher)}, teacher=teacher)
            )
        if lock.room and any(is_blocked(closed[lock.room], slot) for slot in lock.slots):
            issues.append(issue(f"{prefix}on_closed_room", {"room": rooms[lock.room].name}))
        for rule in hard:
            against = (
                rule.kind in (Kind.COURSE_NOT_SLOT, Kind.COURSE_PART_OF_DAY)
                and matches(rule.params["target"], course)
                and _forbids(rule, lock)
            ) or (
                rule.kind == Kind.TEACHER_FREE_DAY
                and rule.params["teacher"] == str(teacher)
                and rule.params["weekday"] == lock.weekday
            )
            if against:
                issues.append(issue(f"{prefix}against_rule", {"other": rule.kind}))
                break
    return issues


def _orphans(rules, rooms, staff, by_course) -> list[Issue]:
    """7. Règle sans objet cette année."""
    issues = []
    courses = list(by_course.values())
    for rule in rules:
        params = rule.params
        if "target" in params:
            orphan = not any(matches(params["target"], course) for course in courses)
        elif rule.kind == Kind.ROOM_UNAVAILABLE:
            room = rooms.get(UUID(params["room"]))
            orphan = room is None or not room.is_active
        elif rule.kind in (Kind.TEACHER_COMPACT, Kind.TEACHER_FREE_DAY):
            orphan = bool(params["teacher"]) and UUID(params["teacher"]) not in staff
        else:
            continue
        if orphan:
            issues.append(_orphan(rule))
    return issues


def _group_issues(parallel, joint, by_group) -> list[Issue]:
    """7. Groupes en parallèle au même enseignant ; cours commun à enseignants différents ;
    heures ou séances différentes dans un groupe (ils se donnent en même temps) ; groupe sans
    objet."""
    issues = []
    for kind_groups, is_joint in ((parallel, False), (joint, True)):
        for rule, members in kind_groups:
            if len(members) < 2:
                issues.append(_orphan(rule))
                continue
            first = members[0]
            subject = first.name if is_joint else by_group[first.class_group_id].name
            names = ", ".join(
                f"{course.name} · {by_group[course.class_group_id].name}"
                if is_joint
                else course.name
                for course in members
            )

            def issue(
                code,
                values=None,
                rule=rule,
                subject=subject,
                names=names,
                first=first,
                joint=is_joint,
            ):
                return Issue(
                    RULES,
                    code,
                    ERROR,
                    subject,
                    {"names": names, **(values or {})},
                    class_group=None if joint else first.class_group_id,
                    rule=rule.pk,
                )

            teachers = [course.teacher_id for course in members]
            if is_joint and (len(set(teachers)) != 1 or teachers[0] is None):
                issues.append(issue("joint_teachers_differ"))
            mine = [teacher for teacher in teachers if teacher]
            if not is_joint and len(mine) != len(set(mine)):
                issues.append(issue("parallel_same_teacher"))
            hours = [course.weekly_hours or 0 for course in members]
            sessions = ["+".join(map(str, placing.sessions(course))) for course in members]
            if len(set(hours)) > 1:
                hours_text = ", ".join(str(value) for value in hours)
                issues.append(issue("group_hours_differ", {"hours": hours_text}))
            elif len(set(sessions)) > 1:
                # Donnés ensemble, séance par séance (EDT.3a).
                issues.append(issue("group_sessions_differ", {"sessions": ", ".join(sessions)}))
    return issues


def fixed_locks(year: AcademicYear) -> tuple[list[Lock], dict[UUID, Room]]:
    """Les verrous des règles `fixed_lesson` qui tiennent dans la grille de leur classe : un
    nouveau brouillon part de là (EDT.2a)."""
    ctx = context(year)
    locks, _issues = _locks(ctx.rules, ctx.by_course, ctx.week_of, ctx.by_group, ctx.rooms)
    return locks, ctx.rooms


def draft(timetable: Timetable) -> dict:
    """Conflits d'un brouillon (EDT.2a, spec § 8) : les contrôles du diagnostic rejoués sur ses
    séances (O1 à O3, O5 à O7), verrou d'une règle absent (O6), cours ou enseignant au-delà de
    son maximum du jour, charge de la semaine dépassée, séances du cours changées depuis le
    placement (O4), trou dans la journée d'une classe et salle à choisir (orange). Avec les
    séances, ce qui reste à placer et les heures placées / dues de chaque classe et enseignant.
    Neuf requêtes, quelle que soit la taille de l'école."""
    ctx = context(timetable.academic_year)
    entries = list(TimetableEntry.objects.filter(timetable=timetable))
    issues: list[Issue] = []
    placed: list[Lock] = []
    lengths: dict[UUID, list[int]] = defaultdict(list)
    gone = {entry.course_id for entry in entries if entry.course_id not in ctx.by_course}
    gone_names = dict(Course.objects.filter(pk__in=gone).values_list("pk", "name")) if gone else {}
    for entry in entries:
        last = entry.first + entry.length - 1
        where = {"day": entry.weekday, "first": entry.first, "last": last}
        course = ctx.by_course.get(entry.course_id)
        if course is None:
            name = gone_names.get(entry.course_id, "")
            issues.append(Issue(COURSES, "entry_course_gone", WARNING, name, where, entry=entry.pk))
            continue
        lengths[course.pk].append(entry.length)
        label = f"{course.name} · {ctx.by_group[course.class_group_id].name}"
        week = ctx.week_of.get(course.class_group_id)
        run = (
            week.span(entry.weekday, entry.first, last, placing.spans_break(course))
            if week
            else "outside_grid"
        )

        def issue(
            check,
            code,
            level=ERROR,
            values=None,
            course=course,
            label=label,
            where=where,
            pk=entry.pk,
        ):
            return Issue(
                check,
                code,
                level,
                label,
                where | (values or {}),
                class_group=course.class_group_id,
                entry=pk,
            )

        if isinstance(run, str):
            lessons = week.lessons_on(entry.weekday) if week else 0
            issues.append(issue(RULES, f"entry_{run}", values={"lessons": lessons}))
            continue
        if entry.room_id is None and course.room_kind:
            issues.append(issue(ROOMS, "room_missing", WARNING, {"kind": course.room_kind}))
        placed.append(
            Lock(
                None,
                course,
                label,
                entry.weekday,
                entry.first,
                last,
                last == week.lessons_on(entry.weekday),
                run[0].start,
                run[-1].end,
                [(entry.weekday, slot.start, slot.end) for slot in run if slot.kind == "lesson"],
                entry.room_id,
                entry.pk,
            )
        )
    issues += _lock_conflicts(placed, ctx.parallel, ctx.joint, ctx.rooms, ctx.by_group, "")
    issues += _against(ctx.rules, placed, ctx.profiles, ctx.rooms, "entry_")
    issues += _missing_locks(ctx, placed)
    issues += _day_overloads(ctx, placed)
    left, changed = _left(ctx, lengths)
    issues += changed
    classes, teachers, gaps, over = _loads(ctx, placed)
    issues += gaps + over
    issues.sort(key=lambda issue: (issue.level != ERROR, issue.check))
    return {
        "errors": sum(issue.level == ERROR for issue in issues),
        "warnings": sum(issue.level == WARNING for issue in issues),
        "entries": entries,
        "left": left,
        "classes": classes,
        "teachers": teachers,
        "issues": [asdict(issue) for issue in issues],
    }


def _missing_locks(ctx: Context, placed: list[Lock]) -> list[Issue]:
    """O6. Heures verrouillées par une règle sans la séance à sa place (ou dans sa salle)."""
    at = {(lock.course.pk, lock.weekday, lock.first, lock.last): lock.room for lock in placed}
    issues = []
    for rule in ctx.rules:
        if rule.kind != Kind.FIXED_LESSON:
            continue
        params = rule.params
        course = ctx.by_course.get(UUID(params["course"]))
        if course is None:
            continue
        key = (course.pk, params["weekday"], params["first"], params["last"])
        wanted = UUID(params["room"]) if params.get("room") else None
        if key not in at or (wanted and at[key] != wanted):
            issues.append(
                Issue(
                    LOCKS,
                    "lock_missing",
                    ERROR,
                    f"{course.name} · {ctx.by_group[course.class_group_id].name}",
                    {"day": params["weekday"], "first": params["first"], "last": params["last"]},
                    class_group=course.class_group_id,
                    rule=rule.pk,
                )
            )
    return issues


def _day_overloads(ctx: Context, placed: list[Lock]) -> list[Issue]:
    """Plus d'heures d'un cours dans la journée que son maximum ; plus d'heures d'un enseignant
    dans la journée que son maximum (profil, sinon règle de l'école)."""
    per_course: Counter = Counter()
    per_teacher: dict[tuple[UUID, int], set] = defaultdict(set)
    for lock in placed:
        per_course[(lock.course.pk, lock.weekday)] += len(lock.slots)
        if lock.course.teacher_id:
            per_teacher[(lock.course.teacher_id, lock.weekday)].update(lock.slots)
    issues = []
    school_max = ctx.school_rules["max_same_course_per_day"]
    for (course_id, weekday), hours in per_course.items():
        course = ctx.by_course[course_id]
        most = placing.max_per_day(course, school_max)
        if hours > most:
            issues.append(
                Issue(
                    COURSES,
                    "course_day_over",
                    ERROR,
                    f"{course.name} · {ctx.by_group[course.class_group_id].name}",
                    {"day": weekday, "hours": hours, "max": most},
                    class_group=course.class_group_id,
                )
            )
    names = {lock.course.teacher_id: str(lock.course.teacher) for lock in placed}
    for (teacher, weekday), slots in per_teacher.items():
        profile = ctx.profiles.get(teacher)
        most = (profile.max_day_hours if profile else None) or ctx.school_rules[
            "teacher_max_day_hours"
        ]
        if len(slots) > most:
            issues.append(
                Issue(
                    TEACHERS,
                    "teacher_day_over",
                    ERROR,
                    names[teacher],
                    {"day": weekday, "hours": len(slots), "max": most},
                    teacher=teacher,
                )
            )
    return issues


def _left(ctx: Context, lengths: dict[UUID, list[int]]) -> tuple[list[dict], list[Issue]]:
    """Séances restant à placer pour chaque cours ; séances placées qui ne sont plus les siennes
    (heures ou découpage changés après le placement)."""
    left, issues = [], []
    for course in ctx.courses:
        sessions = Counter(placing.sessions(course))
        mine = Counter(lengths.get(course.pk, []))
        if mine - sessions:
            issues.append(
                Issue(
                    COURSES,
                    "sessions_changed",
                    ERROR,
                    f"{course.name} · {ctx.by_group[course.class_group_id].name}",
                    {
                        "placed": "+".join(str(n) for n in sorted(mine.elements(), reverse=True)),
                        "sessions": "+".join(
                            str(n) for n in sorted(sessions.elements(), reverse=True)
                        )
                        or "0",
                    },
                    class_group=course.class_group_id,
                )
            )
        remaining = sorted((sessions - mine).elements(), reverse=True)
        if remaining:
            left.append({"course": course.pk, "lengths": remaining})
    return left, issues


def _loads(ctx: Context, placed: list[Lock]) -> tuple[list[dict], list[dict], list, list]:
    """Heures placées / dues de chaque classe (heures de sa grille occupées) et de chaque
    enseignant (heures où il enseigne), maximum de la semaine ; trous dans la journée d'une classe
    quand l'école n'en veut pas (orange : le brouillon est en cours) ; charge dépassée."""
    occupied: dict[UUID, set[tuple[int, int]]] = defaultdict(set)
    teaching: dict[UUID, set[Slot]] = defaultdict(set)
    for lock in placed:
        occupied[lock.course.class_group_id].update(
            (lock.weekday, index) for index in range(lock.first, lock.last + 1)
        )
        if lock.course.teacher_id:
            teaching[lock.course.teacher_id].update(lock.slots)
    due = _class_hours(ctx.courses, ctx.parallel)
    classes = [
        {"class_group": group.pk, "placed": len(occupied[group.pk]), "due": due[group.pk]}
        for group in ctx.groups
    ]
    gaps = []
    if ctx.school_rules["no_gaps"]:
        for group in ctx.groups:
            by_day: dict[int, set[int]] = defaultdict(set)
            for weekday, index in occupied[group.pk]:
                by_day[weekday].add(index)
            for weekday, indexes in sorted(by_day.items()):
                holes = sorted(set(range(1, max(indexes) + 1)) - indexes)
                if holes:
                    gaps.append(
                        Issue(
                            CLASSES,
                            "class_gap",
                            WARNING,
                            group.name,
                            {"day": weekday, "lessons": ", ".join(str(n) for n in holes)},
                            class_group=group.pk,
                        )
                    )
    load, names = _teacher_loads(ctx.courses, ctx.staff, ctx.joint)
    teachers, over = [], []
    for teacher in sorted(load, key=lambda pk: names[pk]):
        profile = ctx.profiles.get(teacher)
        most = profile.max_week_hours if profile else None
        hours = len(teaching[teacher])
        teachers.append(
            {
                "teacher": teacher,
                "name": names[teacher],
                "placed": hours,
                "due": load[teacher],
                "max": most,
            }
        )
        if most and hours > most:
            over.append(
                Issue(
                    TEACHERS,
                    "teacher_week_over",
                    ERROR,
                    names[teacher],
                    {"hours": hours, "max": most},
                    teacher=teacher,
                )
            )
    return classes, teachers, gaps, over

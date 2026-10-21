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


@dataclass
class Lock:
    """Heures verrouillées d'une règle `fixed_lesson`, placées dans la grille de la classe."""

    rule: TimetableRule
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
    rules = list(TimetableRule.objects.filter(active=True))
    by_course = {course.pk: course for course in courses}
    parallel = _groups(rules, Kind.PARALLEL_COURSES, by_course)
    joint = _groups(rules, Kind.JOINT_COURSES, by_course)

    issues: list[Issue] = []
    issues += _classes(groups, courses, week_of, parallel)
    issues += _teachers(courses, staff, profiles, week_of, school_rules, joint)
    issues += _courses(courses, profiles, week_of, by_group, school_rules)
    issues += _rooms(courses, rooms, week_of, by_group)
    issues += _incomplete(courses, staff, by_group)
    locks, found = _locks(rules, by_course, week_of, by_group, rooms)
    issues += _lock_conflicts(locks, parallel, joint, rooms, by_group)
    issues += found
    issues += _contradictions(rules, locks, profiles, rooms, staff, by_course, by_group)
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


def _classes(groups, courses, week_of, parallel) -> list[Issue]:
    """1. Classe surchargée : heures des cours > places de sa grille ; des groupes en parallèle
    ne comptent qu'une fois."""
    hours: dict[UUID, int] = defaultdict(int)
    for course in courses:
        hours[course.class_group_id] += course.weekly_hours or 0
    for _rule, members in parallel:
        if members:
            hours[members[0].class_group_id] -= _shared_hours(members)
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
    for _rule, members in joint:
        mine = [course for course in members if course.teacher_id in load]
        if mine and len({course.teacher_id for course in mine}) == 1:
            load[mine[0].teacher_id] -= _shared_hours(mine)
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
        day = week.days.get(weekday, [])
        position = {
            slot.index: place for place, slot in enumerate(day) if slot.kind == TimeSlot.Kind.LESSON
        }

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

        if any(index not in position for index in range(first, last + 1)):
            issues.append(issue("lock_outside_grid", {"lessons": len(position)}))
            continue
        run = day[position[first] : position[last] + 1]
        if not placing.spans_break(course) and any(
            slot.kind == TimeSlot.Kind.BREAK for slot in run
        ):
            issues.append(issue("lock_crosses_break"))
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
                last == max(position),
                run[0].start,
                run[-1].end,
                [(weekday, slot.start, slot.end) for slot in run if slot.kind == "lesson"],
                room_id,
            )
        )
    return locks, issues


def _lock_conflicts(locks, parallel, joint, rooms, by_group) -> list[Issue]:
    """6. Deux verrous qui se chevauchent pour une même classe (hors groupes en parallèle), un
    même enseignant ou une même salle (hors cours commun ; le sport en reçoit plusieurs)."""
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
            course_a, course_b = a.course, b.course
            if course_a.pk == course_b.pk or (
                course_a.class_group_id == course_b.class_group_id and not same(side_by_side)
            ):
                issues.append(
                    Issue(
                        LOCKS,
                        "locks_same_class",
                        ERROR,
                        by_group[course_a.class_group_id].name,
                        pair,
                        class_group=course_a.class_group_id,
                        rule=b.rule.pk,
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
                        "locks_same_teacher",
                        ERROR,
                        str(course_a.teacher),
                        pair,
                        teacher=course_a.teacher_id,
                        rule=b.rule.pk,
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
                        "locks_same_room",
                        ERROR,
                        rooms[a.room].name,
                        pair,
                        room=a.room,
                        rule=b.rule.pk,
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


def _contradictions(rules, locks, profiles, rooms, staff, by_course, by_group) -> list[Issue]:
    """7. Verrou sur une absence de l'enseignant, sur une salle fermée, contre une règle
    obligatoire (heures, moment, jour libre) ; règle sans objet."""
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
                rule=lock.rule.pk,
                **where,
            )

        profile = profiles.get(teacher)
        if profile and any(is_blocked(profile.unavailable, slot) for slot in lock.slots):
            issues.append(
                issue("lock_on_absence", {"teacher": str(course.teacher)}, teacher=teacher)
            )
        if lock.room and any(is_blocked(closed[lock.room], slot) for slot in lock.slots):
            issues.append(issue("lock_on_closed_room", {"room": rooms[lock.room].name}))
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
                issues.append(issue("lock_against_rule", {"other": rule.kind}))
                break
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
    heures différentes dans un groupe (ils se donnent en même temps) ; groupe sans objet."""
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
            if len(set(hours)) > 1:
                hours_text = ", ".join(str(value) for value in hours)
                issues.append(issue("group_hours_differ", {"hours": hours_text}))
    return issues

"""Emploi du temps de démonstration (EDT.1a) : la grille proposée, une salle par classe, et pour
l'ITIG ses ateliers, son laboratoire, sa salle informatique et son terrain. `volcans` travaille en
deux vacations : grille du matin et grille de l'après-midi, une salle pour deux classes. EDT.1b :
les ateliers exigent un atelier et se donnent en deux séances, le laboratoire, l'informatique et le
sport leur salle (quand l'école en a une), les cours principaux le matin ; l'enseignant des deux
écoles a ses absences et un maximum dans chacune. EDT.1c : les règles de l'ITIG (`_rules`).
Rejouable : grilles, salles, disponibilités et règles de l'espace sont refaites (espace de
démonstration seulement)."""

from collections import Counter, defaultdict
from datetime import time

from django.db.models import Q

from apps.academics.models import MAIN, MORNING, Course
from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace
from apps.schools.models import ClassGroup
from apps.schools.organisation import current_year
from apps.timetable import checks, constraints
from apps.timetable import placement as placing
from apps.timetable.models import (
    Room,
    TeacherTimetableProfile,
    TimeGrid,
    TimeSlot,
    Timetable,
    TimetableEntry,
    TimetableRule,
)
from apps.timetable.services import PRESET_LESSON_MINUTES, PRESET_START, week_shape

WORKSHOP, LAB, COMPUTER, SPORTS = (
    Room.Kind.WORKSHOP,
    Room.Kind.LAB,
    Room.Kind.COMPUTER,
    Room.Kind.SPORTS,
)
ITIG_ROOMS = (
    ("Atelier de mécanique générale", WORKSHOP, 30),
    ("Atelier de mécanique automobile", WORKSHOP, 30),
    ("Atelier d'électricité", WORKSHOP, 30),
    ("Atelier d'électronique", WORKSHOP, 25),
    ("Laboratoire de sciences", LAB, 40),
    ("Salle informatique", COMPUTER, 25),
    ("Terrain de sport", SPORTS, None),
)
VOLCANS_ROOMS = (("Laboratoire", LAB, 35), ("Cour de récréation", SPORTS, None))
# Disponibilités (EDT.1b), par numéro de compte : l'enseignant des deux écoles enseigne à l'ITIG
# sauf le mardi matin, et seulement le mardi et le jeudi à `volcans` ; le chef d'atelier.
PROFILES = {
    "itig": {
        "+243000001008": {
            "max_week_hours": 24,
            "unavailable": [{"weekday": 2, "start": "07:30", "end": "10:00"}],
        },
        "+243000001010": {"max_week_hours": 30, "max_day_hours": 7},
    },
    "volcans": {
        "+243000001008": {
            "max_week_hours": 6,
            "unavailable": [{"weekday": day} for day in (1, 3, 5, 6)],
        },
    },
}
# Après-midi de `volcans` : 12 h 30, heures de 45 min, 6 heures du lundi au vendredi.
AFTERNOON = {
    "lesson_minutes": 45,
    "start": time(12, 30),
    "lessons": {day: 6 for day in range(1, 6)},
    "breaks": ((3, 15),),
}


def _grid(name: str, *, is_default: bool, lesson_minutes: int, start: time, **shape) -> TimeGrid:
    grid = TimeGrid.objects.create(
        name=name, lesson_minutes=lesson_minutes, start_time=start, is_default=is_default
    )
    TimeSlot.objects.bulk_create(
        [TimeSlot(grid=grid, **slot) for slot in week_shape(lesson_minutes, start, **shape)]
    )
    return grid


def create_demo_timetable(spaces: list[DemoSpace]) -> None:
    for space in spaces:
        with use_school(space.school):
            Timetable.objects.all().delete()
            ClassGroup.objects.filter(
                Q(time_grid__isnull=False) | Q(home_room__isnull=False)
            ).update(time_grid=None, home_room=None)
            TimeGrid.objects.all().delete()
            Course.objects.filter(room__isnull=False).update(room=None)
            Room.objects.all().delete()
            TeacherTimetableProfile.objects.all().delete()
            TimetableRule.objects.all().delete()
            groups = list(
                ClassGroup.objects.filter(academic_year=current_year()).select_related(
                    "level", "track"
                )
            )
            two_shifts = space.profile == "volcans"
            _grid(
                "Avant-midi" if two_shifts else "Grille principale",
                is_default=True,
                lesson_minutes=PRESET_LESSON_MINUTES,
                start=PRESET_START,
            )
            afternoon = _grid("Après-midi", is_default=False, **AFTERNOON) if two_shifts else None
            # Deux vacations : la seconde moitié des classes l'après-midi, dans les mêmes salles.
            shared = (len(groups) + 1) // 2 if two_shifts else len(groups)
            classrooms = Room.objects.bulk_create(
                Room(name=f"Salle {number}", capacity=55) for number in range(1, shared + 1)
            )
            extra = VOLCANS_ROOMS if two_shifts else ITIG_ROOMS
            Room.objects.bulk_create(
                Room(name=label, kind=kind, capacity=places) for label, kind, places in extra
            )
            for position, group in enumerate(groups):
                group.home_room = classrooms[position % shared]
                group.time_grid = afternoon if position >= shared else None
            ClassGroup.objects.bulk_update(groups, ["home_room", "time_grid"])
            _place_courses({kind for _label, kind, _places in extra})
            for phone, fields in PROFILES.get(space.profile, {}).items():
                teacher = User.objects.get(phone=space.numbers.of(phone))
                TeacherTimetableProfile.objects.create(teacher=teacher, **fields)
            if space.profile == "itig":
                _rules()
                _draft()


def _place_courses(kinds: set[str]) -> None:
    """Salle exigée par type (si l'école a ce type), ateliers en deux séances, cours principaux
    le matin."""
    courses = list(Course.objects.filter(class_group__academic_year=current_year()))
    for course in courses:
        name = course.name.casefold()
        kind = ""
        if name.startswith("atelier") or name == "pratique professionnelle":
            kind = WORKSHOP
            hours = course.weekly_hours or 0
            course.lesson_pattern = f"{(hours + 1) // 2}+{hours // 2}" if hours >= 4 else ""
        elif name.startswith("labo"):
            kind = LAB
        elif name.startswith("informatique"):
            kind = COMPUTER
        elif name == "éducation physique":
            kind = SPORTS
        course.room_kind = kind if kind in kinds else ""
        if course.category == MAIN:
            course.preferred_part = MORNING
    Course.objects.bulk_update(courses, ["room_kind", "lesson_pattern", "preferred_part"])


def _rules() -> None:
    """L'atelier de la 2HT Électricité A verrouillé le lundi de la 2e à la 7e heure (une séance de
    6 h), les groupes en parallèle de la 1HT Électricité A (atelier et laboratoire), le laboratoire
    fermé le samedi, et quelques souhaits. Vérifiées comme par l'API (`constraints.clean`)."""
    courses = {
        (course.class_group.name, course.name): course
        for course in Course.objects.filter(
            class_group__academic_year=current_year(), is_taught=True
        ).select_related("class_group__level", "class_group__track")
    }
    workshop = courses[("2HT ÉLECTRICITÉ A", "Atelier électrique")]
    workshop.lesson_pattern = "6+1"
    workshop.save(update_fields=["lesson_pattern"])
    pair = [
        courses[("1HT ÉLECTRICITÉ A", name)]
        for name in ("Atelier électrique", "Laboratoire électrique")
    ]
    lab = Room.objects.get(name="Laboratoire de sciences")
    every = {"scope": constraints.ALL, "value": ""}
    rows = [
        ("fixed_lesson", {"course": str(workshop.pk), "weekday": 1, "first": 2, "last": 7}, {}),
        ("parallel_courses", {"courses": [str(course.pk) for course in pair]}, {}),
        ("room_unavailable", {"room": str(lab.pk), "weekday": 6}, {}),
        (
            "course_not_slot",
            {"target": {"scope": constraints.NAME, "value": "Éducation physique"}, "lessons": [1]},
            {"weight": 6},
        ),
        (
            "course_not_slot",
            {"target": {"scope": constraints.NAME, "value": "Mathématique"}, "last": True},
            {"weight": 4},
        ),
        ("spread_over_week", {"target": every}, {}),
        ("teacher_compact", {}, {}),
    ]
    TimetableRule.objects.bulk_create(
        TimetableRule(**constraints.clean({"kind": kind, "params": params, **extra}))
        for kind, params, extra in rows
    )


def _draft() -> None:
    """Un brouillon de l'ITIG (EDT.2a) : les heures verrouillées des règles, puis les séances de
    la classe de l'atelier verrouillé placées une à une à la première heure libre pour la classe
    et l'enseignant, sans dépasser le maximum du jour ; ce qui ne tient pas reste « à placer »
    (ses classes techniques ont plus d'heures que de places, EDT.3)."""
    year = current_year()
    locks, rooms = checks.fixed_locks(year)
    ctx = checks.context(year)
    draft = Timetable.objects.create(academic_year=year, name="Brouillon de démonstration")
    rows = [
        TimetableEntry(
            timetable=draft,
            course=lock.course,
            weekday=lock.weekday,
            first=lock.first,
            length=lock.last - lock.first + 1,
            room=rooms.get(lock.room),
            locked=True,
        )
        for lock in locks
    ]
    group = ctx.by_group[locks[0].course.class_group_id]
    week = ctx.week_of[group.pk]
    # (jour, heure) déjà pris, par classe et par enseignant.
    taken: dict = defaultdict(set)

    def book(row: TimetableEntry) -> None:
        hours = {(row.weekday, index) for index in range(row.first, row.first + row.length)}
        for owner in (row.course.class_group_id, row.course.teacher_id):
            if owner:
                taken[owner] |= hours

    def free_spot(course: Course, length: int, per_day: Counter, most: int):
        for weekday, day in sorted(week.days.items()):
            if per_day[weekday] + length > most:
                continue
            for slot in day:
                if slot.kind != TimeSlot.Kind.LESSON:
                    continue
                last = slot.index + length - 1
                if isinstance(
                    week.span(weekday, slot.index, last, placing.spans_break(course)), str
                ):
                    continue
                hours = {(weekday, index) for index in range(slot.index, last + 1)}
                if not any(
                    hours & taken[owner] for owner in (group.pk, course.teacher_id) if owner
                ):
                    return weekday, slot.index
        return None

    for row in rows:
        book(row)
    school_max = ctx.school_rules["max_same_course_per_day"]
    mine = [course for course in ctx.courses if course.class_group_id == group.pk]
    for course in sorted(mine, key=lambda course: -(course.weekly_hours or 0)):
        already = [row for row in rows if row.course.pk == course.pk]
        placed = Counter(row.length for row in already)
        per_day = Counter()
        for row in already:
            per_day[row.weekday] += row.length
        most = placing.max_per_day(course, school_max)
        for length in sorted((Counter(placing.sessions(course)) - placed).elements(), reverse=True):
            spot = free_spot(course, length, per_day, most)
            if spot is None:
                continue
            room = rooms.get(course.room_id) or (
                None if course.room_kind else rooms.get(group.home_room_id)
            )
            row = TimetableEntry(
                timetable=draft,
                course=course,
                weekday=spot[0],
                first=spot[1],
                length=length,
                room=room,
            )
            rows.append(row)
            book(row)
            per_day[spot[0]] += length
    TimetableEntry.objects.bulk_create(rows)

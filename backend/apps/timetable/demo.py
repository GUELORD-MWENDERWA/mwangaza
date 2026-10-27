"""Emploi du temps de démonstration (EDT.1a) : la grille proposée, une salle par classe, et pour
l'ITIG ses ateliers, son laboratoire, sa salle informatique et son terrain. `volcans` travaille en
deux vacations : grille du matin et grille de l'après-midi, une salle pour deux classes. EDT.1b :
les ateliers exigent un atelier et se donnent en deux séances, le laboratoire, l'informatique et le
sport leur salle (quand l'école en a une), les cours principaux le matin ; l'enseignant des deux
écoles a ses absences et un maximum dans chacune. EDT.1c : les règles de l'ITIG (`_rules`).
EDT.3a : les heures des classes de l'ITIG ramenées sous leur grille (`_fit_hours`), puis un
brouillon avec les heures verrouillées et son horaire calculé par le solveur (`_calculated`).
Rejouable : grilles, salles, disponibilités et règles de l'espace sont refaites (espace de
démonstration seulement)."""

from collections import defaultdict
from datetime import time, timedelta

from django.db.models import Q

from apps.academics.models import MAIN, MORNING, PRACTICAL, Course
from apps.accounts.models import User
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace
from apps.schools.models import ClassGroup, Term
from apps.schools.organisation import current_year
from apps.timetable import checks, constraints, exams, runs, versions
from apps.timetable.models import (
    ExamSchedule,
    ExamSitting,
    Room,
    TeacherTimetableProfile,
    TimeGrid,
    TimeSlot,
    Timetable,
    TimetableEntry,
    TimetableRule,
    TimetableRun,
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
# Heures d'une classe de l'ITIG au plus (39 places dans sa grille), et d'un laboratoire : sa salle
# reçoit sept classes et ferme le samedi.
CLASS_HOURS, LAB_HOURS = 36, 3
# Calcul de l'horaire de démonstration (refait à chaque `make demo`, trois fois dans son test) :
# un premier horaire en ≈ 4 s, puis des souhaits mieux tenus.
DEMO_SECONDS = 10


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
            ExamSchedule.objects.all().delete()
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
            if space.profile == "itig":
                _fit_hours()
            _place_courses({kind for _label, kind, _places in extra})
            for phone, fields in PROFILES.get(space.profile, {}).items():
                teacher = User.objects.get(phone=space.numbers.of(phone))
                TeacherTimetableProfile.objects.create(teacher=teacher, **fields)
            if space.profile == "itig":
                _rules()
                _calculated()
                _exams()


def _fit_hours() -> None:
    """Démonstration : tous les cours sont donnés, même ceux que le formulaire barre (décision du
    2026-10-16), et les classes techniques dépassent leur grille (41 à 62 h pour 39 places). Un
    laboratoire passe à 3 h, puis on retire une heure au plus gros cours qui n'est pas un atelier
    (à un atelier en dernier) jusqu'à 36 h."""
    courses = list(Course.objects.filter(class_group__academic_year=current_year(), is_taught=True))
    by_class = defaultdict(list)
    for course in courses:
        by_class[course.class_group_id].append(course)
        if course.name.casefold().startswith("labo"):
            course.weekly_hours = min(course.weekly_hours or 0, LAB_HOURS)
    for mine in by_class.values():
        while sum(course.weekly_hours or 0 for course in mine) > CLASS_HOURS:
            biggest = max(
                (course for course in mine if (course.weekly_hours or 0) > 1),
                key=lambda course: (
                    course.category != PRACTICAL,
                    course.weekly_hours,
                    -course.order,
                ),
            )
            biggest.weekly_hours -= 1
    Course.objects.bulk_update(courses, ["weekly_hours"])


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
    """L'atelier de la 2HT Électricité A verrouillé le lundi de la 2e à la 7e heure dans l'atelier
    d'électricité (une séance de 6 h), les groupes en parallèle de la 1HT Électricité A (atelier et
    laboratoire), le laboratoire fermé le samedi, et quelques souhaits. Vérifiées comme par l'API
    (`constraints.clean`)."""
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
    # Donnés en même temps : mêmes heures, mêmes séances.
    pair[1].weekly_hours, pair[1].lesson_pattern = pair[0].weekly_hours, pair[0].lesson_pattern
    pair[1].save(update_fields=["weekly_hours", "lesson_pattern"])
    lab = Room.objects.get(name="Laboratoire de sciences")
    room = Room.objects.get(name="Atelier d'électricité")
    every = {"scope": constraints.ALL, "value": ""}
    rows = [
        (
            "fixed_lesson",
            {"course": str(workshop.pk), "weekday": 1, "first": 2, "last": 7, "room": str(room.pk)},
            {},
        ),
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


def _calculated() -> None:
    """Un brouillon de l'ITIG avec les heures verrouillées des règles (EDT.2a), puis son horaire
    calculé une fois par le solveur, comme le ferait l'écran (EDT.3a), en temps court, et publié
    dès la rentrée (EDT.4a)."""
    year = current_year()
    locks, rooms = checks.fixed_locks(year)
    draft = Timetable.objects.create(academic_year=year, name="Brouillon de démonstration")
    TimetableEntry.objects.bulk_create(
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
    )
    run = TimetableRun.objects.create(request_id=uuid7(), timetable=draft, time_limit=DEMO_SECONDS)
    runs.execute(str(run.pk))
    run.refresh_from_db()
    if run.result is not None:
        versions.publish(run.result, valid_from=year.starts_on, actor=None)


def _exams() -> None:
    """EDT.5 : l'horaire des épreuves de la 1re période de l'ITIG, publié : les quatre premières
    classes, un jour chacune dès le premier lundi, deux cours le matin (l'examen puis une
    interrogation), leur enseignant surveillant, dans la salle de la classe."""
    year = current_year()
    term = Term.objects.filter(academic_year=year, kind=Term.Kind.PERIOD).order_by("order").first()
    start = term.starts_on or year.starts_on
    monday = start + timedelta(days=-start.weekday() % 7)
    schedule = ExamSchedule.objects.create(term=term)
    sittings = []
    groups = ClassGroup.objects.filter(academic_year=year).select_related("home_room")[:4]
    for day, group in enumerate(groups):
        courses = Course.objects.filter(class_group=group, is_taught=True)
        for course, (kind, begin, end) in zip(
            courses.order_by("order")[:2],
            (("exam", time(8, 0), time(10, 0)), ("quiz", time(10, 30), time(11, 30))),
            strict=False,
        ):
            sittings.append(
                ExamSitting(
                    schedule=schedule,
                    course=course,
                    kind=kind,
                    date=monday + timedelta(days=day),
                    start=begin,
                    end=end,
                    room=group.home_room,
                    invigilator=course.teacher,
                )
            )
    ExamSitting.objects.bulk_create(sittings)
    exams.publish(term, actor=None)

"""Emploi du temps de démonstration (EDT.1a) : la grille proposée, une salle par classe, et pour
l'ITIG ses ateliers, son laboratoire, sa salle informatique et son terrain. `volcans` travaille en
deux vacations : grille du matin et grille de l'après-midi, une salle pour deux classes. Rejouable :
les grilles et salles de l'espace sont refaites (espace de démonstration seulement)."""

from datetime import time

from django.db.models import Q

from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace
from apps.schools.models import ClassGroup
from apps.schools.organisation import current_year
from apps.timetable.models import Room, TimeGrid, TimeSlot
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
            ClassGroup.objects.filter(
                Q(time_grid__isnull=False) | Q(home_room__isnull=False)
            ).update(time_grid=None, home_room=None)
            TimeGrid.objects.all().delete()
            Room.objects.all().delete()
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

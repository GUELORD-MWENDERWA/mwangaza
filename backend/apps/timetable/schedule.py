"""Lecture de l'horaire publié (EDT.4b, spec § 10) : séances de la version publiée de l'année,
avec début et fin d'après la grille de chaque classe (un enseignant de deux vacations a ses vraies
heures), pour « Mon horaire » de l'enseignant et la page d'un enfant sur le Portail ; jamais un
brouillon. Et, à la publication, les enseignants et les classes dont les séances changent (à
prévenir, `notifications.events.timetable_published`)."""

from dataclasses import dataclass
from datetime import time
from uuid import UUID

from django.db.models import Prefetch, Q

from apps.schools import organisation
from apps.schools.models import ClassGroup
from apps.timetable import checks
from apps.timetable.models import TimeGrid, TimeSlot, Timetable, TimetableEntry


@dataclass(frozen=True)
class Lesson:
    weekday: int
    first: int
    length: int
    start: time | None
    end: time | None
    course: str
    class_group: str
    teacher: str
    room: str
    teacher_id: UUID | None
    class_group_id: UUID
    course_id: UUID
    room_id: UUID | None


def published(year_id) -> Timetable | None:
    """La version publiée de l'année (une seule à la fois), même si elle n'entre en vigueur que
    plus tard : c'est elle qu'on prépare."""
    if year_id is None:
        return None
    return Timetable.objects.filter(
        academic_year_id=year_id, status=Timetable.Status.PUBLISHED
    ).first()


def lessons(timetable: Timetable | None, where: Q) -> list[Lesson]:
    """Séances de la version qui répondent à `where`, par jour puis par heure. Grille de la
    classe, sinon celle par défaut ; une séance que la grille ne porte plus (grille changée après
    la publication) garde ses numéros d'heure, sans horaire. Le nom de l'enseignant seulement
    (jamais son téléphone, qui sert de nom à un compte sans nom). Trois requêtes."""
    if timetable is None:
        return []
    entries = (
        TimetableEntry.objects.filter(where, timetable=timetable)
        .select_related("course__class_group", "course__teacher", "room")
        .order_by("weekday", "first")
    )
    grids = list(
        TimeGrid.objects.prefetch_related(
            Prefetch("slots", queryset=TimeSlot.objects.order_by("weekday", "start"))
        )
    )
    weeks = {grid.pk: checks.Week(grid) for grid in grids}
    default = next((weeks[grid.pk] for grid in grids if grid.is_default), None)
    found = []
    for entry in entries:
        course, group = entry.course, entry.course.class_group
        week = weeks.get(group.time_grid_id, default)
        last = entry.first + entry.length - 1
        run = week.span(entry.weekday, entry.first, last, True) if week else None
        start, end = (run[0].start, run[-1].end) if isinstance(run, list) else (None, None)
        found.append(
            Lesson(
                weekday=entry.weekday,
                first=entry.first,
                length=entry.length,
                start=start,
                end=end,
                course=course.name,
                class_group=group.name,
                teacher=course.teacher.get_full_name() if course.teacher else "",
                room=entry.room.name if entry.room else "",
                teacher_id=course.teacher_id,
                class_group_id=group.pk,
                course_id=course.pk,
                room_id=entry.room_id,
            )
        )
    found.sort(key=lambda row: (row.weekday, row.start is None, row.start, row.first))
    return found


def mine(user) -> dict:
    """« Mon horaire » (Gestion) : les séances du compte et, s'il est titulaire d'une classe de
    l'année en cours, celles de sa classe ; une seule lecture des séances."""
    year = organisation.current_year()
    version = published(year.pk if year else None)
    homeroom = (
        ClassGroup.objects.filter(academic_year=year, homeroom_teacher=user).first()
        if year
        else None
    )
    where = Q(course__teacher=user)
    if homeroom:
        where |= Q(course__class_group=homeroom)
    found = lessons(version, where)
    return {
        "timetable": version,
        "lessons": [lesson for lesson in found if lesson.teacher_id == user.pk],
        "homeroom": homeroom
        and {
            "class_group": homeroom.name,
            "lessons": [lesson for lesson in found if lesson.class_group_id == homeroom.pk],
        },
    }


def touched(before: Timetable | None, after: Timetable) -> tuple[set[UUID], set[UUID]]:
    """Enseignants et classes dont les séances diffèrent d'une version à l'autre (cours, jour,
    heures, salle) ; tout ce qu'a la nouvelle quand il n'y en avait pas avant."""

    def rows(version: Timetable | None) -> set[tuple]:
        if version is None:
            return set()
        return set(
            TimetableEntry.objects.filter(timetable=version).values_list(
                "course_id",
                "course__teacher_id",
                "course__class_group_id",
                "weekday",
                "first",
                "length",
                "room_id",
            )
        )

    changed = rows(before) ^ rows(after)
    return {row[1] for row in changed if row[1]}, {row[2] for row in changed}

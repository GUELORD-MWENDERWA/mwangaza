"""Impressions de l'horaire (EDT.4c, spec § 11) : horaire d'une classe, d'un enseignant (avec sa
charge), d'une salle, et horaire général, d'une version au choix. Les séances de toute la version
sont lues une fois (`schedule.lessons`), puis réparties page par page en mémoire : le nombre de
requêtes ne dépend ni du nombre de classes ni du nombre d'enseignants."""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import time
from math import ceil
from uuid import UUID

from django.db.models import Q
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.academics.models import Course
from apps.core.errors import ApiError, BusinessError
from apps.schools.models import ClassGroup
from apps.timetable import schedule
from apps.timetable.models import Room, TeacherTimetableProfile, TimeGrid, TimeSlot, Timetable
from apps.timetable.services import DAY_NAMES, grids

CLASS, TEACHER, ROOM, GENERAL = "class", "teacher", "room", "general"
KINDS = (CLASS, TEACHER, ROOM, GENERAL)
NOTHING = ApiError(
    "nothing_to_print", gettext_lazy("There is nothing to print in this timetable."), 409
)
NO_GRID = ApiError("no_grid", gettext_lazy("The school has no time grid yet."), 409)
NOT_FOUND = ApiError("not_found", gettext_lazy("Not found."), 404)
Key = tuple[int, int]  # (n° d'heure, 0) pour une heure de cours ; (n° de l'heure avant, 1) : pause

# Mots sans valeur dans un nom de cours (même liste que `editor.ts`).
SMALL_WORDS = frozenset(
    [
        "de",
        "du",
        "des",
        "la",
        "le",
        "les",
        "l",
        "d",
        "et",
        "à",
        "au",
        "aux",
        "en",
        "pour",
        "sur",
        "of",
        "the",
        "and",
        "for",
        "to",
    ]
)


@dataclass
class Row:
    key: Key
    label: str
    start: time
    end: time

    @property
    def is_break(self) -> bool:
        return self.key[1] == 1


def structure(grid: TimeGrid) -> tuple[list[int], list[Row]]:
    """Jours de la grille et lignes du tableau (heures de cours et récréations, dans l'ordre) ;
    une heure dont l'horaire varie d'un jour à l'autre prend celui du premier jour."""
    by_day = defaultdict(list)
    for slot in grid.slots.all():  # rangées par jour puis heure (`services.grids`)
        by_day[slot.weekday].append(slot)
    found: dict[Key, Row] = {}
    for weekday in sorted(by_day):
        last = 0
        for slot in by_day[weekday]:
            if slot.kind == TimeSlot.Kind.LESSON and slot.index:
                last = slot.index
                key, label = (last, 0), str(last)
            else:
                key, label = (last, 1), ""
            found.setdefault(key, Row(key, label, slot.start, slot.end))
    return sorted(by_day), [found[key] for key in sorted(found)]


def lesson_text(kind: str, lesson: schedule.Lesson, row_start: time) -> dict:
    """Ce qu'une case écrit : le cours en gras, puis ce qui change selon le document ; l'heure
    seulement si elle n'est pas celle de la ligne (classe d'une autre grille)."""
    other = {CLASS: (lesson.teacher, lesson.room), TEACHER: (lesson.class_group, lesson.room)}
    details = other.get(kind, (lesson.class_group, lesson.teacher))
    return {
        "title": lesson.course,
        "detail": " · ".join(part for part in details if part),
        "time": f"{lesson.start:%H:%M}\N{EN DASH}{lesson.end:%H:%M}"
        if lesson.start and lesson.end and lesson.start != row_start
        else "",
    }


def table(grid: TimeGrid, kind: str, lessons: list[schedule.Lesson]) -> dict:
    """Le tableau d'une page : une ligne par heure ou récréation, une colonne par jour. La case de
    départ d'une séance porte son texte et couvre les lignes de sa durée (`rowspan`) ; les lignes
    couvertes ne s'impriment pas. Une récréation au milieu d'une séance (atelier de la 2e à la
    7e heure) reste une récréation, pour tous : la séance se coupe autour d'elle (2026-10-27).
    Une séance que la grille ne porte plus est listée à part."""
    days, rows = structure(grid)
    index = {row.key: i for i, row in enumerate(rows)}
    cells: list[list] = [[None] * len(days) for _ in rows]  # None : vide ; "skip" : couverte
    outside = []
    for lesson in sorted(lessons, key=lambda x: (x.weekday, x.first, -x.length)):
        start, end = (lesson.first, 0), (lesson.first + lesson.length - 1, 0)
        if lesson.weekday not in days or start not in index or end not in index:
            outside.append(lesson)
            continue
        column, first = days.index(lesson.weekday), index[start]
        text = lesson_text(kind, lesson, rows[first].start)
        runs: list[list[int]] = [[]]
        for i in range(first, index[end] + 1):
            if rows[i].is_break:
                runs.append([])
            else:
                runs[-1].append(i)
        for run in filter(None, runs):
            head = run[0]
            if isinstance(cells[head][column], dict):  # cours en parallèle (groupes) : même case
                cells[head][column]["lessons"].append(text)
                continue
            cells[head][column] = {"lessons": [text], "rowspan": len(run)}
            for i in run[1:]:
                cells[i][column] = "skip"
    return {
        "days": [str(DAY_NAMES[day - 1]) for day in days],
        "rows": [
            {
                "label": row.label,
                "times": f"{row.start:%H:%M}\N{EN DASH}{row.end:%H:%M}",
                "is_break": row.is_break,
                "cells": line,
            }
            for row, line in zip(rows, cells, strict=True)
        ],
        "outside": [
            {
                **lesson_text(kind, x, time.min),
                "day": str(DAY_NAMES[x.weekday - 1]),
                "first": x.first,
            }
            for x in outside
        ],
    }


def version_note(timetable: Timetable) -> str:
    if timetable.status == Timetable.Status.DRAFT:
        return _("DRAFT | not published")
    since = date_format(timetable.valid_from, "d/m/Y") if timetable.valid_from else ""
    if timetable.status == Timetable.Status.ARCHIVED:
        return _("Archived version «%(name)s»") % {"name": timetable.name}
    return _("In force since %(date)s") % {"date": since}


def short_names(courses) -> dict[str, str]:
    """Nom court de chaque cours, comme à l'écran (`shortNames` de `editor.ts`) : un mot → ses 4
    premières lettres ; plusieurs → 3 lettres du premier et l'initiale des suivants (2 au plus) ;
    deux cours d'une même classe ne gardent pas le même nom court, le mot qui les distingue
    s'allonge. `courses` : paires (nom, classe)."""
    words = {}
    for name in {name for name, _group in courses}:
        parts = (re.sub(r"[^\w]", "", part) for part in re.split(r"[\s'\u2019/,-]+", name))
        words[name] = [w for w in parts if w and w.lower() not in SMALL_WORDS][:3]
    sizes = {
        name: [(4 if len(parts) == 1 else 3) if i == 0 else 1 for i in range(len(parts))]
        for name, parts in words.items()
    }

    def code(name: str) -> str:
        if not words[name]:
            return name[:4]
        return "".join(
            word[: sizes[name][i]][:1].upper() + word[: sizes[name][i]][1:]
            for i, word in enumerate(words[name])
        )

    together = defaultdict(set)
    for name, group in courses:
        together[group].add(name)
    for _round in range(8):
        longer = False
        for names in together.values():
            by_code = defaultdict(list)
            for name in sorted(names):
                by_code[code(name)].append(name)
            for same in (group for group in by_code.values() if len(group) > 1):
                for name in same:
                    mine = words[name]
                    other = words[next(n for n in same if n != name)]
                    at = next(
                        (
                            i
                            for i, w in enumerate(mine)
                            if i >= len(other) or w.lower() != other[i].lower()
                        ),
                        0,
                    )
                    if at < len(mine) and sizes[name][at] < len(mine[at]):
                        sizes[name][at] += 1
                        longer = True
        if not longer:
            break
    return {name: code(name) for name in words}


def timetable_of(pk: UUID | None, year_id) -> Timetable:
    """La version demandée (brouillon, publiée ou archivée, de l'école courante) ou, sans
    demande, la publiée de l'année en cours."""
    found = Timetable.objects.filter(pk=pk).first() if pk else schedule.published(year_id)
    if found is None:
        raise BusinessError(NOT_FOUND)
    return found


def _context(timetable: Timetable, kind: str, **extra) -> dict:
    return {"kind": kind, "timetable": timetable, "version": version_note(timetable), **extra}


def classes_of(timetable: Timetable, subject: UUID | None) -> list[ClassGroup]:
    groups = ClassGroup.objects.filter(academic_year_id=timetable.academic_year_id).select_related(
        "homeroom_teacher"
    )
    if subject:
        groups = groups.filter(pk=subject)
    return list(groups)


def document(
    kind: str, timetable: Timetable, subject: UUID | None, *, one_sheet: bool = False
) -> list[tuple[UUID, dict]]:
    """Les pages du document : (identifiant de ce qu'elles montrent, contexte du gabarit). Sans
    `subject`, toutes les classes (ou enseignants, ou salles) qui ont des séances ; `one_sheet` :
    l'horaire général sur une seule page (A3)."""
    all_grids = grids()
    if not all_grids:
        raise BusinessError(NO_GRID)
    by_id = {grid.pk: grid for grid in all_grids}
    default = (
        all_grids[0]
        if all_grids[0].is_default
        else next((grid for grid in all_grids if grid.is_default), all_grids[0])
    )
    lessons = schedule.lessons(timetable, Q())
    if kind == GENERAL:
        pages = [(timetable.pk, general(timetable, lessons, by_id, default, one_sheet=one_sheet))]
    else:
        pages = {CLASS: by_class, TEACHER: by_teacher, ROOM: by_room}[kind](
            timetable, lessons, subject, by_id, default
        )
    if not pages:
        raise BusinessError(NOT_FOUND if subject else NOTHING)
    return pages


def by_class(timetable, lessons, subject, by_id, default):
    mine = defaultdict(list)
    for lesson in lessons:
        mine[lesson.class_group_id].append(lesson)
    pages = []
    for group in classes_of(timetable, subject):
        if not subject and group.pk not in mine:
            continue
        grid = by_id.get(group.time_grid_id, default)
        found = mine[group.pk]
        pages.append(
            (
                group.pk,
                _context(
                    timetable,
                    CLASS,
                    title=_("Timetable of %(name)s") % {"name": group.name},
                    homeroom=group.homeroom_teacher.get_full_name()
                    if group.homeroom_teacher
                    else "",
                    hours=sum(lesson.length for lesson in found),
                    **table(grid, CLASS, found),
                ),
            )
        )
    if subject and not pages:
        raise BusinessError(NOT_FOUND)
    return pages


def by_teacher(timetable, lessons, subject, by_id, default):
    courses = Course.objects.filter(
        class_group__academic_year_id=timetable.academic_year_id, teacher__isnull=False
    ).select_related("teacher", "class_group")
    if subject:
        courses = courses.filter(teacher_id=subject)
    owned = defaultdict(list)
    for course in courses.order_by(
        *ClassGroup._meta.ordering and [f"class_group__{f}" for f in ClassGroup._meta.ordering],
        "name",
    ):
        owned[course.teacher].append(course)
    placed = Counter()
    mine = defaultdict(list)
    for lesson in lessons:
        placed[lesson.course_id] += lesson.length
        if lesson.teacher_id:
            mine[lesson.teacher_id].append(lesson)
    limits = dict(TeacherTimetableProfile.objects.values_list("teacher_id", "max_week_hours"))
    pages = []
    for teacher, taught in sorted(owned.items(), key=lambda item: item[0].get_full_name()):
        found = mine[teacher.pk]
        if not found and not subject:
            continue
        load = [
            {
                "class_group": course.class_group.name,
                "course": course.name,
                "due": course.weekly_hours or 0,
                "placed": placed[course.pk],
            }
            for course in taught
        ]
        pages.append(
            (
                teacher.pk,
                _context(
                    timetable,
                    TEACHER,
                    title=_("Timetable of %(name)s") % {"name": teacher.get_full_name()},
                    load=load,
                    due=sum(row["due"] for row in load),
                    hours=sum(row["placed"] for row in load),
                    limit=limits.get(teacher.pk),
                    **table(default, TEACHER, found),
                ),
            )
        )
    return pages


def by_room(timetable, lessons, subject, by_id, default):
    mine = defaultdict(list)
    for lesson in lessons:
        if lesson.room_id:
            mine[lesson.room_id].append(lesson)
    rooms = Room.objects.filter(pk=subject) if subject else Room.objects.filter(is_active=True)
    return [
        (
            room.pk,
            _context(
                timetable,
                ROOM,
                title=_("Timetable of %(name)s") % {"name": room.name},
                hours=sum(lesson.length for lesson in mine[room.pk]),
                **table(default, ROOM, mine[room.pk]),
            ),
        )
        for room in rooms.order_by("name")
        if subject or mine[room.pk]
    ]


def general(timetable, lessons, by_id, default, *, one_sheet: bool = False) -> dict:
    """Toutes les classes en lignes, les heures de chaque jour en colonnes, le nom court du cours
    dans chaque case ; légende dessous. Sur A4, la semaine tient sur deux pages (début et fin de
    semaine) ; sur A3, sur une."""
    mine = defaultdict(list)
    for lesson in lessons:
        mine[lesson.class_group_id].append(lesson)
    groups = [group for group in classes_of(timetable, None) if group.pk in mine]
    if not groups:
        raise BusinessError(NOTHING)
    courses = list(
        Course.objects.filter(class_group__academic_year_id=timetable.academic_year_id).values_list(
            "name", "class_group_id", "weekly_hours"
        )
    )
    codes = short_names([(name, group) for name, group, _hours in courses])
    due = Counter()
    for _name, group, hours in courses:
        due[group] += hours or 0
    used = {by_id.get(group.time_grid_id, default) for group in groups}
    width: dict[int, int] = defaultdict(int)  # dernière heure de cours de chaque jour
    for grid in used:
        for slot in grid.slots.all():
            if slot.kind == TimeSlot.Kind.LESSON and slot.index:
                width[slot.weekday] = max(width[slot.weekday], slot.index)
    days = sorted(width)
    cut = ceil(len(days) / 2)
    halves = [days] if one_sheet else [half for half in (days[:cut], days[cut:]) if half]
    legend: dict[str, set[str]] = defaultdict(set)
    sheets = []
    for half in halves:
        lines = []
        for group in groups:
            grid = by_id.get(group.time_grid_id, default)
            has = {(s.weekday, s.index) for s in grid.slots.all() if s.kind == TimeSlot.Kind.LESSON}
            starts = defaultdict(list)
            for lesson in mine[group.pk]:
                starts[(lesson.weekday, lesson.first)].append(lesson)
            cells = []
            for day in half:
                skip_until = 0
                for hour in range(1, width[day] + 1):
                    if hour <= skip_until:
                        continue
                    first = hour == 1
                    found = starts.get((day, hour))
                    if not found:
                        state = "free" if (day, hour) in has else "off"
                        cells.append({"state": state, "span": 1, "first": first})
                        continue
                    span = min(max(x.length for x in found), width[day] - hour + 1)
                    skip_until = hour + span - 1
                    names = sorted({x.course for x in found})
                    for name in names:
                        legend[codes.get(name, name)].add(name)
                    cells.append(
                        {
                            "text": "/".join(codes.get(name, name) for name in names),
                            "title": ", ".join(names),
                            "span": span,
                            "first": first,
                        }
                    )
            placed = sum(x.length for x in mine[group.pk])
            lines.append(
                {"name": group.name, "placed": placed, "due": due[group.pk], "cells": cells}
            )
        names = [str(DAY_NAMES[day - 1]) for day in half]
        sheets.append(
            {
                "title": _("General timetable")
                if not names[1:] or one_sheet
                else f"{_('General timetable')} \N{EN DASH} {names[0]} / {names[-1]}",
                "days": [
                    {"name": name, "hours": range(1, width[day] + 1)}
                    for name, day in zip(names, half, strict=True)
                ],
                "lines": lines,
            }
        )
    return _context(
        timetable,
        GENERAL,
        title=_("General timetable"),
        sheets=sheets,
        legend=sorted((code, " / ".join(sorted(names))) for code, names in legend.items()),
    )

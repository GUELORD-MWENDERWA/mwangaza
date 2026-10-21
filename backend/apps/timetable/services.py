"""Paramètres de l'emploi du temps (EDT.1a, spec § 3) : grilles horaires et leurs cases, salles,
grille et salle habituelle de chaque classe, capacité comparée aux heures de cours, règles
générales de l'école (`School.settings["timetable"]`). Chaque changement va dans le journal."""

import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from itertools import pairwise

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.academics.courses import active_staff
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools import organisation
from apps.schools.models import AcademicYear, ClassGroup, School
from apps.timetable.models import (
    MAX_LESSONS_PER_DAY,
    MAX_SLOT_MINUTES,
    MIN_SLOT_MINUTES,
    Room,
    TeacherTimetableProfile,
    TimeGrid,
    TimeSlot,
)

LESSON, BREAK = TimeSlot.Kind.LESSON, TimeSlot.Kind.BREAK

# Préréglage proposé à une école neuve et utilisé par `make demo` (spec § 3, question Q16 de
# `06`) : chaque école le change ensuite. 5 jours de 7 heures et le samedi de 4 : 39 places.
PRESET_LESSON_MINUTES = 50
PRESET_START = time(7, 30)
PRESET_LESSONS = {1: 7, 2: 7, 3: 7, 4: 7, 5: 7, 6: 4}
# (après la Ne heure, minutes)
PRESET_BREAKS = ((3, 15), (5, 10))

# Règles générales (spec § 3) : lues par le diagnostic (EDT.1b) et le calcul (EDT.3).
DEFAULT_RULES = {
    "max_same_course_per_day": 2,
    "teacher_max_day_hours": 6,
    "no_gaps": True,
    "main_courses_early": True,
}
# Au plus quelques dizaines de salles par école : la liste n'est pas paginée.
ROOMS_LIMIT = 300

DAY_NAMES = (
    _("Monday"),
    _("Tuesday"),
    _("Wednesday"),
    _("Thursday"),
    _("Friday"),
    _("Saturday"),
    _("Sunday"),
)

GRID_EXISTS = ApiError("grid_exists", _("Another time grid already has this name."), 409)
DEFAULT_GRID_KEPT = ApiError(
    "default_grid",
    _("The default time grid stays: make another grid the default first."),
    409,
)
ROOM_EXISTS = ApiError("room_exists", _("Another room already has this name."), 409)
TOO_MANY_ROOMS = ApiError("too_many_rooms", _("The school already has 300 rooms."), 409)
UNKNOWN_GRID = ApiError("unknown_grid", _("This time grid does not exist."), 400)
UNKNOWN_ROOM = ApiError("unknown_room", _("This room does not exist."), 400)
ROOM_RETIRED = ApiError("room_retired", _("This room is no longer in use."), 400)
NO_LESSON = ApiError("no_lesson", _("The grid needs at least one lesson."), 400)
UNKNOWN_TEACHER = ApiError("unknown_teacher", _("This person is not on the school's staff."), 404)


def _bad_slots(weekday: int, message) -> BusinessError:
    detail = gettext("%(day)s: %(problem)s") % {"day": DAY_NAMES[weekday - 1], "problem": message}
    return BusinessError(ApiError("bad_slots", detail, 400))


def _minutes(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


# --------------------------------------------------------------------------- grilles


def week_shape(
    lesson_minutes: int,
    start: time,
    lessons: dict[int, int] = PRESET_LESSONS,
    breaks: tuple[tuple[int, int], ...] = PRESET_BREAKS,
) -> list[dict]:
    """Cases de la semaine calculées : chaque jour commence à `start`, chaque heure dure
    `lesson_minutes`, une récréation suit la Ne heure s'il y a une heure après elle."""
    after = dict(breaks)
    slots: list[dict] = []
    for weekday, count in lessons.items():
        moment = datetime.combine(date(2000, 1, 3), start)
        for index in range(1, count + 1):
            end = moment + timedelta(minutes=lesson_minutes)
            slots.append(
                {
                    "weekday": weekday,
                    "index": index,
                    "kind": LESSON,
                    "start": moment.time(),
                    "end": end.time(),
                }
            )
            moment = end
            if index in after and index < count:
                end = moment + timedelta(minutes=after[index])
                slots.append(
                    {
                        "weekday": weekday,
                        "index": None,
                        "kind": BREAK,
                        "start": moment.time(),
                        "end": end.time(),
                    }
                )
                moment = end
    return slots


def check_slots(slots: list[dict]) -> None:
    """Refuse une semaine incohérente : cases d'un jour qui se chevauchent ou laissent un trou,
    récréation en début ou en fin de journée, heures mal numérotées, case trop courte ou trop
    longue. Message avec le jour concerné."""
    days: dict[int, list[dict]] = defaultdict(list)
    for slot in slots:
        days[slot["weekday"]].append(slot)
    if not any(slot["kind"] == LESSON for slot in slots):
        raise BusinessError(NO_LESSON)
    for weekday, day in sorted(days.items()):
        day.sort(key=lambda slot: slot["start"])
        for slot in day:
            length = _minutes(slot["start"], slot["end"])
            if not MIN_SLOT_MINUTES <= length <= MAX_SLOT_MINUTES:
                raise _bad_slots(weekday, _("each slot lasts between 5 minutes and 4 hours."))
        for before, after in pairwise(day):
            if before["end"] != after["start"]:
                raise _bad_slots(weekday, _("each slot starts when the previous one ends."))
        if day[0]["kind"] == BREAK or day[-1]["kind"] == BREAK:
            raise _bad_slots(weekday, _("a break is always between two lessons."))
        if any(a["kind"] == BREAK and b["kind"] == BREAK for a, b in pairwise(day)):
            raise _bad_slots(weekday, _("a break is always between two lessons."))
        numbers = [slot["index"] for slot in day if slot["kind"] == LESSON]
        if numbers != list(range(1, len(numbers) + 1)):
            raise _bad_slots(weekday, _("lessons are numbered 1, 2, 3… in order."))
        if len(numbers) > MAX_LESSONS_PER_DAY:
            raise _bad_slots(weekday, _("at most 12 lessons a day."))


def grids() -> list[TimeGrid]:
    """Grilles de l'école avec leurs cases, le nombre d'heures de cours par semaine et le nombre
    de classes de l'année en cours qui les suivent : trois requêtes, quel que soit leur nombre."""
    year = organisation.current_year()
    return list(
        TimeGrid.objects.annotate(
            lesson_count=Count("slots", filter=Q(slots__kind=LESSON), distinct=True),
            class_count=Count(
                "class_groups", filter=Q(class_groups__academic_year=year), distinct=True
            ),
        )
        .prefetch_related(Prefetch("slots", queryset=TimeSlot.objects.order_by("weekday", "start")))
        .order_by("-is_default", "name")
    )


def _journal_row(grid: TimeGrid, slots: list[dict]) -> dict:
    """Ce que le journal garde d'une grille : réglages, et pour chaque jour (`day1` = lundi) son
    début, sa fin, ses heures et ses récréations ; un changement ne montre que les jours
    touchés."""
    days: dict[int, list[dict]] = defaultdict(list)
    for slot in slots:
        days[slot["weekday"]].append(slot)
    week = {}
    for weekday, day in sorted(days.items()):
        day.sort(key=lambda slot: slot["start"])
        lessons = sum(1 for slot in day if slot["kind"] == LESSON)
        pauses = ", ".join(
            f"{slot['start']:%H:%M}-{slot['end']:%H:%M}" for slot in day if slot["kind"] == BREAK
        )
        week[f"day{weekday}"] = (
            f"{day[0]['start']:%H:%M}-{day[-1]['end']:%H:%M} ({lessons}) {pauses}".strip()
        )
    return {
        "name": grid.name,
        "lesson_minutes": grid.lesson_minutes,
        "start_time": f"{grid.start_time:%H:%M}",
        "is_default": grid.is_default,
        **week,
    }


def _slot_rows(grid: TimeGrid) -> list[dict]:
    return list(grid.slots.values("weekday", "index", "kind", "start", "end"))


def _check_name_free(name: str, *, exclude: TimeGrid | None = None) -> None:
    taken = TimeGrid.objects.filter(name__iexact=name)
    if exclude is not None:
        taken = taken.exclude(pk=exclude.pk)
    if taken.exists():
        raise BusinessError(GRID_EXISTS)


def create_grid(
    *,
    name: str,
    lesson_minutes: int,
    start_time: time,
    is_default: bool = False,
    slots: list[dict] | None = None,
    actor,
) -> TimeGrid:
    """Nouvelle grille ; sans `slots`, la semaine proposée calculée avec cette durée et ce début.
    La première grille de l'école est la grille par défaut."""
    if slots is None:
        slots = week_shape(lesson_minutes, start_time)
    check_slots(slots)
    try:
        with transaction.atomic():
            _check_name_free(name)
            is_default = is_default or not TimeGrid.objects.exists()
            if is_default:
                TimeGrid.objects.filter(is_default=True).update(is_default=False)
            grid = TimeGrid.objects.create(
                name=name,
                lesson_minutes=lesson_minutes,
                start_time=start_time,
                is_default=is_default,
                created_by=actor,
            )
            TimeSlot.objects.bulk_create(
                [TimeSlot(grid=grid, created_by=actor, **slot) for slot in slots]
            )
            audit.record(
                Action.TIME_GRID_CHANGED, grid, actor=actor, after=_journal_row(grid, slots)
            )
    except IntegrityError as exc:
        # Deux enregistrements en même temps : même nom ou deux grilles par défaut.
        raise BusinessError(GRID_EXISTS) from exc
    return grid


def update_grid(
    grid: TimeGrid,
    *,
    name: str,
    lesson_minutes: int,
    start_time: time,
    is_default: bool,
    slots: list[dict],
    actor,
) -> TimeGrid:
    """Réglages et semaine d'une grille, d'un bloc. Une heure (jour, numéro) qui existait garde
    son identifiant, ses horaires changent ; les récréations sont réécrites."""
    check_slots(slots)
    try:
        with transaction.atomic():
            grid = TimeGrid.objects.select_for_update().get(pk=grid.pk)
            _check_name_free(name, exclude=grid)
            if grid.is_default and not is_default:
                raise BusinessError(DEFAULT_GRID_KEPT)
            before = _journal_row(grid, _slot_rows(grid))
            if is_default and not grid.is_default:
                TimeGrid.objects.filter(is_default=True).update(is_default=False)
            grid.name, grid.lesson_minutes = name, lesson_minutes
            grid.start_time, grid.is_default = start_time, is_default
            grid.save()
            _write_slots(grid, slots, actor=actor)
            old, new = audit.changes(before, _journal_row(grid, slots))
            if new:
                audit.record(Action.TIME_GRID_CHANGED, grid, actor=actor, before=old, after=new)
    except IntegrityError as exc:
        raise BusinessError(GRID_EXISTS) from exc
    return grid


def _write_slots(grid: TimeGrid, slots: list[dict], *, actor) -> None:
    existing = {(slot.weekday, slot.index): slot for slot in grid.slots.filter(kind=LESSON)}
    wanted = {(slot["weekday"], slot["index"]): slot for slot in slots if slot["kind"] == LESSON}
    grid.slots.filter(kind=BREAK).delete()
    gone = [slot.pk for key, slot in existing.items() if key not in wanted]
    if gone:
        TimeSlot.objects.filter(pk__in=gone).delete()
    kept = []
    for key, slot in existing.items():
        if key in wanted:
            slot.start, slot.end = wanted[key]["start"], wanted[key]["end"]
            kept.append(slot)
    TimeSlot.objects.bulk_update(kept, ["start", "end"])
    TimeSlot.objects.bulk_create(
        [
            TimeSlot(grid=grid, created_by=actor, **slot)
            for slot in slots
            if slot["kind"] == BREAK or (slot["weekday"], slot["index"]) not in existing
        ]
    )


def delete_grid(grid: TimeGrid, *, actor) -> None:
    """Supprime une grille qui n'est pas celle par défaut ; ses classes reviennent à la grille par
    défaut."""
    if grid.is_default:
        raise BusinessError(DEFAULT_GRID_KEPT)
    with transaction.atomic():
        row = _journal_row(grid, _slot_rows(grid))
        audit.record(Action.TIME_GRID_DELETED, grid, actor=actor, before=row)
        grid.delete()


# --------------------------------------------------------------------------- classes


def class_rows(year: AcademicYear | None) -> list[dict]:
    """Classes de l'année avec leur grille, leur salle, leurs heures de cours (cours enseignés,
    heures saisies), le nombre de cours sans heures, et les places de leur grille. Deux
    requêtes."""
    if year is None:
        return []
    groups = (
        ClassGroup.objects.filter(academic_year=year)
        .select_related("level", "track")
        .order_by("level__order", "track__name", "section")
        .annotate(
            course_hours=Coalesce(
                Sum("courses__weekly_hours", filter=Q(courses__is_taught=True)), 0
            ),
            missing_hours=Count(
                "courses", filter=Q(courses__is_taught=True, courses__weekly_hours__isnull=True)
            ),
        )
    )
    places: dict = {}
    default = None
    for grid in TimeGrid.objects.annotate(
        lessons=Count("slots", filter=Q(slots__kind=LESSON))
    ).values("pk", "lessons", "is_default"):
        places[grid["pk"]] = grid["lessons"]
        if grid["is_default"]:
            default = grid["pk"]
    return [
        {
            "id": group.pk,
            "name": group.name,
            "time_grid": group.time_grid_id,
            "home_room": group.home_room_id,
            "course_hours": group.course_hours,
            "missing_hours": group.missing_hours,
            "capacity": places.get(group.time_grid_id or default),
        }
        for group in groups
    ]


def set_class(group: ClassGroup, *, actor, **fields) -> ClassGroup:
    """Grille (`time_grid`) et salle habituelle (`home_room`) d'une classe ; `None` les retire.
    Seulement une grille ou une salle de l'école, et une salle encore utilisée."""
    changes = {}
    if "time_grid" in fields:
        grid_id = fields["time_grid"]
        if grid_id is not None and not TimeGrid.objects.filter(pk=grid_id).exists():
            raise BusinessError(UNKNOWN_GRID)
        changes["time_grid_id"] = grid_id
    if "home_room" in fields:
        room_id = fields["home_room"]
        if room_id is not None and room_id != group.home_room_id:
            room = Room.objects.filter(pk=room_id).first()
            if room is None:
                raise BusinessError(UNKNOWN_ROOM)
            if not room.is_active:
                raise BusinessError(ROOM_RETIRED)
        changes["home_room_id"] = room_id
    before = {key: str(getattr(group, key) or "") for key in changes}
    after = {key: str(value or "") for key, value in changes.items()}
    old, new = audit.changes(before, after)
    if not new:
        return group
    with transaction.atomic():
        for key, value in changes.items():
            setattr(group, key, value)
        group.save(update_fields=[*changes, "updated_at"])
        audit.record(Action.CLASS_TIMETABLE_CHANGED, group, actor=actor, before=old, after=new)
    return group


# --------------------------------------------------------------------------- salles


def _with_classes(queryset):
    """Avec les classes de l'année en cours qui y ont leur salle habituelle (une requête)."""
    year = organisation.current_year()
    return queryset.prefetch_related(
        Prefetch(
            "class_groups",
            queryset=ClassGroup.objects.filter(academic_year=year).select_related("level", "track"),
            to_attr="current_classes",
        )
    )


KIND_ORDER = {kind: position for position, kind in enumerate(Room.Kind.values)}


def _natural(room: Room) -> tuple:
    """Salles de classe d'abord, puis ateliers… ; « Salle 2 » avant « Salle 10 »."""
    parts = re.split(r"(\d+)", room.name.casefold())
    return (KIND_ORDER[room.kind], [int(p) if p.isdigit() else p for p in parts])


def rooms() -> list[Room]:
    """Salles de l'école, retirées comprises, avec leurs classes : deux requêtes."""
    return sorted(_with_classes(Room.objects.all()), key=_natural)


def _room_row(room: Room) -> dict:
    return {
        "name": room.name,
        "kind": room.kind,
        "capacity": room.capacity,
        "is_active": room.is_active,
    }


def _check_room_name_free(name: str, *, exclude: Room | None = None) -> None:
    taken = Room.objects.filter(name__iexact=name)
    if exclude is not None:
        taken = taken.exclude(pk=exclude.pk)
    if taken.exists():
        raise BusinessError(ROOM_EXISTS)


def create_room(*, name: str, kind: str, capacity: int | None, actor) -> Room:
    try:
        with transaction.atomic():
            _check_room_name_free(name)
            if Room.objects.count() >= ROOMS_LIMIT:
                raise BusinessError(TOO_MANY_ROOMS)
            room = Room.objects.create(name=name, kind=kind, capacity=capacity, created_by=actor)
            audit.record(Action.ROOM_CHANGED, room, actor=actor, after=_room_row(room))
    except IntegrityError as exc:
        raise BusinessError(ROOM_EXISTS) from exc
    room.current_classes = []
    return room


def update_room(room: Room, *, actor, **fields) -> Room:
    """Nom, type, places, ou retrait (`is_active=False`) / remise d'une salle."""
    if "name" in fields:
        _check_room_name_free(fields["name"], exclude=room)
    before = _room_row(room)
    for key, value in fields.items():
        setattr(room, key, value)
    old, new = audit.changes(before, _room_row(room))
    if new:
        try:
            with transaction.atomic():
                room.save()
                audit.record(Action.ROOM_CHANGED, room, actor=actor, before=old, after=new)
        except IntegrityError as exc:
            raise BusinessError(ROOM_EXISTS) from exc
    return _with_classes(Room.objects.filter(pk=room.pk)).get()


# --------------------------------------------------------------------------- règles générales


def rules_of(school: School) -> dict:
    stored = school.settings.get("timetable") or {}
    return {key: stored.get(key, value) for key, value in DEFAULT_RULES.items()}


def set_rules(changed: dict, *, actor) -> dict:
    """Change une partie des règles générales de l'école courante ; les autres restent."""
    with transaction.atomic():
        school = School.objects.select_for_update().get(pk=require_current_school().pk)
        before = rules_of(school)
        after = {**before, **changed}
        school.settings = {**school.settings, "timetable": after}
        school.save(update_fields=["settings"])
        old, new = audit.changes(before, after)
        if new:
            audit.record(Action.TIMETABLE_RULES_CHANGED, school, actor=actor, before=old, after=new)
    return after


# --------------------------------------------------------------------------- enseignants


def teacher_profiles() -> list[TeacherTimetableProfile]:
    """Disponibilités réglées des enseignants de l'école (au plus son personnel : pas de
    pagination)."""
    return list(TeacherTimetableProfile.objects.order_by("created_at"))


def _profile_row(profile: TeacherTimetableProfile | None) -> dict:
    if profile is None:
        return {"max_week_hours": None, "max_day_hours": None, "unavailable": []}
    return {
        "max_week_hours": profile.max_week_hours,
        "max_day_hours": profile.max_day_hours,
        "unavailable": profile.unavailable,
    }


def normalize_unavailable(items: list[dict]) -> list[dict]:
    """Une journée entière couvre ses plages ; doublons retirés ; rangé par jour et heure."""
    whole = {item["weekday"] for item in items if "start" not in item}
    rows = {(item["weekday"], "", "") for item in items if item["weekday"] in whole}
    rows |= {
        (item["weekday"], item["start"], item["end"])
        for item in items
        if item["weekday"] not in whole
    }
    return [
        {"weekday": day} if not start else {"weekday": day, "start": start, "end": end}
        for day, start, end in sorted(rows)
    ]


def set_teacher_profile(
    teacher_id, *, actor, max_week_hours, max_day_hours, unavailable
) -> TeacherTimetableProfile:
    """Règle la disponibilité d'un membre du personnel actif de l'école (jamais celui d'une
    autre : 404) ; chaque changement va dans le journal."""
    teacher = active_staff().filter(pk=teacher_id).first()
    if teacher is None:
        raise BusinessError(UNKNOWN_TEACHER)
    with transaction.atomic():
        profile = (
            TeacherTimetableProfile.objects.select_for_update().filter(teacher=teacher).first()
        )
        before = _profile_row(profile)
        if profile is None:
            profile = TeacherTimetableProfile(teacher=teacher, created_by=actor)
        profile.max_week_hours = max_week_hours
        profile.max_day_hours = max_day_hours
        profile.unavailable = normalize_unavailable(unavailable)
        old, new = audit.changes(before, _profile_row(profile))
        if new:
            profile.save()
            audit.record(
                Action.TEACHER_TIMETABLE_CHANGED,
                profile,
                actor=actor,
                before={"teacher": str(teacher), **old},
                after={"teacher": str(teacher), **new},
            )
    return profile

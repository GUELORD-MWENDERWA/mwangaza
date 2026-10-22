"""Brouillons de l'horaire (EDT.2a, spec §§ 8 et 10) : créer (vide avec les verrous des règles,
ou copie d'un brouillon), placer, déplacer, échanger, verrouiller, changer la salle, retirer,
annuler. Un geste = une écriture : le brouillon est verrouillé (`select_for_update`) le temps du
geste et l'état d'avant des séances touchées part dans `Timetable.history` (50 derniers gestes).

Un brouillon peut avoir des conflits (`checks.draft` les montre) ; seul ce qui ne peut pas exister
est refusé : séance hors de la grille de la classe ou sur une récréation que le cours ne passe pas,
séance que le cours n'a plus à placer, séance verrouillée qu'on bouge.
Publier : `versions` (EDT.4a)."""

from collections import Counter
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Course
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools.models import AcademicYear
from apps.timetable import checks
from apps.timetable import placement as placing
from apps.timetable.models import HISTORY_LIMIT, Room, Timetable, TimetableEntry
from apps.timetable.services import ROOM_RETIRED, UNKNOWN_ROOM, grids, rules_of

DRAFT = Timetable.Status.DRAFT

NO_YEAR = ApiError("no_year", _("The school has no current school year."), 409)
NOT_A_DRAFT = ApiError("not_a_draft", _("Only a draft timetable can be changed."), 409)
ENTRY_LOCKED = ApiError("entry_locked", _("This lesson is locked: unlock it first."), 409)
NOTHING_TO_UNDO = ApiError("nothing_to_undo", _("There is nothing to undo."), 409)
UNKNOWN_COURSE = ApiError("unknown_course", _("This course is not taught this school year."), 400)
NOT_DUE = ApiError("not_due", _("This course has no lesson of this length left to place."), 400)
SAME_ENTRY = ApiError("same_entry", _("Choose two different lessons."), 400)
MISFIT = {
    "outside_grid": ApiError(
        "outside_grid", _("These hours are not in the time grid of the class."), 400
    ),
    "crosses_break": ApiError("crosses_break", _("This course does not run across a break."), 400),
}


def drafts(year: AcademicYear | None) -> QuerySet[Timetable]:
    """Brouillons de l'année, le plus récent d'abord, avec leurs heures placées."""
    return Timetable.objects.filter(academic_year=year, status=DRAFT).annotate(
        hours=Coalesce(Sum("entries__length"), 0)
    )


def state(timetable: Timetable) -> dict:
    """Ce que montre l'éditeur après chaque geste : séances, conflits, reste à placer, heures ;
    pour une version publiée ou archivée (EDT.4a), sa date d'effet et qui l'a publiée."""
    return {
        "id": timetable.pk,
        "name": timetable.name,
        "status": timetable.status,
        "based_on": timetable.based_on_id,
        "can_undo": bool(timetable.history),
        "valid_from": timetable.valid_from,
        "published_at": timetable.published_at,
        "published_by": str(timetable.published_by) if timetable.published_by_id else None,
        **checks.draft(timetable),
    }


def _snapshot(entry: TimetableEntry) -> dict:
    return {
        "id": str(entry.pk),
        "course": str(entry.course_id),
        "weekday": entry.weekday,
        "first": entry.first,
        "length": entry.length,
        "room": str(entry.room_id) if entry.room_id else None,
        "locked": entry.locked,
    }


def _absent(entry: TimetableEntry) -> dict:
    """Séance créée par le geste : l'annuler la retire."""
    return {"id": str(entry.pk), "absent": True}


def _open(timetable: Timetable) -> Timetable:
    """Le brouillon, verrouillé jusqu'à la fin du geste."""
    draft = Timetable.objects.select_for_update().get(pk=timetable.pk)
    if draft.status != DRAFT:
        raise BusinessError(NOT_A_DRAFT)
    return draft


def _remember(draft: Timetable, items: list[dict]) -> None:
    draft.history = [*draft.history, items][-HISTORY_LIMIT:]
    draft.save(update_fields=["history", "updated_at"])


def _label(course: Course) -> str:
    return f"{course.name} · {course.class_group.name}"


def _fit(course: Course, weekday: int, first: int, length: int) -> None:
    """La séance tient-elle dans la grille de la classe (sans passer une récréation interdite) ?"""
    found = grids()
    grid = next((g for g in found if g.pk == course.class_group.time_grid_id), None) or next(
        (g for g in found if g.is_default), None
    )
    last = first + length - 1
    run = (
        checks.Week(grid).span(weekday, first, last, placing.spans_break(course))
        if grid
        else "outside_grid"
    )
    if isinstance(run, str):
        raise BusinessError(MISFIT[run])


def _movable(entry: TimetableEntry) -> TimetableEntry:
    """La séance relue sous le verrou du brouillon ; refusée si elle est verrouillée."""
    entry = TimetableEntry.objects.select_related("course__class_group").get(pk=entry.pk)
    if entry.locked:
        raise BusinessError(ENTRY_LOCKED)
    return entry


def _audit_lock(entry: TimetableEntry, before: bool, *, actor) -> None:
    audit.record(
        Action.TIMETABLE_LOCK_CHANGED,
        entry,
        actor=actor,
        before={"locked": before},
        after={"locked": entry.locked},
        label=_label(entry.course),
    )


def create_draft(
    *, year: AcademicYear | None, name: str, based_on: Timetable | None = None, actor
) -> Timetable:
    """Nouveau brouillon : copie d'un brouillon, ou vide avec les heures verrouillées des règles
    `fixed_lesson` qui tiennent dans la grille (celles qui ne tiennent pas restent signalées par
    les contrôles)."""
    if year is None:
        raise BusinessError(NO_YEAR)
    with transaction.atomic():
        draft = Timetable.objects.create(
            academic_year=year, name=name, based_on=based_on, created_by=actor
        )
        if based_on is not None:
            rows = [
                TimetableEntry(
                    timetable=draft,
                    course=entry.course,
                    weekday=entry.weekday,
                    first=entry.first,
                    length=entry.length,
                    room=entry.room,
                    locked=entry.locked,
                    created_by=actor,
                )
                for entry in based_on.entries.select_related("course", "room")
            ]
        else:
            locks, rooms = checks.fixed_locks(year)
            rows = [
                TimetableEntry(
                    timetable=draft,
                    course=lock.course,
                    weekday=lock.weekday,
                    first=lock.first,
                    length=lock.last - lock.first + 1,
                    room=rooms.get(lock.room),
                    locked=True,
                    created_by=actor,
                )
                for lock in locks
            ]
        TimetableEntry.objects.bulk_create(rows)
        audit.record(
            Action.TIMETABLE_DRAFT_CREATED,
            draft,
            actor=actor,
            after={
                "name": name,
                "based_on": based_on.name if based_on else None,
                "lessons": len(rows),
            },
            label=name,
        )
    return draft


def delete_draft(timetable: Timetable, *, actor) -> None:
    with transaction.atomic():
        draft = _open(timetable)
        lessons = draft.entries.count()
        audit.record(
            Action.TIMETABLE_DRAFT_DELETED,
            draft,
            actor=actor,
            before={"name": draft.name, "lessons": lessons},
            label=draft.name,
        )
        draft.delete()


def place(
    timetable: Timetable, *, course: UUID, weekday: int, first: int, length: int, actor
) -> Timetable:
    """Placer une séance restant à placer ; salle : celle du cours, sinon celle de la classe (un
    type de salle exigé sans salle choisie reste « à choisir »)."""
    with transaction.atomic():
        draft = _open(timetable)
        found = (
            Course.objects.filter(
                pk=course, class_group__academic_year=draft.academic_year, is_taught=True
            )
            .select_related("class_group__home_room", "room")
            .first()
        )
        if found is None:
            raise BusinessError(UNKNOWN_COURSE)
        _fit(found, weekday, first, length)
        placed = Counter(
            TimetableEntry.objects.filter(timetable=draft, course=found).values_list(
                "length", flat=True
            )
        )
        if (Counter(placing.sessions(found)) - placed)[length] < 1:
            raise BusinessError(NOT_DUE)
        room = found.room or (None if found.room_kind else found.class_group.home_room)
        entry = TimetableEntry.objects.create(
            timetable=draft,
            course=found,
            weekday=weekday,
            first=first,
            length=length,
            room=room,
            created_by=actor,
        )
        _remember(draft, [_absent(entry)])
    return draft


def move(timetable: Timetable, entry: TimetableEntry, *, weekday: int, first: int) -> Timetable:
    with transaction.atomic():
        draft = _open(timetable)
        entry = _movable(entry)
        if (entry.weekday, entry.first) != (weekday, first):
            _fit(entry.course, weekday, first, entry.length)
            before = _snapshot(entry)
            entry.weekday, entry.first = weekday, first
            entry.save(update_fields=["weekday", "first", "updated_at"])
            _remember(draft, [before])
    return draft


def swap(timetable: Timetable, entry: TimetableEntry, other: TimetableEntry) -> Timetable:
    """Échanger les places de deux séances (chacune doit tenir à la place de l'autre)."""
    if entry.pk == other.pk:
        raise BusinessError(SAME_ENTRY)
    with transaction.atomic():
        draft = _open(timetable)
        entry, other = _movable(entry), _movable(other)
        _fit(entry.course, other.weekday, other.first, entry.length)
        _fit(other.course, entry.weekday, entry.first, other.length)
        before = [_snapshot(entry), _snapshot(other)]
        (entry.weekday, entry.first), (other.weekday, other.first) = (
            (other.weekday, other.first),
            (entry.weekday, entry.first),
        )
        for item in (entry, other):
            item.save(update_fields=["weekday", "first", "updated_at"])
        _remember(draft, before)
    return draft


def set_room(timetable: Timetable, entry: TimetableEntry, *, room: UUID | None) -> Timetable:
    with transaction.atomic():
        draft = _open(timetable)
        entry = _movable(entry)
        chosen = None
        if room is not None:
            chosen = Room.objects.filter(pk=room).first()
            if chosen is None:
                raise BusinessError(UNKNOWN_ROOM)
            if not chosen.is_active:
                raise BusinessError(ROOM_RETIRED)
        if entry.room_id != room:
            before = _snapshot(entry)
            entry.room = chosen
            entry.save(update_fields=["room", "updated_at"])
            _remember(draft, [before])
    return draft


def set_locked(timetable: Timetable, entry: TimetableEntry, *, locked: bool, actor) -> Timetable:
    with transaction.atomic():
        draft = _open(timetable)
        entry = TimetableEntry.objects.select_related("course__class_group").get(pk=entry.pk)
        if entry.locked != locked:
            before = _snapshot(entry)
            entry.locked = locked
            entry.save(update_fields=["locked", "updated_at"])
            _remember(draft, [before])
            _audit_lock(entry, not locked, actor=actor)
    return draft


def remove(timetable: Timetable, entry: TimetableEntry) -> Timetable:
    """Retirer une séance du brouillon : elle revient dans « À placer »."""
    with transaction.atomic():
        draft = _open(timetable)
        entry = _movable(entry)
        before = _snapshot(entry)
        entry.delete()
        _remember(draft, [before])
    return draft


def undo(timetable: Timetable, *, actor) -> Timetable:
    """Remettre les séances du dernier geste dans leur état d'avant. Une séance dont le cours a
    disparu entre-temps ne revient pas."""
    with transaction.atomic():
        draft = _open(timetable)
        if not draft.history:
            raise BusinessError(NOTHING_TO_UNDO)
        items = draft.history[-1]
        current = {
            str(entry.pk): entry
            for entry in TimetableEntry.objects.filter(
                timetable=draft, pk__in=[item["id"] for item in items]
            ).select_related("course__class_group")
        }
        kept = [item for item in items if not item.get("absent")]
        courses = Course.objects.select_related("class_group").in_bulk(
            [item["course"] for item in kept]
        )
        rooms = Room.objects.in_bulk([item["room"] for item in kept if item["room"]])
        for item in items:
            entry = current.get(item["id"])
            if item.get("absent"):
                if entry is not None:
                    entry.delete()
                continue
            course = courses.get(UUID(item["course"]))
            if course is None:
                continue
            was_locked = entry.locked if entry is not None else item["locked"]
            if entry is None:
                entry = TimetableEntry(id=UUID(item["id"]), timetable=draft, created_by=actor)
            entry.course = course
            entry.weekday, entry.first, entry.length = (
                item["weekday"],
                item["first"],
                item["length"],
            )
            entry.room = rooms.get(UUID(item["room"])) if item["room"] else None
            entry.locked = item["locked"]
            entry.save()
            if was_locked != entry.locked:
                _audit_lock(entry, was_locked, actor=actor)
        draft.history = draft.history[:-1]
        draft.save(update_fields=["history", "updated_at"])
    return draft


def year_courses(year: AcademicYear | None) -> list[dict]:
    """Cours enseignés de l'année, avec ce que l'éditeur affiche et vérifie : séances, salle ou
    type exigé, récréation traversable, au plus par jour. Une requête."""
    if year is None:
        return []
    school_max = rules_of(require_current_school())["max_same_course_per_day"]
    courses = (
        Course.objects.filter(class_group__academic_year=year, is_taught=True)
        .select_related("teacher", "class_group")
        .order_by("class_group__level__order", "class_group__section", "order")
    )
    return [
        {
            "id": course.pk,
            "name": course.name,
            "category": course.category,
            "class_group": course.class_group_id,
            "teacher": course.teacher_id,
            "teacher_name": str(course.teacher) if course.teacher_id else "",
            "sessions": placing.sessions(course),
            "room": course.room_id,
            "room_kind": course.room_kind,
            "spans_break": placing.spans_break(course),
            "max_per_day": placing.max_per_day(course, school_max),
        }
        for course in courses
    ]

"""Horaire des interrogations et des examens (EDT.5, spec § 11.6) : le directeur des études fixe,
pour une période ou des examens, les épreuves de chaque classe, voit les conflits, puis publie.
Brouillon tant qu'il se règle ; publié, il ne se modifie plus (le rouvrir est écrit au journal).

Les contrôles lisent tout l'horaire en quatre requêtes, quelle que soit sa taille. Rouge (bloque la
publication) : une classe, un surveillant ou une salle à deux épreuves en même temps, une date hors
de la période. Orange : surveillant absent ce jour-là (EDT.1b), jour de congé du calendrier."""

from collections import defaultdict
from itertools import combinations

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.courses import active_staff
from apps.academics.models import Course
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.notifications.models import SchoolEvent
from apps.schools.models import Term
from apps.timetable import checks
from apps.timetable.models import ExamSchedule, ExamSitting, Room, TeacherTimetableProfile

DRAFT = ExamSchedule.Status.DRAFT
PUBLISHED = ExamSchedule.Status.PUBLISHED

NOT_A_PERIOD = ApiError(
    "not_a_period", _("Choose a period or the exams, not a semester or a term."), 400
)
NOT_A_DRAFT = ApiError(
    "exam_timetable_published", _("This timetable is published: reopen it to change it."), 409
)
NOT_PUBLISHED = ApiError("exam_timetable_not_published", _("This timetable is not published."), 409)
UNKNOWN_COURSE = ApiError(
    "unknown_course", _("This course is not taught in the school year of the period."), 400
)
UNKNOWN_ROOM = ApiError("unknown_room", _("This room does not exist."), 400)
UNKNOWN_INVIGILATOR = ApiError("unknown_invigilator", _("This person is not on the staff."), 400)
HAS_CONFLICTS = ApiError(
    "publish_conflicts",
    _("This timetable still has conflicts: correct them before publishing."),
    409,
)
EMPTY = ApiError("exam_timetable_empty", _("Add at least one sitting before publishing."), 409)

FIELDS = ("course", "kind", "date", "start", "end", "room", "invigilator")


def period(term: Term) -> Term:
    """Un semestre ou un trimestre n'a pas d'horaire d'épreuves."""
    if term.kind in Term.GROUPS:
        raise BusinessError(NOT_A_PERIOD)
    return term


def schedule_of(term: Term) -> ExamSchedule | None:
    return ExamSchedule.objects.filter(term=term).select_related("published_by").first()


def _overlap(a: ExamSitting, b: ExamSitting) -> bool:
    return a.date == b.date and a.start < b.end and b.start < a.end


def _issue(level: str, code: str, sittings: list[ExamSitting], **values) -> dict:
    return {
        "level": level,
        "code": code,
        "sittings": [sitting.pk for sitting in sittings],
        "values": values,
    }


def _pairs(sittings: list[ExamSitting], key, code: str, **values) -> list[dict]:
    """Deux épreuves qui se chevauchent pour la même clé (classe, surveillant, salle)."""
    groups = defaultdict(list)
    for sitting in sittings:
        if key(sitting) is not None:
            groups[key(sitting)].append(sitting)
    return [
        _issue("error", code, [first, second], date=first.date.isoformat(), **values)
        for group in groups.values()
        for first, second in combinations(group, 2)
        if _overlap(first, second)
    ]


def report(term: Term, sittings: list[ExamSitting]) -> dict:
    """Les contrôles : rouges d'abord, puis orange."""
    issues = _pairs(sittings, lambda s: s.course.class_group_id, "class_overlap")
    issues += _pairs(sittings, lambda s: s.invigilator_id, "invigilator_overlap")
    issues += _pairs(sittings, lambda s: s.room_id, "room_overlap")
    for sitting in sittings:
        if (term.starts_on and sitting.date < term.starts_on) or (
            term.ends_on and sitting.date > term.ends_on
        ):
            issues.append(_issue("error", "outside_term", [sitting], date=sitting.date.isoformat()))
    if sittings:
        days = {sitting.date for sitting in sittings}
        holidays = SchoolEvent.objects.filter(
            kind=SchoolEvent.Kind.HOLIDAY,
            starts_on__lte=max(days),
            ends_on__gte=min(days),
        ).values_list("starts_on", "ends_on")
        profiles = {
            profile.teacher_id: profile.unavailable
            for profile in TeacherTimetableProfile.objects.filter(
                teacher__in={s.invigilator_id for s in sittings if s.invigilator_id}
            )
        }
        for sitting in sittings:
            if any(start <= sitting.date <= end for start, end in holidays):
                issues.append(
                    _issue("warning", "holiday", [sitting], date=sitting.date.isoformat())
                )
            slot = (sitting.date.isoweekday(), sitting.start, sitting.end)
            if sitting.invigilator_id and checks.is_blocked(
                profiles.get(sitting.invigilator_id, []), slot
            ):
                issues.append(_issue("warning", "invigilator_unavailable", [sitting]))
    issues.sort(key=lambda issue: issue["level"] != "error")
    return {
        "errors": sum(issue["level"] == "error" for issue in issues),
        "warnings": sum(issue["level"] == "warning" for issue in issues),
        "issues": issues,
    }


def sittings_of(schedule: ExamSchedule | None) -> list[ExamSitting]:
    if schedule is None:
        return []
    return list(
        schedule.sittings.select_related("course__class_group", "course__teacher", "room").order_by(
            "date", "start", "course__class_group__level__order", "course__class_group__section"
        )
    )


def state(term: Term) -> dict:
    """Horaire d'une période : état, épreuves et contrôles (sans créer de ligne en lecture)."""
    schedule = schedule_of(term)
    sittings = sittings_of(schedule)
    return {"term": term, "schedule": schedule, "sittings": sittings, **report(term, sittings)}


def _open(term: Term) -> ExamSchedule:
    """L'horaire en brouillon de la période (créé au premier geste) ; refusé s'il est publié."""
    schedule, _created = ExamSchedule.objects.select_for_update().get_or_create(term=term)
    if schedule.status != DRAFT:
        raise BusinessError(NOT_A_DRAFT)
    return schedule


def _checked(term: Term, values: dict, sitting: ExamSitting | None) -> dict:
    """Le cours est enseigné dans l'année de la période, la salle et le surveillant existent
    (l'isolation vient du gestionnaire de l'école)."""
    course = values.get("course") or sitting.course
    if not Course.objects.filter(
        pk=course.pk, class_group__academic_year=term.academic_year_id, is_taught=True
    ).exists():
        raise BusinessError(UNKNOWN_COURSE)
    if (
        values.get("room")
        and not Room.objects.filter(pk=values["room"].pk, is_active=True).exists()
    ):
        raise BusinessError(UNKNOWN_ROOM)
    invigilator = values.get("invigilator")
    if invigilator and invigilator.pk not in set(active_staff().values_list("pk", flat=True)):
        raise BusinessError(UNKNOWN_INVIGILATOR)
    return values


def _snapshot(sitting: ExamSitting) -> dict:
    return {
        "course": sitting.course.name,
        "class": str(sitting.course.class_group),
        "kind": sitting.kind,
        "date": sitting.date.isoformat(),
        "start": sitting.start.isoformat(timespec="minutes"),
        "end": sitting.end.isoformat(timespec="minutes"),
        "room": sitting.room.name if sitting.room else None,
        "invigilator": str(sitting.invigilator) if sitting.invigilator else None,
    }


@transaction.atomic
def save_sitting(term: Term, *, sitting: ExamSitting | None, values: dict, actor) -> ExamSitting:
    """Ajoute une épreuve, ou change celle qui est donnée (jamais celle d'une autre période)."""
    schedule = _open(term)
    values = _checked(term, values, sitting)
    before = None
    if sitting is None:
        sitting = ExamSitting(schedule=schedule)
    else:
        before = _snapshot(sitting)
    for name, value in values.items():
        setattr(sitting, name, value)
    sitting.save()
    sitting = ExamSitting.objects.select_related("course__class_group", "room").get(pk=sitting.pk)
    audit.record(
        Action.EXAM_SITTING_CHANGED,
        sitting,
        actor=actor,
        before=before,
        after=_snapshot(sitting),
        label=f"{term} · {sitting.course.name}",
    )
    return sitting


@transaction.atomic
def delete_sitting(sitting: ExamSitting, *, actor) -> None:
    term = sitting.schedule.term
    _open(term)
    audit.record(
        Action.EXAM_SITTING_DELETED,
        sitting,
        actor=actor,
        before=_snapshot(sitting),
        label=f"{term} · {sitting.course.name}",
    )
    sitting.delete()


@transaction.atomic
def publish(term: Term, *, actor) -> ExamSchedule:
    """Publie l'horaire de la période : refusé vide ou avec du rouge (l'orange ne bloque pas)."""
    schedule = _open(term)
    sittings = sittings_of(schedule)
    if not sittings:
        raise BusinessError(EMPTY)
    result = report(term, sittings)
    if result["errors"]:
        raise BusinessError(HAS_CONFLICTS)
    schedule.status = PUBLISHED
    schedule.published_at = timezone.now()
    schedule.published_by = actor
    schedule.save(update_fields=["status", "published_at", "published_by", "updated_at"])
    audit.record(
        Action.EXAM_TIMETABLE_PUBLISHED,
        schedule,
        actor=actor,
        after={"term": str(term), "sittings": len(sittings), "warnings": result["warnings"]},
        label=str(term),
    )
    return schedule


@transaction.atomic
def reopen(term: Term, *, actor) -> ExamSchedule:
    """Un horaire publié redevient un brouillon (un changement de dernière minute) ; écrit au
    journal."""
    schedule = ExamSchedule.objects.select_for_update().filter(term=term).first()
    if schedule is None or schedule.status != PUBLISHED:
        raise BusinessError(NOT_PUBLISHED)
    schedule.status = DRAFT
    schedule.save(update_fields=["status", "updated_at"])
    audit.record(
        Action.EXAM_TIMETABLE_REOPENED,
        schedule,
        actor=actor,
        before={
            "published_at": schedule.published_at.isoformat() if schedule.published_at else None
        },
        label=str(term),
    )
    return schedule

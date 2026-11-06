"""Heures prestées (EDT.6, spec § 12) : on part de l'horaire publié et on ne note que les
exceptions (`LessonException`), jamais chaque heure. Prestées = prévues - absent - annulées +
remplacements faits + heures en plus ; calculées à la demande, jamais stockées.

Prévues : chaque jour de cours du mois (jusqu'à aujourd'hui), les séances de la version de
l'horaire en vigueur ce jour-là (une nouvelle version en cours de mois compte à partir de sa date),
congés du calendrier retirés (`SchoolEvent` « congé »), et, si l'école a daté ses périodes, les
jours hors période (vacances). Une heure = une case de la grille ; un cours commun à plusieurs
classes compte une fois. Deux requêtes pour les séances et une pour les exceptions, quelle que soit
la taille de l'école ; le reste se compte en mémoire (un mois de séances).

L'enseignant d'une séance est celui du cours aujourd'hui : un cours réattribué en cours de mois se
note par des remplacements."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.courses import active_staff
from apps.academics.models import Course
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.notifications.models import SchoolEvent
from apps.schools import organisation
from apps.schools.models import AcademicYear, ClassGroup, Term
from apps.timetable import schedule
from apps.timetable.models import LessonException, Timetable, TimetableEntry

Kind = LessonException.Kind
FROM_TIMETABLE = (Kind.TEACHER_ABSENT, Kind.REPLACED, Kind.CANCELLED)
MISSED = (Kind.TEACHER_ABSENT, Kind.REPLACED)  # l'enseignant prévu ne l'a pas donnée
EXTRA_MAX = 8

NO_YEAR = ApiError("no_current_year", _("The school has no current school year."), 409)
FUTURE = ApiError("future_date", _("Only record what has already happened."), 400)
NOT_A_SCHOOL_DAY = ApiError(
    "not_a_school_day", _("This day is not a school day (holiday or outside the year)."), 400
)
NOT_IN_TIMETABLE = ApiError(
    "not_in_timetable",
    _("These lessons are not in this teacher's published timetable for that day."),
    400,
)
REPLACEMENT_REQUIRED = ApiError(
    "replacement_required", _("Choose the person who replaced the teacher."), 400
)
UNKNOWN_PERSON = ApiError("unknown_person", _("This person is not on the staff."), 400)
UNKNOWN_COURSE = ApiError("unknown_course", _("This course is not taught this year."), 400)
ALREADY = ApiError(
    "already_recorded", _("One of these lessons is already recorded for that day."), 409
)
ALREADY_CANCELLED = ApiError("exception_cancelled", _("This exception is already cancelled."), 409)


def _year() -> AcademicYear:
    year = organisation.current_year()
    if year is None:
        raise BusinessError(NO_YEAR)
    return year


def month_range(month: date) -> tuple[date, date]:
    first = month.replace(day=1)
    return first, (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def school_days(start: date, end: date, year: AcademicYear) -> tuple[list[date], list[date]]:
    """(jours de classe possibles, congés) entre `start` et `end`, dans l'année et ses périodes
    datées. Deux requêtes."""
    start, end = max(start, year.starts_on), min(end, year.ends_on)
    if start > end:
        return [], []
    off = set()
    for event in SchoolEvent.objects.filter(
        kind=SchoolEvent.Kind.HOLIDAY, starts_on__lte=end, ends_on__gte=start
    ):
        day = max(event.starts_on, start)
        while day <= min(event.ends_on, end):
            off.add(day)
            day += timedelta(days=1)
    ranges = list(
        Term.objects.filter(
            academic_year=year, starts_on__isnull=False, ends_on__isnull=False
        ).values_list("starts_on", "ends_on")
    )
    days, holidays = [], []
    day = start
    while day <= end:
        if day in off:
            holidays.append(day)
        elif not ranges or any(first <= day <= last for first, last in ranges):
            days.append(day)
        day += timedelta(days=1)
    return days, holidays


def _versions(year: AcademicYear) -> list[Timetable]:
    """Versions publiées et archivées de l'année, de la plus ancienne à la plus récente."""
    return list(
        Timetable.objects.filter(
            academic_year=year,
            status__in=[Timetable.Status.PUBLISHED, Timetable.Status.ARCHIVED],
            valid_from__isnull=False,
        ).order_by("valid_from", "published_at")
    )


def in_effect(versions: list[Timetable], day: date) -> Timetable | None:
    found = None
    for version in versions:
        if version.valid_from <= day:
            found = version
    return found


@dataclass
class Slot:
    teacher_id: object
    first: int
    length: int
    label: str


def _slots(version_ids) -> dict[tuple, list[Slot]]:
    """(version, jour de la semaine) → heures de chaque enseignant ; un cours commun (même
    enseignant, même heure, plusieurs classes) ne compte qu'une fois. Deux requêtes."""
    rows = list(
        TimetableEntry.objects.filter(
            timetable_id__in=version_ids, course__teacher__isnull=False
        ).values_list(
            "timetable_id",
            "weekday",
            "course__teacher_id",
            "first",
            "length",
            "course__name",
            "course__class_group_id",
        )
    )
    names = {
        group.pk: group.name
        for group in ClassGroup.objects.filter(pk__in={row[6] for row in rows}).select_related(
            "level", "track"
        )
    }
    grouped: dict[tuple, dict] = {}
    for version, weekday, teacher, first, length, course, group in sorted(
        rows, key=lambda row: names.get(row[6], "")
    ):
        key = (version, weekday, teacher, first)
        found = grouped.setdefault(key, {"length": length, "course": course, "groups": []})
        found["groups"].append(names.get(group, ""))
    slots: dict[tuple, list[Slot]] = defaultdict(list)
    for (version, weekday, teacher, first), found in grouped.items():
        label = f"{found['course']} · {', '.join(found['groups'])}"
        slots[(version, weekday)].append(Slot(teacher, first, found["length"], label))
    return slots


@dataclass
class Line:
    teacher_id: object
    name: str = ""
    planned: int = 0
    absent: int = 0
    cancelled: int = 0
    replacements: int = 0
    extra: int = 0
    by_label: dict = field(default_factory=lambda: defaultdict(lambda: [0, 0, 0, 0]))

    @property
    def given(self) -> int:
        return self.planned - self.absent - self.cancelled + self.replacements + self.extra


def month_report(month: date, *, teacher=None) -> dict:
    """Le mois (jusqu'à aujourd'hui) : jours de cours, congés, une ligne par enseignant qui avait
    des heures ou une exception, et les exceptions actives ; `teacher` : lui seul."""
    year = _year()
    first, last = month_range(month)
    last = min(last, timezone.localdate())
    days, holidays = school_days(first, last, year)
    versions = _versions(year)
    by_day = {day: version for day in days if (version := in_effect(versions, day))}
    slots = _slots({version.pk for version in by_day.values()})
    lines: dict = {}

    def line(pk) -> Line:
        return lines.setdefault(pk, Line(pk))

    taught = 0
    for day, version in by_day.items():
        today_slots = slots.get((version.pk, day.isoweekday()), [])
        taught += bool(today_slots)
        for slot in today_slots:
            if teacher is None or slot.teacher_id == teacher.pk:
                current = line(slot.teacher_id)
                current.planned += slot.length
                current.by_label[slot.label][0] += slot.length
    school_day = set(days)
    exceptions = list(
        LessonException.objects.filter(
            date__gte=first, date__lte=last, cancelled_at__isnull=True
        ).select_related("teacher", "replacement", "created_by")
    )
    for exception in exceptions:
        hours, label = exception.hours, exception.label
        if exception.kind in FROM_TIMETABLE and exception.date not in school_day:
            continue  # jour devenu congé après coup : rien n'était prévu
        if teacher is None or exception.teacher_id == teacher.pk:
            current = line(exception.teacher_id)
            if exception.kind in MISSED:
                current.absent += hours
                current.by_label[label][1] += hours
            elif exception.kind == Kind.CANCELLED:
                current.cancelled += hours
                current.by_label[label][1] += hours
            else:
                current.extra += hours
                current.by_label[label][3] += hours
        if exception.kind == Kind.REPLACED and (
            teacher is None or exception.replacement_id == teacher.pk
        ):
            current = line(exception.replacement_id)
            current.replacements += hours
            current.by_label[label][2] += hours
    people = User.objects.filter(pk__in=lines).order_by("last_name", "middle_name", "first_name")
    ordered = []
    for person in people:
        lines[person.pk].name = person.get_full_name()
        ordered.append(lines[person.pk])
    mine = [
        exception
        for exception in exceptions
        if teacher is None or teacher.pk in (exception.teacher_id, exception.replacement_id)
    ]
    return {
        "month": first,
        "school_days": taught,
        "holidays": holidays,
        "teachers": ordered,
        "exceptions": sorted(mine, key=lambda row: (row.date, row.first or 0)),
        "totals": {
            "planned": sum(row.planned for row in ordered),
            "missed": sum(row.absent + row.cancelled for row in ordered),
            "added": sum(row.replacements + row.extra for row in ordered),
        },
    }


def day_lessons(day: date, teacher: User) -> list[dict]:
    """Les heures de l'enseignant ce jour-là dans l'horaire en vigueur (pour noter une exception),
    une par heure même pour un cours commun, avec l'exception déjà notée."""
    year = _year()
    version = in_effect(_versions(year), day)
    if version is None:
        return []
    found = schedule.lessons(version, Q(course__teacher=teacher, weekday=day.isoweekday()))
    recorded = dict(
        LessonException.objects.filter(
            date=day, teacher=teacher, cancelled_at__isnull=True, first__isnull=False
        ).values_list("first", "kind")
    )
    rows: dict = {}
    for lesson in found:
        row = rows.setdefault(
            lesson.first,
            {
                "entry": lesson.entry_id,
                "first": lesson.first,
                "length": lesson.length,
                "start": lesson.start,
                "end": lesson.end,
                "course": lesson.course,
                "class_groups": [],
                "recorded": recorded.get(lesson.first),
            },
        )
        row["class_groups"].append(lesson.class_group)
    return list(rows.values())


def _snapshot(exception: LessonException) -> dict:
    return {
        "date": exception.date.isoformat(),
        "kind": exception.kind,
        "teacher": exception.teacher.get_full_name(),
        "replacement": exception.replacement.get_full_name() if exception.replacement else None,
        "lesson": exception.label,
        "hours": exception.hours,
        "reason": exception.reason,
    }


def _staff(person: User | None) -> User | None:
    if person is not None and not active_staff().filter(pk=person.pk).exists():
        raise BusinessError(UNKNOWN_PERSON)
    return person


@transaction.atomic
def record(
    *,
    actor,
    day: date,
    kind: str,
    teacher: User,
    reason: str,
    entries=(),
    replacement: User | None = None,
    course: Course | None = None,
    hours: int | None = None,
) -> list[LessonException]:
    """Note ce qui s'est passé un jour : pour une absence, un remplacement ou une annulation, une
    exception par heure de l'horaire de l'enseignant (`entries`) ; pour une heure en plus, le cours
    et le nombre d'heures. Tout est vérifié avant d'écrire ; journal de chaque ligne."""
    year = _year()
    if day > timezone.localdate():
        raise BusinessError(FUTURE)
    if day not in school_days(day, day, year)[0]:
        raise BusinessError(NOT_A_SCHOOL_DAY)
    _staff(teacher)
    rows = []
    if kind in FROM_TIMETABLE:
        version = in_effect(_versions(year), day)
        wanted = set(entries)
        found = list(
            TimetableEntry.objects.filter(
                pk__in=wanted, timetable=version, weekday=day.isoweekday(), course__teacher=teacher
            ).select_related("course__class_group__level", "course__class_group__track")
            if version and wanted
            else []
        )
        if not wanted or len(found) != len(wanted):
            raise BusinessError(NOT_IN_TIMETABLE)
        if kind == Kind.REPLACED:
            if replacement is None or replacement.pk == teacher.pk:
                raise BusinessError(REPLACEMENT_REQUIRED)
            _staff(replacement)
        else:
            replacement = None
        for entry in found:
            rows.append(
                LessonException(
                    date=day,
                    kind=kind,
                    teacher=teacher,
                    replacement=replacement,
                    entry=entry,
                    course=entry.course,
                    first=entry.first,
                    hours=entry.length,
                    label=f"{entry.course.name} · {entry.course.class_group.name}",
                    reason=reason,
                    created_by=actor,
                )
            )
    else:
        if (
            course is None
            or not Course.objects.filter(
                pk=course.pk, class_group__academic_year=year, is_taught=True
            ).exists()
        ):
            raise BusinessError(UNKNOWN_COURSE)
        rows.append(
            LessonException(
                date=day,
                kind=Kind.EXTRA,
                teacher=teacher,
                course=course,
                hours=max(1, min(hours or 1, EXTRA_MAX)),
                label=f"{course.name} · {course.class_group.name}",
                reason=reason,
                created_by=actor,
            )
        )
    try:
        with transaction.atomic():
            for row in rows:
                row.save()
    except IntegrityError as error:
        raise BusinessError(ALREADY) from error
    for row in rows:
        audit.record(
            Action.LESSON_EXCEPTION_RECORDED, row, actor=actor, after=_snapshot(row), label=str(row)
        )
    return rows


@transaction.atomic
def cancel(exception: LessonException, *, actor, reason: str) -> LessonException:
    """Retire une exception du calcul sans l'effacer : qui, quand, motif ; journal."""
    exception = LessonException.objects.select_for_update().get(pk=exception.pk)
    if exception.cancelled_at is not None:
        raise BusinessError(ALREADY_CANCELLED)
    exception.cancelled_at = timezone.now()
    exception.cancelled_by = actor
    exception.cancel_reason = reason
    exception.save(update_fields=["cancelled_at", "cancelled_by", "cancel_reason", "updated_at"])
    audit.record(
        Action.LESSON_EXCEPTION_CANCELLED,
        exception,
        actor=actor,
        before=_snapshot(exception),
        after={"cancelled": True, "reason": reason},
        label=str(exception),
    )
    return exception


def sheet(month: date, teacher: User) -> dict:
    """Contexte de la fiche d'un enseignant (PDF) : une ligne par cours et classe, le total, le
    détail des exceptions du mois."""
    report = month_report(month, teacher=teacher)
    line = next((row for row in report["teachers"] if row.teacher_id == teacher.pk), None)
    rows = [
        {
            "label": label,
            "planned": planned,
            "missed": missed,
            "replacements": done,
            "extra": extra,
            "given": planned - missed + done + extra,
        }
        for label, (planned, missed, done, extra) in sorted((line.by_label if line else {}).items())
    ]
    return {
        "month": report["month"],
        "teacher": teacher.get_full_name(),
        "school_days": report["school_days"],
        "holidays": report["holidays"],
        "rows": rows,
        "line": line or Line(teacher.pk, teacher.get_full_name()),
        "exceptions": report["exceptions"],
    }

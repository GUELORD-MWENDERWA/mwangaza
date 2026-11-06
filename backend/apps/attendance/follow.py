"""Suivi des présences (6.5) : présents, retards et absents, calculés à la demande, jamais
stockés. Un jour compte s'il a sa séance « entrée » (quelqu'un a pointé) et n'est pas un congé de
l'école (`SchoolEvent` « congé ») : un dimanche, ou un jour où l'école n'a pas pointé, personne
n'est absent. Un élève est attendu à partir de son inscription (`enrolled_on`).

La correction la plus récente d'une personne pour un jour l'emporte sur son passage ; une
absence couverte par une justification acceptée est justifiée, par une justification en attente,
« en attente ». `totals` compte en six requêtes quel que soit le nombre d'élèves ou de jours
(regroupement dans la base, seules les corrections et les jours justifiés sont lus un par un)."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, QuerySet

from apps.attendance.cards import current_enrollments
from apps.attendance.models import (
    AbsenceJustification,
    AttendanceCorrection,
    AttendanceRecord,
    AttendanceSession,
)
from apps.notifications.models import SchoolEvent
from apps.students.models import Enrollment

PRESENT, LATE, ABSENT = "present", "late", "absent"
Status = AbsenceJustification.Status


@dataclass
class Totals:
    """Jours de classe attendus d'une personne et ce qu'elle en a fait."""

    days: int = 0
    present: int = 0
    late: int = 0
    justified: int = 0
    pending: int = 0

    @property
    def absent(self) -> int:
        return self.days - self.present - self.late

    @property
    def unjustified(self) -> int:
        return self.absent - self.justified

    @property
    def rate(self) -> int | None:
        """Taux de présence en pour cent (retards compris), arrondi ; None sans jour attendu."""
        return round(100 * (self.present + self.late) / self.days) if self.days else None


def holidays(start: date, end: date) -> set[date]:
    off = set()
    for first, last in SchoolEvent.objects.filter(
        kind=SchoolEvent.Kind.HOLIDAY, starts_on__lte=end, ends_on__gte=start
    ).values_list("starts_on", "ends_on"):
        day = max(first, start)
        while day <= min(last, end):
            off.add(day)
            day += timedelta(days=1)
    return off


def school_days(start: date, end: date) -> dict[date, object]:
    """Jours de classe entre `start` et `end` (séance « entrée », hors congés) : {jour: séance}.
    Deux requêtes."""
    sessions = dict(
        AttendanceSession.objects.filter(
            kind=AttendanceSession.Kind.ENTRANCE, date__gte=start, date__lte=end
        ).values_list("date", "id")
    )
    if not sessions:
        return {}
    off = holidays(min(sessions), max(sessions))
    return {day: sessions[day] for day in sorted(sessions) if day not in off}


def is_school_day(day: date) -> bool:
    return bool(school_days(day, day))


def windows(enrollments: QuerySet[Enrollment], start: date) -> dict:
    """{élève: premier jour attendu} des inscriptions données (au plus tôt `start`)."""
    return {
        student: max(enrolled_on, start)
        for student, enrolled_on in enrollments.values_list("student_id", "enrolled_on")
    }


def totals(first_days: dict, days: dict[date, object]) -> dict:
    """{élève: `Totals`} sur les jours de classe `days` ({jour: séance}), chacun à partir de son
    premier jour attendu (`first_days`, voir `windows`)."""
    ordered = sorted(days)
    sessions = {session: day for day, session in days.items()}
    result = {
        student: Totals(days=len(ordered) - bisect_left(ordered, first))
        for student, first in first_days.items()
    }
    if not ordered or not result:
        return result
    students = list(result)

    def expected(student, day) -> bool:
        return day >= first_days[student]

    # Passages, regroupés dans la base.
    for student, status, count in (
        AttendanceRecord.objects.filter(session_id__in=sessions, student_id__in=students)
        .values("student_id", "status")
        .annotate(count=Count("id"))
        .values_list("student_id", "status", "count")
    ):
        setattr(result[student], status, getattr(result[student], status) + count)
    # Passages d'avant l'inscription (date changée ensuite) : retirés, presque toujours aucun.
    later = {student: first for student, first in first_days.items() if first > ordered[0]}
    if later:
        for student, day, status in AttendanceRecord.objects.filter(
            student_id__in=later, session_id__in=sessions, session__date__lt=max(later.values())
        ).values_list("student_id", "session__date", "status"):
            if day < later[student]:
                setattr(result[student], status, getattr(result[student], status) - 1)

    # Corrections : la plus récente de chaque jour l'emporte.
    corrected = {
        (session, student): status
        for session, student, status in AttendanceCorrection.objects.filter(
            session_id__in=sessions, student_id__in=students
        )
        .order_by("created_at")
        .values_list("session_id", "student_id", "status")
        if expected(student, sessions[session])
    }
    # Jours couverts par une justification acceptée (elle l'emporte sur une en attente).
    covered = {}
    for student, first, last, status in (
        AbsenceJustification.objects.filter(
            student_id__in=students,
            status__in=[Status.ACCEPTED, Status.PENDING],
            starts_on__lte=ordered[-1],
            ends_on__gte=ordered[0],
        )
        .order_by("status")  # « accepted » avant « pending »
        .values_list("student_id", "starts_on", "ends_on", "status")
    ):
        for day in ordered[bisect_left(ordered, first) : bisect_right(ordered, last)]:
            if expected(student, day):
                covered.setdefault((days[day], student), status)

    pairs = set(corrected) | set(covered)
    base = _records(pairs)
    for pair, status in corrected.items():
        _move(result[pair[1]], base.get(pair, ABSENT), status)
    for pair, status in covered.items():
        if corrected.get(pair, base.get(pair, ABSENT)) == ABSENT:
            if status == Status.ACCEPTED:
                result[pair[1]].justified += 1
            else:
                result[pair[1]].pending += 1
    return result


def _records(pairs: set) -> dict:
    """Statut du passage de chaque (séance, élève) demandé ; une requête."""
    if not pairs:
        return {}
    found = AttendanceRecord.objects.filter(
        session_id__in={session for session, _ in pairs},
        student_id__in={student for _, student in pairs},
    ).values_list("session_id", "student_id", "status")
    return {(session, student): status for session, student, status in found}


def _move(totals_: Totals, before: str, after: str) -> None:
    if before != ABSENT:
        setattr(totals_, before, getattr(totals_, before) - 1)
    if after != ABSENT:
        setattr(totals_, after, getattr(totals_, after) + 1)


# Un jour


@dataclass
class Day:
    """Un jour : la séance (None : pas un jour de classe), l'état de chaque élève attendu."""

    date: date
    session: object | None
    holiday: bool
    students: dict  # {élève: Totals d'un jour}
    classes: dict  # {élève: classe}


def day_of(day: date, enrollments: QuerySet[Enrollment] | None = None) -> Day:
    """Élèves inscrits ce jour-là (toute l'école, ou `enrollments`), chacun avec son état."""
    chosen = current_enrollments() if enrollments is None else enrollments
    enrollments = chosen.filter(enrolled_on__lte=day)
    days = school_days(day, day)
    session = days.get(day)
    holiday = session is None and bool(holidays(day, day))
    classes = dict(enrollments.values_list("student_id", "class_group_id"))
    students = totals(dict.fromkeys(classes, day), days) if session else {}
    return Day(date=day, session=session, holiday=holiday, students=students, classes=classes)


def state(totals_: Totals) -> str:
    """État d'un élève pour un jour : `present`, `late`, `absent` (non justifié), `pending`
    (justification en attente) ou `justified`."""
    if totals_.present:
        return PRESENT
    if totals_.late:
        return LATE
    if totals_.justified:
        return "justified"
    return "pending" if totals_.pending else ABSENT


def by_class(day: Day) -> dict:
    """{classe: compteurs} : élèves, présents, retards, absents, justifiés."""
    counts = defaultdict(lambda: defaultdict(int))
    for student, group in day.classes.items():
        row = counts[group]
        row["enrolled"] += 1
        if day.session is None:
            continue
        current = state(day.students[student])
        row[current if current in (PRESENT, LATE, "justified") else ABSENT] += 1
        if current == "justified":
            row[ABSENT] += 1
    return counts


def staff_statuses(session, ids: list) -> dict:
    """{membre: present / late / absent} du jour (`ids` : les membres), corrections comprises ;
    deux requêtes."""
    if session is None:
        return {}
    statuses = dict.fromkeys(ids, ABSENT)
    statuses.update(
        AttendanceRecord.objects.filter(session=session, member_id__in=ids).values_list(
            "member_id", "status"
        )
    )
    statuses.update(
        AttendanceCorrection.objects.filter(session=session, member_id__in=ids)
        .order_by("created_at")
        .values_list("member_id", "status")
    )
    return statuses


# Un élève, jour par jour (Portail)


def absences_of(student, first: date, days: dict[date, object]) -> list[tuple[date, str]]:
    """Jours d'absence d'un élève, du plus récent au plus ancien, avec leur état (`absent`,
    `pending`, `justified`) ; trois requêtes."""
    ordered = [day for day in sorted(days) if day >= first]
    if not ordered:
        return []
    sessions = [days[day] for day in ordered]
    base = dict(
        AttendanceRecord.objects.filter(session_id__in=sessions, student=student).values_list(
            "session_id", "status"
        )
    )
    base.update(
        AttendanceCorrection.objects.filter(session_id__in=sessions, student=student)
        .order_by("created_at")
        .values_list("session_id", "status")
    )
    covered = {}
    for first_day, last_day, status in (
        AbsenceJustification.objects.filter(
            student=student,
            status__in=[Status.ACCEPTED, Status.PENDING],
            starts_on__lte=ordered[-1],
            ends_on__gte=ordered[0],
        )
        .order_by("status")
        .values_list("starts_on", "ends_on", "status")
    ):
        for day in ordered[bisect_left(ordered, first_day) : bisect_right(ordered, last_day)]:
            covered.setdefault(day, "justified" if status == Status.ACCEPTED else "pending")
    return [
        (day, covered.get(day, ABSENT))
        for day in reversed(ordered)
        if base.get(days[day], ABSENT) == ABSENT
    ]

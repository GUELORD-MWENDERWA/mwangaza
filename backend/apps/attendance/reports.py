"""Écrans du suivi des présences (6.5) : un jour à l'entrée, ses absents, le personnel, et le
rapport d'une période en Excel. Tout est calculé par `follow` ; ici, seulement la mise en forme
pour l'API (une page à la fois pour les listes)."""

from collections import Counter
from dataclasses import dataclass
from datetime import date

from django.db.models import QuerySet
from django.http import FileResponse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.attendance import follow
from apps.attendance.cards import current_enrollments, staff
from apps.attendance.models import AbsenceJustification, AttendanceRecord
from apps.core.documents import workbook
from apps.core.http import LOGO_TYPES
from apps.core.tenancy import require_current_school
from apps.notifications.models import ScheduledRun
from apps.schools import organisation
from apps.schools.attendance import attendance_settings
from apps.schools.models import ClassGroup

ABSENT_STATES = ("absent", "pending", "justified")
# Ordre des classes (celui de `ClassGroup`), puis des noms.
BY_CLASS = (
    "class_group__level__order",
    "class_group__level__name",
    "class_group__track__name",
    "class_group__section",
    "student__last_name",
    "student__first_name",
    "pk",
)
CLASS_NAME = ("class_group__level", "class_group__track")


def day_summary(day: date) -> dict:
    """Compteurs du jour : école, personnel, chaque classe (une ligne par classe qui a des
    élèves). Sept requêtes environ, quel que soit le nombre d'élèves."""
    today = follow.day_of(day)
    states = Counter(follow.state(totals) for totals in today.students.values())
    enrolled = len(today.classes)
    arrived = states["present"] + states["late"]
    per_class = follow.by_class(today)
    groups = ClassGroup.objects.filter(pk__in=per_class).select_related("level", "track")
    members = list(staff().values_list("pk", flat=True))
    staff_states = follow.staff_statuses(today.session, members)
    run = ScheduledRun.objects.filter(job=ScheduledRun.Job.ABSENCES, day=day).first()
    settings = attendance_settings(require_current_school().settings)
    return {
        "date": day,
        "school_day": today.session is not None,
        "holiday": today.holiday,
        "enrolled": enrolled,
        "present": states["present"],
        "late": states["late"],
        "absent": enrolled - arrived if today.session else 0,
        "justified": states["justified"],
        "pending": states["pending"],
        "rate": round(100 * arrived / enrolled) if today.session and enrolled else None,
        "staff_present": sum(1 for state in staff_states.values() if state != follow.ABSENT),
        "staff_total": len(members),
        "late_after": settings["late_after"],
        "parents_notified_at": run.created_at if run else None,
        "alert_after": settings["alert_after"],
        "classes": [
            {
                "id": group.pk,
                "name": group.name,
                "enrolled": per_class[group.pk]["enrolled"],
                "present": per_class[group.pk]["present"],
                "late": per_class[group.pk]["late"],
                "absent": per_class[group.pk]["absent"],
                "justified": per_class[group.pk]["justified"],
            }
            for group in groups
        ],
    }


@dataclass
class Absents:
    enrollments: QuerySet
    states: dict


def absents(day: date, class_group: ClassGroup | None, state: str | None) -> Absents:
    """Inscriptions des absents du jour (à paginer), par classe puis nom, et l'état de chacun."""
    enrollments = current_enrollments()
    if class_group is not None:
        enrollments = enrollments.filter(class_group=class_group)
    today = follow.day_of(day, enrollments)
    states = {
        student: current
        for student, totals in today.students.items()
        if (current := follow.state(totals)) in ABSENT_STATES and current == (state or current)
    }
    return Absents(
        enrollments=enrollments.filter(student_id__in=list(states))
        .select_related("student__family", *CLASS_NAME)
        .order_by(*BY_CLASS),
        states=states,
    )


def absence_rows(day: date, page, states: dict) -> list[dict]:
    """Lignes d'une page d'absents : absences non justifiées de l'année et justification du
    jour. Six requêtes pour la page."""
    year = organisation.current_year()
    if not page or year is None:
        return []
    counts = follow.totals(
        {item.student_id: max(item.enrolled_on, year.starts_on) for item in page},
        follow.school_days(year.starts_on, day),
    )
    covering = {}
    for justification, student in (
        AbsenceJustification.objects.filter(
            student_id__in=[item.student_id for item in page],
            status__in=[AbsenceJustification.Status.ACCEPTED, AbsenceJustification.Status.PENDING],
            starts_on__lte=day,
            ends_on__gte=day,
        )
        .order_by("status")
        .values_list("pk", "student_id")
    ):
        covering.setdefault(student, justification)
    return [
        {
            "student": item.student,
            "class_group": item.class_group,
            "state": states[item.student_id],
            "unjustified": counts[item.student_id].unjustified,
            "parent_on_portal": item.student.family.primary_user_id is not None
            and item.student.family.portal_suspended_at is None,
            "justification_id": covering.get(item.student_id),
        }
        for item in page
    ]


def staff_rows(day: date, page) -> list[dict]:
    """Lignes d'une page du personnel : état du jour et heure du passage."""
    session = follow.school_days(day, day).get(day)
    ids = [member.pk for member in page]
    statuses = follow.staff_statuses(session, ids)
    seen = (
        dict(
            AttendanceRecord.objects.filter(session_id=session, member_id__in=ids).values_list(
                "member_id", "seen_at"
            )
        )
        if session
        else {}
    )
    return [
        {
            "id": member.pk,
            "user": member.user,
            "status": statuses.get(member.pk, follow.ABSENT),
            "seen_at": seen.get(member.pk),
        }
        for member in page
    ]


def export(date_from: date, date_to: date, class_group: ClassGroup | None) -> tuple[bytes, str]:
    """Classeur de la période : une ligne par élève inscrit (classe, nom)."""
    enrollments = current_enrollments()
    if class_group is not None:
        enrollments = enrollments.filter(class_group=class_group)
    days = follow.school_days(date_from, min(date_to, timezone.localdate()))
    counts = follow.totals(follow.windows(enrollments, date_from), days)

    def row(item) -> list:
        totals = counts[item.student_id]
        return [
            item.student.matricule,
            item.student.full_name,
            item.class_group.name,
            totals.days,
            totals.present,
            totals.late,
            totals.absent,
            totals.justified,
            totals.rate,
        ]

    ordered = enrollments.select_related("student", *CLASS_NAME).order_by(*BY_CLASS)
    rows = (row(item) for item in ordered)
    content = workbook(
        [
            _("Student number"),
            _("Student"),
            _("Class"),
            _("School days"),
            _("On time"),
            _("Late"),
            _("Absences"),
            _("Justified"),
            _("Attendance rate (%)"),
        ],
        rows,
        title=_("Attendance"),
        widths=[16, 30, 22, 12, 12, 10, 12, 12, 14],
    )
    return content, f"presences-{date_from:%Y%m%d}-{date_to:%Y%m%d}.xlsx"


def document_response(justification: AbsenceJustification) -> FileResponse:
    """Le certificat, servi comme un fichier privé : jamais exécuté dans la page."""
    kind = justification.document.name.rsplit(".", 1)[-1]
    response = FileResponse(
        justification.document.open("rb"),
        content_type="application/pdf" if kind == "pdf" else LOGO_TYPES.get(kind, "image/jpeg"),
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    response["Cache-Control"] = "private, max-age=3600"
    return response

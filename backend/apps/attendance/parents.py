"""Présences et parents (6.6). Chaque jour de classe, à l'heure choisie par l'école (après
l'heure limite d'arrivée), le passage du planificateur (`notifications/scheduled.py`, travail
`absences`, une fois par jour) prévient le parent de chaque enfant absent sans justification —
une notification par parent, ses enfants réunis — et signale à la direction les élèves qui
atteignent le seuil d'absences non justifiées de l'année (puis chaque multiple du seuil).

Le Portail montre au parent les présences de son enfant et lui permet de justifier une absence ;
un parent ne voit que ses enfants (`portal.children.find_student`)."""

from collections import defaultdict
from datetime import date

from django.utils import timezone, translation
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.attendance import corrections, follow
from apps.attendance.cards import current_enrollments
from apps.attendance.models import AbsenceJustification
from apps.notifications import events, push
from apps.notifications.models import Notification
from apps.portal.children import find_student, in_school
from apps.schools import organisation
from apps.schools.attendance import attendance_settings
from apps.schools.models import School
from apps.students.models import Enrollment, Family, Student

App, Kind = Notification.App, Notification.Kind
# Noms cités dans l'alerte à la direction ; les autres sont comptés.
ALERT_NAMES = 8
# Absences montrées au parent (les plus récentes) et justifications.
CHILD_ABSENCES, CHILD_JUSTIFICATIONS = 60, 20


def morning(school: School, day: date) -> int:
    """Travail du matin d'une école (dans son fuseau) : rien un jour sans pointage ou de congé.
    Rend le nombre de notifications créées."""
    today = follow.day_of(day)
    if today.session is None:
        return 0
    absent = [
        student for student, totals in today.students.items() if follow.state(totals) == "absent"
    ]
    if not absent:
        return 0
    created = _tell_parents(school, day, absent) if school.has_module("portal") else 0
    return created + _alert(school, day, absent)


def _tell_parents(school: School, day: date, absent: list) -> int:
    """Une notification par parent (compte du portail actif, accès non suspendu), tous ses
    enfants absents réunis, dans sa langue."""
    by_family = defaultdict(list)
    for student in Student.objects.filter(pk__in=absent).only("id", "family_id", "first_name"):
        by_family[student.family_id].append(student)
    parents = {
        family.pk: family.primary_user
        for family in Family.objects.filter(
            pk__in=by_family, primary_user__is_active=True, portal_suspended_at__isnull=True
        ).select_related("primary_user")
    }
    drafts = []
    for family, parent in parents.items():
        children = by_family[family]
        names = ", ".join(sorted(student.first_name or str(student) for student in children))
        with translation.override(parent.language):
            title = ngettext(
                "Absent this morning: %(names)s",
                "Absent this morning: %(names)s",
                len(children),
            ) % {"names": names}
            body = _(
                "Not recorded at the entrance on %(date)s. "
                "Was it planned? Justify it in the Portal."
            ) % {"date": date_format(day, "l j F")}
        url = f"/children/{children[0].pk}/attendance" if len(children) == 1 else "/"
        drafts.append(
            push.draft(parent, app=App.PORTAIL, kind=Kind.ABSENCE, title=title, body=body, url=url)
        )
    return len(push.create(school, drafts))


def _alert(school: School, day: date, absent: list) -> int:
    """Élèves absents ce matin dont les absences non justifiées de l'année atteignent le seuil
    de l'école ou un de ses multiples : une notification à la direction."""
    threshold = attendance_settings(school.settings)["alert_after"]
    year = organisation.current_year()
    if not threshold or year is None:
        return 0
    days = follow.school_days(year.starts_on, day)
    counts = follow.totals(
        follow.windows(current_enrollments().filter(student_id__in=absent), year.starts_on), days
    )
    reached = [
        student
        for student, totals in counts.items()
        if totals.unjustified and totals.unjustified % threshold == 0
    ]
    if not reached:
        return 0
    names = sorted(str(student) for student in Student.objects.filter(pk__in=reached))
    shown = ", ".join(names[:ALERT_NAMES])
    more = len(names) - ALERT_NAMES

    def text():
        title = ngettext(
            "%(count)d student reached %(threshold)d unjustified absences",
            "%(count)d students reached %(threshold)d unjustified absences",
            len(names),
        ) % {"count": len(names), "threshold": threshold}
        body = (
            shown
            if more <= 0
            else _("%(names)s and %(more)d others")
            % {
                "names": shown,
                "more": more,
            }
        )
        return title, body

    return events.send(
        events.staff(Kind.ABSENCE_ALERT),
        app=App.GESTION,
        kind=Kind.ABSENCE_ALERT,
        url="/attendance?tab=absences",
        text=text,
    )


# Portail


def _enrollment(student: Student) -> Enrollment:
    return current_enrollments().filter(student=student).select_related("class_group").first()


def child_attendance(user: User, student_id) -> dict:
    """Présences de l'année d'un enfant : totaux, jours d'absence (état de chacun) et
    justifications envoyées ; 404 si l'enfant n'est pas d'une famille reliée au compte, ou si
    l'école n'a pas le module des présences."""
    student = _child(user, student_id)
    with in_school(student.school):
        enrollment = _enrollment(student)
        year = organisation.current_year()
        if enrollment is None or year is None:
            raise NotFound
        days = follow.school_days(year.starts_on, timezone.localdate())
        first = max(enrollment.enrolled_on, year.starts_on)
        totals = follow.totals({student.pk: first}, days)[student.pk]
        absences = follow.absences_of(student, first, days)[:CHILD_ABSENCES]
        justifications = list(
            AbsenceJustification.objects.filter(student=student)[:CHILD_JUSTIFICATIONS]
        )
        return {
            "student": student,
            "class_group": str(enrollment.class_group),
            "totals": totals,
            "absences": [{"date": day, "state": state} for day, state in absences],
            "justifications": justifications,
        }


def justify(user: User, student_id, **fields) -> AbsenceJustification:
    """Le parent justifie une absence de son enfant (en attente) ; l'école en est prévenue."""
    student = _child(user, student_id)
    with in_school(student.school):
        return corrections.justify(actor=user, student=student, by_school=False, **fields)


def _child(user: User, student_id) -> Student:
    student = find_student(user, student_id)
    if not student.school.has_module("attendance"):
        raise NotFound
    return student

"""Réussite et examens de repêchage (8.4.1) : d'après le pourcentage de l'année de chaque cours et
les règles de l'école (`schools/pass_rules.py`), le système repère les cours échoués, ceux qui
ouvrent un repêchage, et propose l'issue de l'élève. L'enseignant du cours saisit (et signe) la
note de repêchage de chaque cours échoué. Rien n'est stocké que cette note : la proposition suit
les notes et les règles. La décision prise (admis, doublant…) est celle de la délibération (8.4.2).

Issues proposées : `incomplete` (une note de l'année manque), `passed`, `resit` (notes de
repêchage attendues), `failed`.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.academics import report_cards
from apps.academics.grades import gradable_courses
from apps.academics.models import Course, ResitGrade
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.schools import pass_rules as rules_module
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment

INCOMPLETE, PASSED, RESIT, FAILED = "incomplete", "passed", "resit", "failed"

NOT_A_RESIT_COURSE = ApiError(
    "not_a_resit_course", _("This course does not open a resit exam for this student."), 400
)
BAD_PERCENT = ApiError("bad_percent", _("A resit grade is a percentage from 0 to 100."), 400)
STEP = Decimal("0.1")


@dataclass
class CourseResit:
    course: Course
    percent: Decimal
    eligible: bool
    resit: ResitGrade | None = None
    can_enter: bool = False

    def passed(self, rules: dict) -> bool | None:
        if self.resit is None:
            return None
        return self.resit.percent >= rules["course_pass_percent"]


@dataclass
class StudentResits:
    enrollment: Enrollment
    percent: Decimal | None
    outcome: str
    failed: list[CourseResit] = field(default_factory=list)


def _outcome(rules: dict, percent: Decimal | None, complete: bool, failed: list[CourseResit]):
    if percent is None or not complete:
        return INCOMPLETE
    if percent < rules["pass_percent"] or any(not f.eligible for f in failed):
        return FAILED
    if not failed:
        return PASSED
    if any(f.resit is None for f in failed):
        return RESIT
    lost = sum(1 for f in failed if not f.passed(rules))
    return FAILED if lost >= rules["resit_failures_to_fail"] else PASSED


def rules_of(group: ClassGroup) -> dict:
    """Règles de la classe : celles de l'école, que son niveau peut remplacer (7e, 3e…)."""
    return rules_module.class_rules(group.school.settings, group.level.pass_rules)


def class_overview(
    report: report_cards.ClassReport, *, user: User | None = None, permissions=()
) -> list[StudentResits]:
    """Pour chaque élève de la classe : pourcentage de l'année, cours échoués (avec la note de
    repêchage éventuelle) et issue proposée. Une requête pour les notes de repêchage de toute la
    classe ; `user` et `permissions` disent quels cours la personne peut noter."""
    rules = rules_of(report.class_group)
    resits = {
        (r.enrollment_id, r.course_id): r
        for r in ResitGrade.objects.filter(
            enrollment__in=[s.enrollment.pk for s in report.students]
        ).select_related("signed_by")
    }
    enterable: set[UUID] = set()
    if user is not None:
        enterable = set(
            gradable_courses(user, permissions)
            .filter(class_group=report.class_group)
            .values_list("pk", flat=True)
        )
    result = []
    for student in report.students:
        total = student.totals.get(report_cards.YEAR_KEY)
        failed, complete = [], True
        for course in report.courses:
            cell = student.cells[course.pk].get(report_cards.YEAR_KEY)
            if not course.is_taught or cell is None or not cell.maximum:
                continue
            if cell.score is None:
                complete = False
                continue
            percent = report_cards._percent(cell.score, cell.maximum)
            if percent >= rules["course_pass_percent"]:
                continue
            eligible = course.resit_allowed and (
                rules["resit_mode"] == rules_module.ANY_FAILED
                or percent >= rules["resit_floor_percent"]
            )
            failed.append(
                CourseResit(
                    course,
                    percent,
                    eligible,
                    resits.get((student.enrollment.pk, course.pk)),
                    course.pk in enterable,
                )
            )
        if sum(f.eligible for f in failed) > rules["max_resit_courses"]:
            # Trop de cours à repêcher : aucun repêchage, l'année est reprise.
            for row in failed:
                row.eligible = False
        year_percent = total.percent if total else None
        result.append(
            StudentResits(
                student.enrollment,
                year_percent,
                _outcome(rules, year_percent, complete, failed),
                failed,
            )
        )
    return result


def record(
    enrollment: Enrollment, course: Course, *, actor: User, permissions, percent: Decimal
) -> ResitGrade:
    """Saisit (ou remplace) la note de repêchage d'un cours échoué ; l'enseignant la signe. Le
    cours doit être l'un de ceux qui ouvrent un repêchage pour cet élève."""
    percent = Decimal(percent).quantize(STEP)
    if not Decimal(0) <= percent <= Decimal(100):
        raise BusinessError(BAD_PERCENT)
    row = _failed_course(enrollment, course, actor, permissions)
    with transaction.atomic():
        before = {"percent": str(row.resit.percent)} if row.resit else None
        saved, _created = ResitGrade.objects.update_or_create(
            enrollment=enrollment,
            course=course,
            defaults={"percent": percent, "signed_by": actor},
        )
        audit.record(
            Action.RESIT_GRADE_CHANGED,
            saved,
            actor=actor,
            before=before,
            after={"percent": str(percent), "course": course.name},
            label=f"{enrollment.student.full_name} · {course.name}",
        )
    return saved


def clear(enrollment: Enrollment, course: Course, *, actor: User, permissions) -> None:
    """Reprend la note de repêchage ; le journal garde la note retirée."""
    row = _failed_course(enrollment, course, actor, permissions)
    if row.resit is None:
        return
    with transaction.atomic():
        before = {"percent": str(row.resit.percent), "course": course.name}
        row.resit.delete()
        audit.record(
            Action.RESIT_GRADE_CHANGED,
            None,
            actor=actor,
            before=before,
            after=None,
            label=f"{enrollment.student.full_name} · {course.name}",
        )


def _failed_course(enrollment, course, actor, permissions) -> CourseResit:
    if course.class_group_id != enrollment.class_group_id:
        raise BusinessError(NOT_A_RESIT_COURSE)
    report = report_cards.class_report(enrollment.class_group)
    for student in class_overview(report, user=actor, permissions=permissions):
        if student.enrollment.pk == enrollment.pk:
            for row in student.failed:
                if row.course.pk == course.pk and row.eligible:
                    return row
    raise BusinessError(NOT_A_RESIT_COURSE)

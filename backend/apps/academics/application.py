"""Application (8.5.1c) : la cote de chaque période est proposée d'après le pourcentage de la
période au bulletin, et le titulaire de la classe peut la corriger, avec un motif.

Comme la conduite (`discipline.py`), seule la correction est gardée : sans ligne, la cote suit les
notes. Les pourcentages viennent du bulletin de la classe, déjà calculé : aucun calcul de plus.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.academics import report_cards
from apps.academics.models import ApplicationGrade
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.schools.models import ClassGroup, Term
from apps.students.models import Enrollment

# Du plus haut au plus bas : (pourcentage minimal, cote). Mêmes seuils que les mentions du
# bulletin (`report_cards.MENTIONS`, à confirmer par l'école, `07` I15). Sous le dernier : MA.
PROPOSALS = ((80, "TB"), (70, "B"), (60, "AB"), (50, "ME"))
LOWEST = "MA"
GRADES = ("TB", "B", "AB", "ME", "MA")

BAD_GRADE = ApiError("bad_grade", _("This is not an application grade."), 400)
REASON_REQUIRED = ApiError("reason_required", _("Say why the grade is corrected."), 400)
BAD_TERM = ApiError(
    "bad_term",
    _("An application grade is given for a period of this school year, not for a semester."),
    400,
)


def proposal(percent: Decimal | None) -> str:
    """Cote d'après le pourcentage de la période ; vide si la période n'a pas encore de note."""
    if percent is None:
        return ""
    return next((grade for floor, grade in PROPOSALS if percent >= floor), LOWEST)


@dataclass
class TermApplication:
    term: Term
    percent: Decimal | None
    proposed: str
    grade: str
    override: ApplicationGrade | None = None


def _periods(report: report_cards.ClassReport) -> list[Term]:
    return [c.term for c in report.columns if c.kind == "leaf" and c.term.kind == Term.Kind.PERIOD]


def _overrides(enrollment_ids) -> dict:
    rows = ApplicationGrade.objects.filter(enrollment__in=enrollment_ids).select_related(
        "corrected_by"
    )
    return {(o.enrollment_id, o.term_id): o for o in rows}


def class_overview(report: report_cards.ClassReport) -> list[tuple]:
    """Pour chaque élève de la classe : (inscription, [TermApplication par période]). Une requête
    pour les corrections de toute la classe."""
    terms = _periods(report)
    overrides = _overrides([s.enrollment.pk for s in report.students])
    result = []
    for student in report.students:
        rows = []
        for term in terms:
            total = student.totals.get(str(term.pk))
            percent = total.percent if total else None
            proposed = proposal(percent)
            override = overrides.get((student.enrollment.pk, term.pk))
            rows.append(
                TermApplication(
                    term, percent, proposed, override.grade if override else proposed, override
                )
            )
        result.append((student.enrollment, rows))
    return result


def grades_of_report(report: report_cards.ClassReport) -> dict:
    """Cote retenue pour le bulletin : {(inscription, période): cote} ; vide sans note."""
    return {
        (enrollment.pk, row.term.pk): row.grade
        for enrollment, rows in class_overview(report)
        for row in rows
    }


def may_correct(user: User, permissions, group: ClassGroup) -> bool:
    """Le titulaire ou le cotitulaire de la classe (NB.7), ou qui entre les notes de toutes les
    classes."""
    return group.is_homeroom_of(user) or "grades.enter_any" in permissions


def _retained(enrollment: Enrollment, term: Term) -> str:
    report = report_cards.class_report(enrollment.class_group)
    for found, rows in class_overview(report):
        if found.pk == enrollment.pk:
            return next((r.grade for r in rows if r.term.pk == term.pk), "")
    return ""


def override_grade(
    enrollment: Enrollment, term: Term, *, actor: User, grade: str, reason: str
) -> ApplicationGrade:
    """Corrige la cote de la période (motif obligatoire) ; une seconde correction remplace la
    première, le journal garde les deux."""
    reason = reason.strip()
    if grade not in GRADES:
        raise BusinessError(BAD_GRADE)
    if not reason:
        raise BusinessError(REASON_REQUIRED)
    if term.kind != Term.Kind.PERIOD or term.academic_year_id != enrollment.academic_year_id:
        raise BusinessError(BAD_TERM)
    with transaction.atomic():
        before = _retained(enrollment, term)
        row, _created = ApplicationGrade.objects.update_or_create(
            enrollment=enrollment,
            term=term,
            defaults={"grade": grade, "reason": reason, "corrected_by": actor},
        )
        audit.record(
            Action.APPLICATION_GRADE_OVERRIDDEN,
            row,
            actor=actor,
            before={"grade": before},
            after={"grade": grade, "reason": reason, "term": str(term)},
            label=f"{enrollment.student.full_name} · {term}",
        )
    return row


def clear_override(enrollment: Enrollment, term: Term, *, actor: User) -> None:
    """Reprend la cote proposée ; le journal garde la correction retirée."""
    with transaction.atomic():
        row = ApplicationGrade.objects.filter(enrollment=enrollment, term=term).first()
        if row is None:
            return
        before = {"grade": row.grade, "reason": row.reason}
        row.delete()
        audit.record(
            Action.APPLICATION_GRADE_OVERRIDDEN,
            None,
            actor=actor,
            before=before,
            after={"grade": _retained(enrollment, term), "term": str(term)},
            label=f"{enrollment.student.full_name} · {term}",
        )

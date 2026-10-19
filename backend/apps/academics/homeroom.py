"""Espace du titulaire (NB.3) : pour sa classe et une période (ou les examens), les fiches de cotes
reçues (état, moyenne d'un cours une fois sa fiche envoyée), la vérification élève par élève
(total, %, place, conduite, application) et les chiffres de la classe une fois toutes les fiches
validées, puis « Bulletins prêts ».

Rien n'est recopié : tout vient du bulletin de la classe (`report_cards.class_report`) et du
tableau du directeur des études (`board`). Les notes d'une fiche pas encore envoyée restent à
l'enseignant (NB.1) : ni moyenne du cours, ni total d'élève avant que la classe soit complète.
Droit : être le titulaire de la classe (vérifié par l'API).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics import application, board, discipline, report_cards
from apps.academics.grades import NOT_GRADED_HERE, term_label
from apps.academics.models import ReportCardsReady
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.notifications import events
from apps.schools import pass_rules
from apps.schools.models import ClassGroup, Term
from apps.schools.organisation import current_year

SHEETS_MISSING = ApiError(
    "sheets_missing",
    _("Every grade sheet of this period must be validated before the report cards are ready."),
    409,
)


@dataclass
class CourseRow:
    course: board.BoardCourse
    average: Decimal | None = None
    below_half: int | None = None


@dataclass
class StudentRow:
    enrollment_id: UUID
    number: int
    full_name: str
    total: report_cards.Total
    conduct: str
    application: str


@dataclass
class Stats:
    students: int
    graded: int
    average: Decimal | None
    highest: Decimal | None
    lowest: Decimal | None
    at_least_half: int


@dataclass
class Space:
    class_group: ClassGroup
    term: Term
    courses: list[CourseRow]
    complete: bool
    ready_at: datetime | None
    ready_by: str
    students: list[StudentRow] = field(default_factory=list)
    stats: Stats | None = None


def homeroom_classes(user: User) -> list[ClassGroup]:
    """Classes de l'année en cours dont le compte est le titulaire."""
    year = current_year()
    if year is None:
        return []
    return list(
        ClassGroup.objects.filter(academic_year=year, homeroom_teacher=user)
        .select_related("academic_year", "level", "track")
        .order_by("level__order", "level__name", "track__name", "section")
    )


def check_term(group: ClassGroup, term: Term) -> None:
    if term.kind not in (Term.Kind.PERIOD, Term.Kind.EXAM) or (
        term.academic_year_id != group.academic_year_id
    ):
        raise BusinessError(NOT_GRADED_HERE)


def _percent(score: Decimal, maximum: int) -> Decimal:
    return (score * 100 / maximum).quantize(report_cards.PERCENT_STEP, rounding=ROUND_HALF_UP)


def _course_stats(
    row: CourseRow, report: report_cards.ClassReport, key: str, threshold: int
) -> None:
    cells = [s.cells[row.course.id][key] for s in report.students if row.course.id in s.cells]
    scores = [cell.score for cell in cells if cell.score is not None]
    maximum = cells[0].maximum if cells else 0
    if scores and maximum:
        row.average = _percent(sum(scores, Decimal(0)) / len(scores), maximum)
        # Sous le seuil d'un cours des règles de délibération (NB.4).
        row.below_half = sum(1 for score in scores if score * 100 < threshold * maximum)


def _mean(values: list[Decimal]) -> Decimal:
    mean = sum(values, Decimal(0)) / len(values)
    return mean.quantize(report_cards.PERCENT_STEP, rounding=ROUND_HALF_UP)


def space(group: ClassGroup, term: Term) -> Space:
    """La classe dans la période : fiches, et une fois complète, élèves et chiffres."""
    check_term(group, term)
    entry = next(iter(board.board(term, group)), None)
    courses = [CourseRow(course) for course in (entry.courses if entry else [])]
    complete = bool(entry and entry.complete)
    result = Space(
        group,
        term,
        courses,
        complete,
        entry.ready_at if entry else None,
        entry.ready_by if entry else "",
    )
    sent = [row for row in courses if row.course.status in (board.SUBMITTED, board.VALIDATED)]
    if not sent:
        return result
    report = report_cards.class_report(group)
    rules = pass_rules.class_rules(group.school.settings, group.level.pass_rules)
    key = str(term.pk)
    for row in sent:
        _course_stats(row, report, key, rules["course_pass_percent"])
    if not complete:
        return result
    ids = [s.enrollment.pk for s in report.students]
    period = term.kind == Term.Kind.PERIOD
    conduct = discipline.grades_of_class(ids, [term]) if period else {}
    applied = application.grades_of_report(report) if period else {}
    for number, student in enumerate(report.students, start=1):
        enrollment = student.enrollment
        result.students.append(
            StudentRow(
                enrollment.pk,
                number,
                enrollment.student.full_name,
                student.totals[key],
                conduct.get((enrollment.pk, term.pk), ""),
                applied.get((enrollment.pk, term.pk), ""),
            )
        )
    percents = [row.total.percent for row in result.students if row.total.percent is not None]
    result.stats = Stats(
        len(result.students),
        len(percents),
        _mean(percents) if percents else None,
        max(percents, default=None),
        min(percents, default=None),
        sum(1 for percent in percents if percent >= rules["pass_percent"]),
    )
    return result


def _label(group: ClassGroup, term: Term) -> str:
    return f"{group.name} · {term_label(term)}"


def declare_ready(group: ClassGroup, term: Term, *, actor: User) -> None:
    """Le titulaire déclare les bulletins de la période prêts : 409 `sheets_missing` tant qu'une
    fiche n'est pas validée ; déjà prêts : rien de plus. Journal, et notification à ceux qui
    valident les notes."""
    check_term(group, term)
    with transaction.atomic():
        # Deux clics en même temps : le second attend le premier et trouve la classe prête.
        list(ClassGroup.objects.select_for_update(of=("self",)).filter(pk=group.pk).values("pk"))
        entry = next(iter(board.board(term, group)), None)
        if entry is None or not entry.complete:
            raise BusinessError(SHEETS_MISSING)
        if entry.ready_at:
            return
        ReportCardsReady.objects.update_or_create(
            class_group=group,
            term=term,
            defaults={"declared_by": actor, "declared_at": timezone.now()},
        )
        audit.record(
            Action.GRADES_REPORT_CARDS_READY,
            group,
            actor=actor,
            after={"term": str(term.pk)},
            label=_label(group, term),
        )
        events.report_cards_ready(group, term, actor=actor)


def withdraw_ready(group: ClassGroup, term: Term, *, actor: User) -> None:
    """Le titulaire reprend sa déclaration (une erreur vue après coup) ; au journal."""
    check_term(group, term)
    deleted, _rows = ReportCardsReady.objects.filter(class_group=group, term=term).delete()
    if deleted:
        audit.record(
            Action.GRADES_REPORT_CARDS_WITHDRAWN,
            group,
            actor=actor,
            before={"term": str(term.pk)},
            label=_label(group, term),
        )

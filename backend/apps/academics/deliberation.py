"""Délibération d'une classe (8.4.2) : pour chaque élève, la décision proposée par le système
(issue de `resits.py`, d'après les notes et les règles) puis la décision prise. Quand elles
diffèrent, l'écart est signalé : motif obligatoire, compté à part. La proclamation fige les
résultats dans un `DeliberationSnapshot` ; les corriger demande de rouvrir la classe (motif), et la
proclamation suivante crée la version suivante.

La proposition n'est jamais stockée comme vérité : elle suit les notes (recalculée à la lecture).
La ligne d'un élève garde seulement celle qu'il y avait quand la décision a été prise.

Reprise (8.4.7) : un élève sans aucune note cette année (année passée créée à l'arrivée, année
tenue sur papier) reçoit, avec sa décision, le pourcentage obtenu hors de Mwangaza ; il compte
comme un pourcentage calculé (situations, passage de classe), jamais à la place de l'un d'eux.

Sessions (NB.5) : le conseil délibère aussi à chaque période et chaque semestre (`term`). Rien à y
décider par élève : il confirme les pourcentages, les places, la conduite et l'application, qui
sont figés à la proclamation ; elle demande les bulletins dits prêts par le titulaire (NB.3). La
fin d'année (`term` vide) reste seule lue par le bulletin, les situations et le passage de classe.

Seconde session (NB.6, `second=True`) : les élèves que la dernière proclamation de fin d'année
envoie au repêchage ; ils gardent leur pourcentage, la proposition suit leurs notes de repêchage.
Décision finale (jamais un nouveau repêchage), conseil, proclamation et procès-verbal comme la fin
d'année. `year_results` lit les deux : la ligne de seconde session remplace celle du repêchage.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics import application, board, council, discipline, report_cards, resits
from apps.academics.models import Deliberation, DeliberationDecision, DeliberationSnapshot
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.schools import pass_rules
from apps.schools.models import ClassGroup, Term
from apps.students.models import Enrollment

Decision = DeliberationDecision.Decision
# Issue proposée (resits.py) → décision proposée. Sans note ou notes incomplètes : pas de
# proposition, la délibération décide (abandon, dossier à compléter…).
PROPOSAL = {
    resits.PASSED: Decision.PASS,
    resits.RESIT: Decision.RESIT,
    resits.FAILED: Decision.REPEAT,
    resits.ORIENT: Decision.ORIENT,
    resits.EXCLUDE: Decision.EXCLUDE,
}

CLOSED = ApiError("deliberation_closed", _("The results are proclaimed: reopen them first."), 400)
NOT_PROCLAIMED = ApiError("not_proclaimed", _("The results are not proclaimed."), 400)
BAD_DECISION = ApiError("bad_decision", _("This is not a deliberation decision."), 400)
REASON_REQUIRED = ApiError(
    "reason_required", _("Say why the decision differs from the proposal."), 400
)
NOT_IN_CLASS = ApiError("not_in_class", _("This student is not in this class."), 400)
DATE_REQUIRED = ApiError("date_required", _("Set the deliberation date first."), 400)
UNDECIDED = ApiError(
    "undecided", _("Every student needs a decision before the results are proclaimed."), 400
)
CORRECTION_REASON = ApiError("correction_reason", _("Say why the results are corrected."), 400)
HAS_GRADES = ApiError(
    "has_grades",
    _("This student has grades: the percentage is calculated from them."),
    400,
)
BAD_PERCENT = ApiError("bad_percent", _("A percentage is a number from 0 to 100."), 400)
NOT_A_SESSION = ApiError(
    "not_a_session", _("The council deliberates on a period, a semester or the year."), 400
)
NOT_READY = ApiError(
    "report_cards_not_ready",
    _("The homeroom teacher has not declared the report cards of this session ready."),
    400,
)
NO_SECOND_SESSION = ApiError(
    "no_second_session", _("No student of this class was sent to the second session."), 400
)
NOT_IN_SECOND_SESSION = ApiError(
    "not_in_second_session", _("This student is not in the second session."), 400
)
RESIT_AGAIN = ApiError(
    "resit_again", _("The second session gives a final decision: no new resit exam."), 400
)
EXAM_DATE_REQUIRED = ApiError("exam_date_required", _("Set the date of the resit exam first."), 400)
SESSIONS = (Term.Kind.PERIOD, *Term.GROUPS)


@dataclass
class StudentRow:
    enrollment: Enrollment
    percent: object
    outcome: str
    proposed: str
    decision: str
    reason: str
    resit_courses: list[str]
    rule: str = ""
    rule_params: dict = field(default_factory=dict)
    # Seconde session : chaque cours repassé (pourcentage de l'année, note de repêchage, réussi).
    resits: list[dict] = field(default_factory=list)

    @property
    def deviates(self) -> bool:
        return bool(self.decision and self.proposed and self.decision != self.proposed)


@dataclass
class ClassDeliberation:
    deliberation: Deliberation | None
    rows: list[StudentRow]
    latest: DeliberationSnapshot | None

    @property
    def status(self) -> str:
        return self.deliberation.status if self.deliberation else Deliberation.Status.DRAFT

    @property
    def counts(self) -> dict[str, int]:
        return dict(Counter(r.decision for r in self.rows if r.decision))

    @property
    def deviations(self) -> int:
        return sum(r.deviates for r in self.rows)


def _resit_lines(student: resits.StudentResits, rules: dict) -> list[dict]:
    return [
        {
            "course": row.course.name,
            "percent": str(row.percent),
            "resit_percent": str(row.resit.percent) if row.resit else None,
            "passed": row.passed(rules),
        }
        for row in student.failed
        if row.eligible
    ]


def overview(group: ClassGroup, *, second: bool = False) -> ClassDeliberation:
    """Tableau de la classe : proposition recalculée, décision prise, écart. Une lecture du
    bulletin de la classe, une pour les décisions. `second` : seconde session, les élèves
    envoyés au repêchage seulement."""
    deliberation = Deliberation.objects.filter(
        class_group=group, term__isnull=True, second_session=second
    ).first()
    decided = {}
    latest = None
    if deliberation:
        decided = {d.enrollment_id: d for d in deliberation.decisions.all()}
        latest = deliberation.snapshots.order_by("-version").first()
    sent = (resits.proclaimed_resits(group) or set()) if second else None
    students = resits.class_overview(report_cards.class_report(group), resit_decided=sent)
    rules = resits.rules_of(group) if second else {}
    rows = []
    for student in students:
        if second and student.enrollment.pk not in sent:
            continue
        found = decided.get(student.enrollment.pk)
        percent = student.percent
        if student.outcome == resits.UNRANKED and found and found.prior_percent is not None:
            percent = found.prior_percent
        proposed = PROPOSAL.get(student.outcome, "")
        if second and proposed == Decision.RESIT:
            proposed = ""
        rows.append(
            StudentRow(
                student.enrollment,
                percent,
                student.outcome,
                proposed,
                found.decision if found else "",
                found.reason if found else "",
                [f.course.name for f in student.failed if f.eligible],
                student.rule,
                student.params,
                _resit_lines(student, rules) if second else [],
            )
        )
    return ClassDeliberation(deliberation, rows, latest)


def _get_or_create(
    group: ClassGroup, term: Term | None = None, *, second: bool = False
) -> Deliberation:
    deliberation, _created = Deliberation.objects.get_or_create(
        class_group=group, term=term, second_session=second
    )
    return deliberation


def check_session(group: ClassGroup, term: Term | None, *, second: bool = False) -> None:
    """Une période, un semestre ou un trimestre de l'année de la classe ; `None` : fin d'année.
    Seconde session : des élèves envoyés au repêchage par la proclamation de fin d'année."""
    if second:
        if term is not None or not resits.proclaimed_resits(group):
            raise BusinessError(NO_SECOND_SESSION)
        return
    if term is not None and (
        term.kind not in SESSIONS or term.academic_year_id != group.academic_year_id
    ):
        raise BusinessError(NOT_A_SESSION)


@dataclass
class SessionRow:
    enrollment: Enrollment
    total: report_cards.Total
    conduct: str
    application: str
    passed: bool


@dataclass
class SessionDeliberation:
    """Une période ou un semestre de la classe : résultats de chaque élève et état."""

    deliberation: Deliberation | None
    rows: list[SessionRow]
    latest: DeliberationSnapshot | None
    ready: bool
    pass_percent: int

    @property
    def status(self) -> str:
        return self.deliberation.status if self.deliberation else Deliberation.Status.DRAFT


def _leaves(term: Term) -> list[Term]:
    if term.kind == Term.Kind.PERIOD:
        return [term]
    return list(term.children.filter(kind__in=(Term.Kind.PERIOD, Term.Kind.EXAM)))


def is_ready(group: ClassGroup, term: Term) -> bool:
    """Bulletins dits prêts par le titulaire pour la période, ou pour chaque période et examen
    du semestre (une session sans cours noté n'en demande pas)."""
    for leaf in _leaves(term):
        entry = next(iter(board.board(leaf, group)), None)
        if entry is not None and not entry.ready_at:
            return False
    return True


def session_overview(group: ClassGroup, term: Term) -> SessionDeliberation:
    """Résultats de la session : pourcentage, place, conduite et application (périodes)."""
    check_session(group, term)
    deliberation = Deliberation.objects.filter(class_group=group, term=term).first()
    latest = deliberation.snapshots.order_by("-version").first() if deliberation else None
    report = report_cards.class_report(group)
    key = str(term.pk)
    ids = [s.enrollment.pk for s in report.students]
    period = term.kind == Term.Kind.PERIOD
    conduct = discipline.grades_of_class(ids, [term]) if period else {}
    applied = application.grades_of_report(report) if period else {}
    threshold = pass_rules.class_rules(group.school.settings, group.level.pass_rules)[
        "pass_percent"
    ]
    rows = []
    for student in report.students:
        total = student.totals.get(key) or report_cards.Total(None, 0, None, None, None)
        pk = student.enrollment.pk
        rows.append(
            SessionRow(
                student.enrollment,
                total,
                conduct.get((pk, term.pk), ""),
                applied.get((pk, term.pk), ""),
                total.percent is not None and total.percent >= threshold,
            )
        )
    return SessionDeliberation(deliberation, rows, latest, is_ready(group, term), threshold)


def session_of(
    group: ClassGroup, term: Term | None, *, second: bool = False
) -> Deliberation | None:
    return Deliberation.objects.filter(class_group=group, term=term, second_session=second).first()


def sessions(group: ClassGroup) -> list[Deliberation]:
    """Les délibérations de la classe, toutes sessions : état et version de chacune."""
    return list(Deliberation.objects.filter(class_group=group))


def _open(deliberation: Deliberation) -> None:
    if deliberation.status == Deliberation.Status.PROCLAIMED:
        raise BusinessError(CLOSED)


def open_session(group: ClassGroup, term: Term | None, *, second: bool = False) -> Deliberation:
    """La délibération de la session, créée au besoin, refusée si elle est proclamée."""
    check_session(group, term, second=second)
    deliberation = _get_or_create(group, term, second=second)
    _open(deliberation)
    return deliberation


def set_date(
    group: ClassGroup,
    held_on: date,
    *,
    actor: User,
    term: Term | None = None,
    second: bool = False,
) -> Deliberation:
    check_session(group, term, second=second)
    with transaction.atomic():
        deliberation = _get_or_create(group, term, second=second)
        _open(deliberation)
        before = deliberation.held_on
        deliberation.held_on = held_on
        deliberation.save(update_fields=["held_on", "updated_at"])
        audit.record(
            Action.DELIBERATION_DECIDED,
            deliberation,
            actor=actor,
            before={"held_on": str(before)} if before else None,
            after={"held_on": str(held_on)},
            label=group.name,
        )
    return deliberation


def set_exam_date(group: ClassGroup, exam_on: date, *, actor: User) -> Deliberation:
    """Date de l'examen de repêchage (seconde session), imprimée sur les convocations."""
    check_session(group, None, second=True)
    with transaction.atomic():
        deliberation = _get_or_create(group, second=True)
        _open(deliberation)
        before = deliberation.exam_on
        deliberation.exam_on = exam_on
        deliberation.save(update_fields=["exam_on", "updated_at"])
        audit.record(
            Action.DELIBERATION_DECIDED,
            deliberation,
            actor=actor,
            before={"exam_on": str(before)} if before else None,
            after={"exam_on": str(exam_on)},
            label=group.name,
        )
    return deliberation


def convocations(group: ClassGroup) -> tuple[date, list[StudentRow]]:
    """Date de l'examen de repêchage et élèves convoqués, avec les cours à repasser."""
    check_session(group, None, second=True)
    current = session_of(group, None, second=True)
    if current is None or current.exam_on is None:
        raise BusinessError(EXAM_DATE_REQUIRED)
    return current.exam_on, overview(group, second=True).rows


def prior_percent(value) -> Decimal | None:
    """Pourcentage repris, au dixième, de 0 à 100 ; `None` : aucun."""
    if value is None:
        return None
    percent = Decimal(value).quantize(resits.STEP)
    if not Decimal(0) <= percent <= Decimal(100):
        raise BusinessError(BAD_PERCENT)
    return percent


def decide(
    enrollment: Enrollment,
    decision: str,
    reason: str,
    *,
    actor: User,
    percent: Decimal | None = None,
    second: bool = False,
) -> DeliberationDecision:
    """Décision prise pour un élève. Un écart avec la proposition demande un motif. `percent` :
    pourcentage repris d'un élève sans aucune note cette année (8.4.7), refusé sinon. `second` :
    seconde session, décision finale."""
    if decision not in Decision.values:
        raise BusinessError(BAD_DECISION)
    if second and decision == Decision.RESIT:
        raise BusinessError(RESIT_AGAIN)
    percent = prior_percent(percent)
    group = enrollment.class_group
    reason = reason.strip()
    if second:
        check_session(group, None, second=True)
    with transaction.atomic():
        deliberation = _get_or_create(group, second=second)
        _open(deliberation)
        rows = overview(group, second=second).rows
        row = next((r for r in rows if r.enrollment.pk == enrollment.pk), None)
        if row is None:
            raise BusinessError(NOT_IN_SECOND_SESSION if second else NOT_IN_CLASS)
        if row.proposed and decision != row.proposed and not reason:
            raise BusinessError(REASON_REQUIRED)
        if percent is not None and row.outcome != resits.UNRANKED:
            raise BusinessError(HAS_GRADES)
        before = DeliberationDecision.objects.filter(
            deliberation=deliberation, enrollment=enrollment
        ).first()
        saved, _created = DeliberationDecision.objects.update_or_create(
            deliberation=deliberation,
            enrollment=enrollment,
            defaults={
                "decision": decision,
                "proposed": row.proposed,
                "reason": reason,
                "prior_percent": percent,
            },
        )
        after = {"decision": decision, "proposed": row.proposed, "reason": reason}
        if percent is not None or (before and before.prior_percent is not None):
            after["prior_percent"] = str(percent) if percent is not None else None
        audit.record(
            Action.DELIBERATION_DECIDED,
            saved,
            actor=actor,
            before=_logged(before) if before else None,
            after=after,
            label=f"{enrollment.student.full_name} · {group.name}",
        )
    return saved


def _logged(decision: DeliberationDecision) -> dict:
    logged = {"decision": decision.decision, "reason": decision.reason}
    if decision.prior_percent is not None:
        logged["prior_percent"] = str(decision.prior_percent)
    return logged


def apply_proposals(group: ClassGroup, *, actor: User, second: bool = False) -> int:
    """Reprend la proposition du système pour chaque élève qui en a une et pas encore de
    décision. Retourne le nombre d'élèves décidés."""
    if second:
        check_session(group, None, second=True)
    with transaction.atomic():
        deliberation = _get_or_create(group, second=second)
        _open(deliberation)
        todo = [r for r in overview(group, second=second).rows if r.proposed and not r.decision]
        DeliberationDecision.objects.bulk_create(
            DeliberationDecision(
                deliberation=deliberation,
                enrollment=r.enrollment,
                decision=r.proposed,
                proposed=r.proposed,
            )
            for r in todo
        )
        if todo:
            audit.record(
                Action.DELIBERATION_DECIDED,
                deliberation,
                actor=actor,
                after={"proposals_applied": len(todo)},
                label=group.name,
            )
    return len(todo)


@dataclass
class YearResult:
    """Résultats proclamés de fin d'année d'une classe : dernière version de la fin d'année, avec
    par-dessus la dernière version de la seconde session pour les élèves qu'elle envoyait au
    repêchage. `rows` : lignes figées par inscription (texte)."""

    snapshot: DeliberationSnapshot
    second: DeliberationSnapshot | None
    rows: dict[str, dict]

    @property
    def held_on(self) -> date:
        return self.second.held_on if self.second else self.snapshot.held_on

    @property
    def version(self) -> int:
        return self.snapshot.version

    @property
    def lines(self) -> list[dict]:
        return list(self.rows.values())

    def date_of(self, row: dict) -> date:
        return self.second.held_on if row.get("second_session") else self.snapshot.held_on


def year_results(groups) -> dict[UUID, YearResult]:
    """Résultats de fin d'année de chaque classe proclamée, en une requête : seuls ce que le
    bulletin, les situations et le passage de classe lisent, jamais un brouillon."""
    first, second = {}, {}
    for snapshot in (
        DeliberationSnapshot.objects.filter(
            deliberation__class_group__in=groups, deliberation__term__isnull=True
        )
        .annotate(
            group_id=F("deliberation__class_group_id"), later=F("deliberation__second_session")
        )
        .order_by("deliberation__class_group_id", "deliberation__second_session", "-version")
        .distinct("deliberation__class_group_id", "deliberation__second_session")
    ):
        (second if snapshot.later else first)[snapshot.group_id] = snapshot
    results = {}
    for group_id, snapshot in first.items():
        rows = {row["enrollment"]: row for row in snapshot.rows}
        later = second.get(group_id)
        for row in later.rows if later else ():
            if rows.get(row["enrollment"], {}).get("decision") == Decision.RESIT:
                rows[row["enrollment"]] = row
        results[group_id] = YearResult(snapshot, later, rows)
    return results


def proclaimed_rows(group: ClassGroup) -> YearResult | None:
    """Résultats proclamés de la classe (`year_results`) ; `None` avant la proclamation."""
    return year_results([group]).get(group.pk)


def _frozen(row: StudentRow, second: bool = False) -> dict:
    if second:
        return {**_frozen(row), "second_session": True, "resits": row.resits}
    return {
        "enrollment": str(row.enrollment.pk),
        "student": row.enrollment.student.full_name,
        "percent": str(row.percent) if row.percent is not None else None,
        "outcome": row.outcome,
        "proposed": row.proposed,
        "decision": row.decision,
        "reason": row.reason,
        "deviates": row.deviates,
        "resit_courses": row.resit_courses,
        "rule": row.rule,
        "rule_params": row.rule_params,
    }


def _session_frozen(row: SessionRow) -> dict:
    total = row.total
    return {
        "enrollment": str(row.enrollment.pk),
        "student": row.enrollment.student.full_name,
        "percent": str(total.percent) if total.percent is not None else None,
        "place": total.place,
        "conduct": row.conduct,
        "application": row.application,
        "passed": row.passed,
    }


def _year_rows(group: ClassGroup, second: bool = False) -> tuple[list[dict], int]:
    rows = overview(group, second=second).rows
    if any(not r.decision for r in rows):
        raise BusinessError(UNDECIDED)
    # La proposition a pu changer depuis la décision (notes corrigées) : l'écart se juge sur
    # la proposition d'aujourd'hui.
    if any(r.deviates and not r.reason for r in rows):
        raise BusinessError(REASON_REQUIRED)
    return [_frozen(r, second) for r in rows], sum(r.deviates for r in rows)


def proclaim(
    group: ClassGroup, *, actor: User, term: Term | None = None, second: bool = False
) -> DeliberationSnapshot:
    """Proclame les résultats de la session. Fin d'année : date posée, chaque élève décidé,
    chaque écart motivé ; de même la seconde session, pour ses élèves. Période ou semestre : date
    posée, bulletins dits prêts. Fige les résultats et le conseil (version suivante, avec le motif
    donné à la réouverture)."""
    check_session(group, term, second=second)
    with transaction.atomic():
        deliberation = _get_or_create(group, term, second=second)
        _open(deliberation)
        if deliberation.held_on is None:
            raise BusinessError(DATE_REQUIRED)
        if term is None:
            frozen_rows, deviations = _year_rows(group, second)
        else:
            if not is_ready(group, term):
                raise BusinessError(NOT_READY)
            frozen_rows = [_session_frozen(r) for r in session_overview(group, term).rows]
            deviations = 0
        now = timezone.now()
        deliberation.version += 1
        deliberation.status = Deliberation.Status.PROCLAIMED
        reason, deliberation.correction_reason = deliberation.correction_reason, ""
        deliberation.save(update_fields=["version", "status", "correction_reason", "updated_at"])
        snapshot = DeliberationSnapshot.objects.create(
            deliberation=deliberation,
            version=deliberation.version,
            held_on=deliberation.held_on,
            proclaimed_at=now,
            proclaimed_by=actor,
            reason=reason,
            rows=frozen_rows,
            council=council.frozen(deliberation),
        )
        audit.record(
            Action.DELIBERATION_PROCLAIMED,
            snapshot,
            actor=actor,
            after={
                "term": str(term.pk) if term else None,
                "second_session": second,
                "version": deliberation.version,
                "students": len(frozen_rows),
                "deviations": deviations,
                "reason": snapshot.reason,
            },
            label=f"{group.name} · v{deliberation.version}",
        )
    return snapshot


def reopen(
    group: ClassGroup,
    reason: str,
    *,
    actor: User,
    term: Term | None = None,
    second: bool = False,
) -> Deliberation:
    """Rouvre une session proclamée pour corriger : motif obligatoire. Les résultats figés
    restent lus par le bulletin jusqu'à la proclamation suivante."""
    check_session(group, term, second=second)
    reason = reason.strip()
    if not reason:
        raise BusinessError(CORRECTION_REASON)
    with transaction.atomic():
        deliberation = _get_or_create(group, term, second=second)
        if deliberation.status != Deliberation.Status.PROCLAIMED:
            raise BusinessError(NOT_PROCLAIMED)
        deliberation.status = Deliberation.Status.DRAFT
        deliberation.correction_reason = reason
        deliberation.save(update_fields=["status", "correction_reason", "updated_at"])
        audit.record(
            Action.DELIBERATION_REOPENED,
            deliberation,
            actor=actor,
            after={"version": deliberation.version, "reason": reason},
            label=f"{group.name} · v{deliberation.version}",
        )
    return deliberation

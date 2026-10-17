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
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics import report_cards, resits
from apps.academics.models import Deliberation, DeliberationDecision, DeliberationSnapshot
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.schools.models import ClassGroup
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
    _("This student has grades in Mwangaza: the percentage is calculated from them."),
    400,
)
BAD_PERCENT = ApiError("bad_percent", _("A percentage is a number from 0 to 100."), 400)


@dataclass
class StudentRow:
    enrollment: Enrollment
    percent: object
    outcome: str
    proposed: str
    decision: str
    reason: str
    resit_courses: list[str]

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


def overview(group: ClassGroup) -> ClassDeliberation:
    """Tableau de la classe : proposition recalculée, décision prise, écart. Une lecture du
    bulletin de la classe, une pour les décisions."""
    deliberation = Deliberation.objects.filter(class_group=group).first()
    decided = {}
    latest = None
    if deliberation:
        decided = {d.enrollment_id: d for d in deliberation.decisions.all()}
        latest = deliberation.snapshots.order_by("-version").first()
    students = resits.class_overview(report_cards.class_report(group))
    rows = []
    for student in students:
        found = decided.get(student.enrollment.pk)
        percent = student.percent
        if student.outcome == resits.UNRANKED and found and found.prior_percent is not None:
            percent = found.prior_percent
        rows.append(
            StudentRow(
                student.enrollment,
                percent,
                student.outcome,
                PROPOSAL.get(student.outcome, ""),
                found.decision if found else "",
                found.reason if found else "",
                [f.course.name for f in student.failed if f.eligible],
            )
        )
    return ClassDeliberation(deliberation, rows, latest)


def _get_or_create(group: ClassGroup) -> Deliberation:
    deliberation, _created = Deliberation.objects.get_or_create(class_group=group)
    return deliberation


def _open(deliberation: Deliberation) -> None:
    if deliberation.status == Deliberation.Status.PROCLAIMED:
        raise BusinessError(CLOSED)


def set_date(group: ClassGroup, held_on: date, *, actor: User) -> Deliberation:
    with transaction.atomic():
        deliberation = _get_or_create(group)
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
) -> DeliberationDecision:
    """Décision prise pour un élève. Un écart avec la proposition demande un motif. `percent` :
    pourcentage repris d'un élève sans aucune note cette année (8.4.7), refusé sinon."""
    if decision not in Decision.values:
        raise BusinessError(BAD_DECISION)
    percent = prior_percent(percent)
    group = enrollment.class_group
    reason = reason.strip()
    with transaction.atomic():
        deliberation = _get_or_create(group)
        _open(deliberation)
        row = next((r for r in overview(group).rows if r.enrollment.pk == enrollment.pk), None)
        if row is None:
            raise BusinessError(NOT_IN_CLASS)
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


def apply_proposals(group: ClassGroup, *, actor: User) -> int:
    """Reprend la proposition du système pour chaque élève qui en a une et pas encore de
    décision. Retourne le nombre d'élèves décidés."""
    with transaction.atomic():
        deliberation = _get_or_create(group)
        _open(deliberation)
        todo = [r for r in overview(group).rows if r.proposed and not r.decision]
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


def proclaimed_rows(group: ClassGroup) -> tuple[DeliberationSnapshot | None, dict[str, dict]]:
    """Dernière version figée de la classe et ses lignes par inscription (texte) : seul ce que le
    bulletin lit de la délibération, jamais le brouillon en cours."""
    snapshot = (
        DeliberationSnapshot.objects.filter(deliberation__class_group=group)
        .order_by("-version")
        .first()
    )
    return snapshot, {row["enrollment"]: row for row in snapshot.rows} if snapshot else {}


def _frozen(row: StudentRow) -> dict:
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
    }


def proclaim(group: ClassGroup, *, actor: User) -> DeliberationSnapshot:
    """Proclame les résultats : date posée, chaque élève décidé, chaque écart motivé. Fige les
    résultats (version suivante, avec le motif donné à la réouverture)."""
    with transaction.atomic():
        deliberation = _get_or_create(group)
        _open(deliberation)
        if deliberation.held_on is None:
            raise BusinessError(DATE_REQUIRED)
        rows = overview(group).rows
        if any(not r.decision for r in rows):
            raise BusinessError(UNDECIDED)
        # La proposition a pu changer depuis la décision (notes corrigées) : l'écart se juge sur
        # la proposition d'aujourd'hui.
        if any(r.deviates and not r.reason for r in rows):
            raise BusinessError(REASON_REQUIRED)
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
            rows=[_frozen(r) for r in rows],
        )
        audit.record(
            Action.DELIBERATION_PROCLAIMED,
            snapshot,
            actor=actor,
            after={
                "version": deliberation.version,
                "students": len(rows),
                "deviations": sum(r.deviates for r in rows),
                "reason": snapshot.reason,
            },
            label=f"{group.name} · v{deliberation.version}",
        )
    return snapshot


def reopen(group: ClassGroup, reason: str, *, actor: User) -> Deliberation:
    """Rouvre une classe proclamée pour corriger : motif obligatoire. Les résultats figés
    restent lus par le bulletin jusqu'à la proclamation suivante."""
    reason = reason.strip()
    if not reason:
        raise BusinessError(CORRECTION_REASON)
    with transaction.atomic():
        deliberation = _get_or_create(group)
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

"""Conduite et discipline, première moitié (8.5.1a) : liste des infractions avec leurs points,
seuils des cotes de conduite (TB, B, AB, ME, MA) et incidents des élèves.

Droits : `discipline.configure` (liste, seuils, annulation d'un incident), `discipline.record`
(attribuer une infraction : tout enseignant). Un incident garde les points de l'infraction à
l'instant où il est écrit ; il n'est jamais modifié ni effacé, seulement annulé (motif, auteur).
Chaque changement va dans le journal de l'école (domaine `discipline`). La cote d'une période
calculée d'après ces points, corrigeable avec motif (`discipline.override`, 8.5.1b), les parents
prévenus et la ligne du bulletin.
"""

from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone, translation
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.academics.models import (
    ConductGrade,
    ConductScale,
    DisciplineIncident,
    DisciplineRule,
    IncidentCancellation,
)
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.notifications import events
from apps.schools.models import Term
from apps.students.models import Enrollment

RULE_EXISTS = ApiError("rule_exists", _("This offence is already in the list."), 409)
RULES_NOT_EMPTY = ApiError(
    "rules_not_empty", _("The list already has offences: add the missing ones by hand."), 409
)
RULE_INACTIVE = ApiError("rule_inactive", _("This offence is no longer in the list."), 400)
ENROLLMENT_INACTIVE = ApiError(
    "enrollment_inactive", _("This student is no longer enrolled in this class."), 400
)
FUTURE_DATE = ApiError("future_date", _("The date cannot be in the future."), 400)
NO_TERM = ApiError(
    "no_term", _("No period matches this date: choose the period of the offence."), 400
)
BAD_TERM = ApiError("bad_term", _("This period does not belong to the student's school year."), 400)
ALREADY_CANCELLED = ApiError("already_cancelled", _("This offence is already cancelled."), 409)
BAD_GRADE = ApiError("bad_grade", _("This is not a conduct grade."), 400)
REASON_REQUIRED = ApiError("reason_required", _("Say why the grade is corrected."), 400)
BAD_TERM_GRADE = ApiError(
    "bad_term_grade",
    _("A conduct grade is given for a period, not for a semester or an exam."),
    400,
)
BAD_SCALE = ApiError(
    "bad_scale", _("The scale must start at 0 point and rise from one grade to the next."), 400
)

# Seuils de départ (`docs/04` § Conduite) : de 0 à 4 points TB, 5 à 9 B, 10 à 14 AB, 15 à 24 ME,
# 25 et plus MA.
DEFAULT_SCALE = (("TB", 0), ("B", 5), ("AB", 10), ("ME", 15), ("MA", 25))
GRADES = tuple(code for code, _minimum in DEFAULT_SCALE)

# Liste proposée aux écoles qui n'ont encore rien saisi (libellés et points modifiables).
DEFAULT_RULES = (
    (_("Late arrival"), 1),
    (_("Wearing the uniform incorrectly"), 1),
    (_("Disturbing the class"), 2),
    (_("Using a phone in class"), 3),
    (_("Leaving class without permission"), 3),
    (_("Skipping a class"), 4),
    (_("Insulting a classmate or a teacher"), 6),
    (_("Fighting"), 10),
    (_("Cheating during a test"), 10),
    (_("Damaging school property"), 10),
)


def _rule_row(rule: DisciplineRule) -> dict:
    return {"label": rule.label, "points": rule.points, "is_active": rule.is_active}


# Liste des infractions


def rules_of(*, only_active: bool = False):
    rules = DisciplineRule.objects.all()
    return rules.filter(is_active=True) if only_active else rules


def _check_label_free(label: str, *, exclude=None) -> None:
    taken = DisciplineRule.objects.filter(label__iexact=label)
    if exclude is not None:
        taken = taken.exclude(pk=exclude.pk)
    if taken.exists():
        raise BusinessError(RULE_EXISTS)


def create_rule(*, actor: User, label: str, points: int) -> DisciplineRule:
    label = label.strip()
    with transaction.atomic():
        _check_label_free(label)
        order = (
            DisciplineRule.objects.order_by("-order").values_list("order", flat=True).first() or 0
        ) + 1
        rule = DisciplineRule.objects.create(label=label, points=points, order=order)
        audit.record(Action.DISCIPLINE_RULE_CHANGED, rule, actor=actor, after=_rule_row(rule))
    return rule


def update_rule(rule: DisciplineRule, *, actor: User, **changes) -> DisciplineRule:
    """Libellé, points ou retrait de la liste (`is_active`) ; les incidents passés gardent leurs
    points."""
    if "label" in changes:
        changes["label"] = changes["label"].strip()
    before = _rule_row(rule)
    with transaction.atomic():
        if "label" in changes:
            _check_label_free(changes["label"], exclude=rule)
        for field, value in changes.items():
            setattr(rule, field, value)
        after = _rule_row(rule)
        if after != before:
            rule.save(update_fields=[*changes, "updated_at"])
            audit.record(
                Action.DISCIPLINE_RULE_CHANGED,
                rule,
                actor=actor,
                before={k: v for k, v in before.items() if after[k] != v},
                after={k: v for k, v in after.items() if before[k] != v},
            )
    return rule


def add_default_rules(*, actor: User) -> list[DisciplineRule]:
    """La liste proposée, dans la langue de l'école (celle de la plateforme) ; seulement tant que
    la liste est vide."""
    with transaction.atomic():
        if DisciplineRule.objects.exists():
            raise BusinessError(RULES_NOT_EMPTY)
        with translation.override(settings.LANGUAGE_CODE):
            rules = DisciplineRule.objects.bulk_create(
                DisciplineRule(label=gettext(label), points=points, order=order)
                for order, (label, points) in enumerate(DEFAULT_RULES, start=1)
            )
        audit.record(
            Action.DISCIPLINE_RULE_CHANGED,
            None,
            actor=actor,
            after={"rules": [_rule_row(rule) for rule in rules]},
            label=gettext("Proposed offence list"),
        )
    return rules


# Seuils des cotes


def scale_of() -> list[dict]:
    """Les cinq cotes avec leurs points minimum : ceux de l'école, sinon ceux de départ."""
    saved = dict(ConductScale.objects.values_list("grade", "min_points"))
    return [
        {"grade": code, "min_points": saved.get(code, minimum)} for code, minimum in DEFAULT_SCALE
    ]


def set_scale(minimums: dict[str, int], *, actor: User) -> list[dict]:
    """`minimums` : points minimum de chaque cote (les cinq). TB commence à 0, chaque cote
    commence plus haut que la précédente."""
    values = [minimums.get(code) for code in GRADES]
    if (
        None in values
        or values[0] != 0
        or any(later <= earlier for earlier, later in pairwise(values))
    ):
        raise BusinessError(BAD_SCALE)
    before = scale_of()
    with transaction.atomic():
        saved = {row.grade: row for row in ConductScale.objects.all()}
        for code, minimum in zip(GRADES, values, strict=True):
            if code in saved:
                if saved[code].min_points != minimum:
                    saved[code].min_points = minimum
                    saved[code].save(update_fields=["min_points", "updated_at"])
            else:
                ConductScale.objects.create(grade=code, min_points=minimum)
        after = scale_of()
        if after != before:
            audit.record(
                Action.DISCIPLINE_SCALE_CHANGED,
                None,
                actor=actor,
                before={"scale": before},
                after={"scale": after},
                label=gettext("Conduct scale"),
            )
    return after


def grade_for(points: int, scale: list[dict]) -> str:
    """Cote qui correspond à `points` : la plus haute dont le minimum est atteint."""
    grade = scale[0]["grade"]
    for row in scale:
        if points >= row["min_points"]:
            grade = row["grade"]
    return grade


# Incidents


def _term_for(enrollment: Enrollment, on: date, term: Term | None) -> Term:
    if term is not None:
        if term.academic_year_id != enrollment.academic_year_id or term.kind != Term.Kind.PERIOD:
            raise BusinessError(BAD_TERM)
        return term
    found = Term.objects.filter(
        academic_year_id=enrollment.academic_year_id,
        kind=Term.Kind.PERIOD,
        starts_on__lte=on,
        ends_on__gte=on,
    ).first()
    if found is None:
        raise BusinessError(NO_TERM)
    return found


def record_incident(
    *,
    actor: User,
    enrollment: Enrollment,
    rule: DisciplineRule,
    occurred_on: date,
    note: str = "",
    term: Term | None = None,
) -> DisciplineIncident:
    """Attribue l'infraction à l'élève ; la période est celle de la date (ou `term`)."""
    if not rule.is_active:
        raise BusinessError(RULE_INACTIVE)
    if enrollment.status != Enrollment.Status.ACTIVE:
        raise BusinessError(ENROLLMENT_INACTIVE)
    if occurred_on > timezone.localdate():
        raise BusinessError(FUTURE_DATE)
    period = _term_for(enrollment, occurred_on, term)
    with transaction.atomic():
        incident = DisciplineIncident.objects.create(
            enrollment=enrollment,
            term=period,
            rule=rule,
            points=rule.points,
            occurred_on=occurred_on,
            note=note.strip(),
            recorded_by=actor,
        )
        audit.record(
            Action.DISCIPLINE_INCIDENT_RECORDED,
            incident,
            actor=actor,
            after={
                "offence": rule.label,
                "points": rule.points,
                "date": occurred_on.isoformat(),
                "term": str(period),
            },
            label=f"{enrollment.student.full_name} · {rule.label}",
        )
        events.incident_recorded(incident)
    return incident


def cancel_incident(incident: DisciplineIncident, *, actor: User, reason: str) -> None:
    """Annule l'incident : une ligne liée, avec motif ; ses points ne comptent plus."""
    with transaction.atomic():
        if IncidentCancellation.objects.filter(incident=incident).exists():
            raise BusinessError(ALREADY_CANCELLED)
        IncidentCancellation.objects.create(
            incident=incident, reason=reason.strip(), cancelled_by=actor
        )
        audit.record(
            Action.DISCIPLINE_INCIDENT_CANCELLED,
            incident,
            actor=actor,
            after={"reason": reason.strip(), "points": incident.points},
            label=f"{incident.enrollment.student.full_name} · {incident.rule.label}",
        )


def incidents_of(enrollment: Enrollment):
    """Incidents d'une inscription, annulés compris (marqués), les plus récents d'abord."""
    return DisciplineIncident.objects.filter(enrollment=enrollment).select_related(
        "rule", "term", "recorded_by", "cancellation__cancelled_by"
    )


@dataclass
class TermConduct:
    """Une période d'une inscription : points retenus, cote des points, cote retenue (la
    correction si elle existe) et, s'il y en a une, la correction avec son motif."""

    term: Term
    points: int
    calculated: str
    grade: str
    override: ConductGrade | None = None
    label: str = ""


def _terms_of(enrollments, *, only: Term | None = None) -> dict:
    """Points retenus (incidents non annulés) : {(inscription, période): total}."""
    rows = DisciplineIncident.objects.filter(enrollment__in=enrollments, cancellation__isnull=True)
    if only is not None:
        rows = rows.filter(term=only)
    sums = rows.values("enrollment", "term").annotate(total=Sum("points"))
    return {(row["enrollment"], row["term"]): row["total"] for row in sums}


def totals_of(enrollment: Enrollment) -> list[TermConduct]:
    """Cote de chaque période de l'année de l'inscription (la correction peut porter sur une
    période sans incident)."""
    scale = scale_of()
    totals = _terms_of([enrollment])
    overrides = {
        o.term_id: o
        for o in ConductGrade.objects.filter(enrollment=enrollment).select_related("overridden_by")
    }
    result = []
    periods = Term.objects.filter(
        academic_year_id=enrollment.academic_year_id, kind=Term.Kind.PERIOD
    ).order_by("order")
    for number, term in enumerate(periods, start=1):
        points = totals.get((enrollment.pk, term.pk), 0)
        calculated = grade_for(points, scale)
        override = overrides.get(term.pk)
        result.append(
            TermConduct(
                term,
                points,
                calculated,
                override.grade if override else calculated,
                override,
                term.name or gettext("Period %(n)d") % {"n": number},
            )
        )
    return result


def grades_of_class(enrollment_ids, terms) -> dict:
    """Cote retenue de chaque inscription pour chaque période de `terms` : {(inscription, période):
    cote}. Deux requêtes pour toute la classe (bulletins) ; sans incident ni correction, TB."""
    scale = scale_of()
    totals = _terms_of(enrollment_ids)
    overrides = {
        (o.enrollment_id, o.term_id): o.grade
        for o in ConductGrade.objects.filter(enrollment__in=enrollment_ids)
    }
    return {
        (enrollment_id, term.pk): overrides.get(
            (enrollment_id, term.pk), grade_for(totals.get((enrollment_id, term.pk), 0), scale)
        )
        for enrollment_id in enrollment_ids
        for term in terms
    }


def override_grade(
    enrollment: Enrollment, term: Term, *, actor: User, grade: str, reason: str
) -> ConductGrade:
    """Corrige la cote de la période (motif obligatoire) ; une seconde correction remplace la
    première, le journal garde les deux."""
    reason = reason.strip()
    if grade not in GRADES:
        raise BusinessError(BAD_GRADE)
    if not reason:
        raise BusinessError(REASON_REQUIRED)
    if term.kind != Term.Kind.PERIOD or term.academic_year_id != enrollment.academic_year_id:
        raise BusinessError(BAD_TERM_GRADE)
    with transaction.atomic():
        before = totals_for_term(enrollment, term)
        row, _created = ConductGrade.objects.update_or_create(
            enrollment=enrollment,
            term=term,
            defaults={"grade": grade, "reason": reason, "overridden_by": actor},
        )
        audit.record(
            Action.DISCIPLINE_GRADE_OVERRIDDEN,
            row,
            actor=actor,
            before={"grade": before},
            after={"grade": grade, "reason": reason, "term": str(term)},
            label=f"{enrollment.student.full_name} · {term}",
        )
    return row


def clear_override(enrollment: Enrollment, term: Term, *, actor: User) -> None:
    """Reprend la cote des points ; le journal garde la correction retirée."""
    with transaction.atomic():
        row = ConductGrade.objects.filter(enrollment=enrollment, term=term).first()
        if row is None:
            return
        before = {"grade": row.grade, "reason": row.reason}
        row.delete()
        audit.record(
            Action.DISCIPLINE_GRADE_OVERRIDDEN,
            None,
            actor=actor,
            before=before,
            after={"grade": totals_for_term(enrollment, term), "term": str(term)},
            label=f"{enrollment.student.full_name} · {term}",
        )


def totals_for_term(enrollment: Enrollment, term: Term) -> str:
    """Cote retenue de la période (la correction sinon celle des points)."""
    return grades_of_class([enrollment.pk], [term])[(enrollment.pk, term.pk)]

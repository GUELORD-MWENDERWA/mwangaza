"""Conduite et discipline, première moitié (8.5.1a) : liste des infractions avec leurs points,
seuils des cotes de conduite (TB, B, AB, ME, MA) et incidents des élèves.

Droits : `discipline.configure` (liste, seuils, annulation d'un incident), `discipline.record`
(attribuer une infraction : tout enseignant). Un incident garde les points de l'infraction à
l'instant où il est écrit ; il n'est jamais modifié ni effacé, seulement annulé (motif, auteur).
Chaque changement va dans le journal de l'école (domaine `discipline`). La cote d'une période
calculée d'après ces points, les parents prévenus et la ligne du bulletin sont la tâche 8.5.1b.
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
    ConductScale,
    DisciplineIncident,
    DisciplineRule,
    IncidentCancellation,
)
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
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
    term: Term
    points: int
    grade: str


def totals_of(enrollment: Enrollment) -> list[TermConduct]:
    """Points retenus (incidents non annulés) et cote proposée, période par période ; seules les
    périodes qui ont des incidents sont listées."""
    scale = scale_of()
    sums = (
        DisciplineIncident.objects.filter(enrollment=enrollment, cancellation__isnull=True)
        .values("term")
        .annotate(total=Sum("points"))
    )
    totals = {row["term"]: row["total"] for row in sums}
    terms = Term.objects.filter(pk__in=totals).order_by("order")
    return [TermConduct(t, totals[t.pk], grade_for(totals[t.pk], scale)) for t in terms]

"""Configuration des frais de l'école courante (E1, E2, E5) : types de frais, barèmes et leurs
tranches, taux de change de l'année, reprise des barèmes dans une nouvelle année (C1).

Droits `finance.configure_fees` et `finance.set_exchange_rate`, vérifiés par l'API. Chaque
changement va dans le journal de l'école (domaine `finance`), dans la transaction de l'action.
Montants en entiers dans la devise du barème (skill `argent`).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.money import Money
from apps.core.tenancy import require_current_school, use_school
from apps.finance.models import ExchangeRate, FeeRule, FeeType, InstallmentTemplate
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Track

FEE_TYPE_NAME_TAKEN = ApiError(
    "fee_type_name_taken", _("The school already has a fee type with this name."), 409
)
FEE_TYPE_IN_USE = ApiError(
    "fee_type_in_use", _("This fee type has fee rules: deactivate it instead."), 409
)
FEE_RULE_EXISTS = ApiError(
    "fee_rule_exists", _("This fee already has a fee rule for this scope this school year."), 409
)


def _invalid(path: str, message, code: str, **params) -> ValidationError:
    return ValidationError({path: ValidationError(message, code=code, params=params or None)})


# Types de frais (E1)


def _fee_type_data(fee_type: FeeType) -> dict:
    return {
        "name": fee_type.name,
        "category": fee_type.category,
        "funds_teacher_bonus": fee_type.funds_teacher_bonus,
        "accounting_code": fee_type.accounting_code,
        "is_active": fee_type.is_active,
    }


def _check_fee_type_name(name: str, *, fee_type_id=None) -> None:
    if FeeType.objects.filter(name__iexact=name).exclude(pk=fee_type_id).exists():
        raise BusinessError(FEE_TYPE_NAME_TAKEN)


def create_fee_type(*, actor: User, name: str, category: str, **fields) -> FeeType:
    require_current_school()
    with transaction.atomic():
        _check_fee_type_name(name)
        fee_type = FeeType.objects.create(name=name, category=category, created_by=actor, **fields)
        audit.record(
            Action.FINANCE_FEE_TYPE_CREATED, fee_type, actor=actor, after=_fee_type_data(fee_type)
        )
    return fee_type


def update_fee_type(fee_type: FeeType, *, actor: User, **fields) -> FeeType:
    with transaction.atomic():
        if "name" in fields:
            _check_fee_type_name(fields["name"], fee_type_id=fee_type.pk)
        before = _fee_type_data(fee_type)
        label = str(fee_type)
        for field, value in fields.items():
            setattr(fee_type, field, value)
        before, after = audit.changes(before, _fee_type_data(fee_type))
        if after:
            fee_type.save()
            audit.record(
                Action.FINANCE_FEE_TYPE_UPDATED,
                fee_type,
                actor=actor,
                before=before,
                after=after,
                label=label,
            )
    return fee_type


def delete_fee_type(fee_type: FeeType, *, actor: User) -> None:
    """Un type créé par erreur, sans barème ; sinon on le désactive."""
    with transaction.atomic():
        audit.record(
            Action.FINANCE_FEE_TYPE_DELETED, fee_type, actor=actor, before=_fee_type_data(fee_type)
        )
        try:
            fee_type.delete()
        except ProtectedError:
            raise BusinessError(FEE_TYPE_IN_USE) from None


# Barèmes et tranches (E2)


@dataclass(frozen=True)
class Installment:
    label: str
    amount_minor: int
    due_on: date


@dataclass(frozen=True)
class Scope:
    """Toute l'école (rien de rempli), ou un seul niveau, une seule option ou une seule classe."""

    level: Level | None = None
    track: Track | None = None
    class_group: ClassGroup | None = None


WHOLE_SCHOOL = Scope()


def _rule_data(rule: FeeRule, installments: list[Installment]) -> dict:
    return {
        "scope": rule.scope_name or str(_("Whole school")),
        "currency": rule.currency,
        "total_amount_minor": rule.total_amount_minor,
        "schedule_kind": rule.schedule_kind,
        "installments": [
            {"label": i.label, "amount_minor": i.amount_minor, "due_on": i.due_on.isoformat()}
            for i in installments
        ],
    }


def _rule_label(rule: FeeRule) -> str:
    scope = rule.scope_name or _("Whole school")
    return f"{rule.fee_type.name} · {scope} · {rule.academic_year.name}"


def _installments_of(rule: FeeRule) -> list[Installment]:
    return [Installment(i.label, i.amount_minor, i.due_on) for i in rule.installments.all()]


def _check_rule(
    rule: FeeRule, scope: Scope, installments: list[Installment], *, school: School
) -> None:
    """Vérifie tout avant d'écrire : un refus ne laisse rien à moitié changé."""
    if sum(target is not None for target in (scope.level, scope.track, scope.class_group)) > 1:
        raise _invalid("scope", _("Choose a level, a track or a class, not several."), "scopes")
    if scope.class_group and scope.class_group.academic_year_id != rule.academic_year_id:
        message = _("This class belongs to another school year.")
        raise _invalid("class_group", message, "class_other_year")
    if rule.currency not in school.enabled_currencies:
        message = _("This currency is not one of the school's currencies.")
        raise _invalid("currency", message, "currency_not_enabled")
    if not installments:
        raise _invalid("installments", _("Add at least one installment."), "no_installment")
    if rule.schedule_kind == FeeRule.ScheduleKind.SINGLE and len(installments) != 1:
        message = _("A single payment has exactly one installment.")
        raise _invalid("installments", message, "single_needs_one")
    total = Money(rule.total_amount_minor, rule.currency)
    paid_in = sum(
        (Money(i.amount_minor, rule.currency) for i in installments), Money.zero(rule.currency)
    )
    if paid_in != total:
        message = _("The installments must add up to the total.")
        raise _invalid("installments", message, "installments_total_mismatch")
    same_scope = FeeRule.objects.filter(
        academic_year=rule.academic_year,
        fee_type=rule.fee_type,
        level=scope.level,
        track=scope.track,
        class_group=scope.class_group,
    ).exclude(pk=rule.pk)
    if same_scope.exists():
        raise BusinessError(FEE_RULE_EXISTS)


def _write_installments(rule: FeeRule, installments: list[Installment], *, actor: User) -> None:
    """Tranches mises à jour par position : chacune garde son identifiant (les dus des élèves
    y seront rattachés, 2.6) ; celles en trop sont retirées."""
    existing = list(rule.installments.all())
    kept = existing[: len(installments)]
    for template, item in zip(kept, installments, strict=False):
        template.label, template.amount_minor, template.due_on = (
            item.label,
            item.amount_minor,
            item.due_on,
        )
        template.save(update_fields=["label", "amount_minor", "due_on", "updated_at"])
    InstallmentTemplate.objects.filter(
        pk__in=[t.pk for t in existing[len(installments) :]]
    ).delete()
    InstallmentTemplate.objects.bulk_create(
        [
            InstallmentTemplate(
                fee_rule=rule,
                label=item.label,
                amount_minor=item.amount_minor,
                due_on=item.due_on,
                order=order,
                created_by=actor,
            )
            for order, item in enumerate(installments)
            if order >= len(existing)
        ]
    )


def create_fee_rule(
    *,
    actor: User,
    academic_year: AcademicYear,
    fee_type: FeeType,
    currency: str,
    total_amount_minor: int,
    schedule_kind: str,
    installments: list[Installment],
    scope: Scope = WHOLE_SCHOOL,
) -> FeeRule:
    school = require_current_school()
    rule = FeeRule(
        academic_year=academic_year,
        fee_type=fee_type,
        level=scope.level,
        track=scope.track,
        class_group=scope.class_group,
        currency=currency,
        total_amount_minor=total_amount_minor,
        schedule_kind=schedule_kind,
        created_by=actor,
    )
    with transaction.atomic():
        _check_rule(rule, scope, installments, school=school)
        rule.save()
        _write_installments(rule, installments, actor=actor)
        audit.record(
            Action.FINANCE_FEE_RULE_CREATED,
            rule,
            actor=actor,
            after=_rule_data(rule, installments),
            label=_rule_label(rule),
        )
    return rule


def update_fee_rule(
    rule: FeeRule,
    *,
    actor: User,
    currency: str,
    total_amount_minor: int,
    schedule_kind: str,
    installments: list[Installment],
    scope: Scope = WHOLE_SCHOOL,
) -> FeeRule:
    """Tout le barème d'un coup (portée, devise, total, tranches) ; le type de frais et l'année
    ne changent pas."""
    school = require_current_school()
    with transaction.atomic():
        rule = FeeRule.objects.select_for_update().get(pk=rule.pk)
        before = _rule_data(rule, _installments_of(rule))
        rule.level, rule.track, rule.class_group = scope.level, scope.track, scope.class_group
        rule.currency, rule.total_amount_minor, rule.schedule_kind = (
            currency,
            total_amount_minor,
            schedule_kind,
        )
        _check_rule(rule, scope, installments, school=school)
        before, after = audit.changes(before, _rule_data(rule, installments))
        if after:
            rule.save()
            _write_installments(rule, installments, actor=actor)
            audit.record(
                Action.FINANCE_FEE_RULE_UPDATED,
                rule,
                actor=actor,
                before=before,
                after=after,
                label=_rule_label(rule),
            )
    return rule


def delete_fee_rule(rule: FeeRule, *, actor: User) -> None:
    with transaction.atomic():
        audit.record(
            Action.FINANCE_FEE_RULE_DELETED,
            rule,
            actor=actor,
            before=_rule_data(rule, _installments_of(rule)),
            label=_rule_label(rule),
        )
        rule.delete()


def _shift_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 février vers une année non bissextile
        return day.replace(year=day.year + years, day=28)


def copy_fee_rules(source: AcademicYear, year: AcademicYear, *, actor: User) -> int:
    """Barèmes de `source` repris dans `year` (C1), dates limites décalées d'autant d'années que
    le début de l'année. Le barème d'une classe va à la classe reprise (même niveau, option et
    section) ; sans elle, il n'est pas repris. Appelé dans la transaction de la création."""
    years = year.starts_on.year - source.starts_on.year
    classes = {
        (group.level_id, group.track_id, group.section): group for group in year.class_groups.all()
    }
    rules = source.fee_rules.select_related("class_group").prefetch_related("installments")
    copied = 0
    for rule in rules:
        class_group = None
        if rule.class_group:
            old = rule.class_group
            class_group = classes.get((old.level_id, old.track_id, old.section))
            if class_group is None:
                continue
        new = FeeRule.objects.create(
            academic_year=year,
            fee_type_id=rule.fee_type_id,
            level_id=rule.level_id,
            track_id=rule.track_id,
            class_group=class_group,
            currency=rule.currency,
            total_amount_minor=rule.total_amount_minor,
            schedule_kind=rule.schedule_kind,
            created_by=actor,
        )
        InstallmentTemplate.objects.bulk_create(
            [
                InstallmentTemplate(
                    fee_rule=new,
                    label=item.label,
                    amount_minor=item.amount_minor,
                    due_on=_shift_years(item.due_on, years),
                    order=item.order,
                    created_by=actor,
                )
                for item in rule.installments.all()
            ]
        )
        copied += 1
    audit.record(
        Action.FINANCE_FEE_RULES_COPIED,
        year,
        actor=actor,
        after={"copied_from": source.name, "fee_rule_count": copied},
    )
    return copied


# Devises utilisées (M5)


def currencies_in_use(school: School) -> set[str]:
    """Devises des barèmes de l'école, toutes années confondues (plus tard : des paiements)."""
    with use_school(school):
        return set(FeeRule.objects.values_list("currency", flat=True).distinct())


# Taux de l'année (E5)


def current_rate(academic_year: AcademicYear) -> ExchangeRate | None:
    """Le taux en vigueur : la dernière ligne de l'année."""
    return (
        ExchangeRate.objects.filter(academic_year=academic_year)
        .order_by("-created_at", "-id")
        .first()
    )


def _rate_text(rate: Decimal) -> str:
    return f"{rate.normalize():f}"


def set_exchange_rate(
    *, actor: User, academic_year: AcademicYear, rate: Decimal, reason: str = ""
) -> ExchangeRate:
    """Taux USD → CDF de l'année, fixe toute l'année (E5). Une correction ajoute une ligne avec
    son motif ; les paiements déjà faits gardent le taux qu'ils ont utilisé."""
    require_current_school()
    reason = reason.strip()
    with transaction.atomic():
        # Deux corrections en même temps : l'une après l'autre.
        AcademicYear.objects.select_for_update().get(pk=academic_year.pk)
        previous = current_rate(academic_year)
        if previous is not None and not reason:
            message = _("Give the reason for the correction.")
            raise _invalid("reason", message, "reason_required")
        if previous is not None and previous.rate == rate:
            raise _invalid("rate", _("This is already the rate of the year."), "same_rate")
        new = ExchangeRate.objects.create(
            academic_year=academic_year, rate=rate, reason=reason, created_by=actor
        )
        audit.record(
            Action.FINANCE_EXCHANGE_RATE_SET,
            new,
            actor=actor,
            before={"rate": _rate_text(previous.rate)} if previous else None,
            after={"rate": _rate_text(rate), **({"reason": reason} if reason else {})},
            label=academic_year.name,
        )
    return new

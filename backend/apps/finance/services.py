"""Configuration des frais de l'école courante (E1, E2, E5) : types de frais, barèmes et leurs
tranches, taux de change de l'année, reprise des barèmes dans une nouvelle année (C1) ; frais
dus des élèves, tirés des barèmes (2.6) ou d'un échéancier particulier (E4).

Droits `finance.configure_fees`, `finance.set_exchange_rate` et `finance.grant_discount`,
vérifiés par l'API. Chaque
changement va dans le journal de l'école (domaine `finance`), dans la transaction de l'action.
Montants en entiers dans la devise du barème (skill `argent`).
"""

from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.money import Money
from apps.core.tenancy import require_current_school, use_school
from apps.finance.models import (
    ExchangeRate,
    FeeRule,
    FeeType,
    InstallmentTemplate,
    StudentCharge,
)
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Track
from apps.students.models import Enrollment

FEE_TYPE_NAME_TAKEN = ApiError(
    "fee_type_name_taken", _("The school already has a fee type with this name."), 409
)
FEE_TYPE_IN_USE = ApiError(
    "fee_type_in_use",
    _("This fee type has fee rules or students who owe it: deactivate it instead."),
    409,
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
            after={**_rule_data(rule, installments), "students_updated": _sync_rule(rule, actor)},
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
                after={**after, "students_updated": _sync_rule(rule, actor)},
                label=_rule_label(rule),
            )
    return rule


def delete_fee_rule(rule: FeeRule, *, actor: User) -> None:
    with transaction.atomic():
        before, label = _rule_data(rule, _installments_of(rule)), _rule_label(rule)
        deleted = copy(rule)  # `delete()` vide l'identifiant ; le journal garde celui du barème
        rule.delete()
        audit.record(
            Action.FINANCE_FEE_RULE_DELETED,
            deleted,
            actor=actor,
            before=before,
            after={"students_updated": _sync_rule(deleted, actor)},
            label=label,
        )


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


# Frais dus des élèves (2.6)


def _rank(rule: FeeRule, group: ClassGroup) -> int | None:
    """Précision du barème pour la classe : 0 la classe, 1 son niveau, 2 son option, 3 toute
    l'école ; `None` s'il ne la concerne pas."""
    if rule.class_group_id:
        return 0 if rule.class_group_id == group.pk else None
    if rule.level_id:
        return 1 if rule.level_id == group.level_id else None
    if rule.track_id:
        return 2 if rule.track_id == group.track_id else None
    return 3


def _wanted(rules: list[FeeRule], group: ClassGroup) -> dict:
    """Tranches dues par un élève de la classe : `{tranche: (barème, tranche)}`, avec pour chaque
    type de frais le barème le plus précis."""
    best: dict = {}
    for rule in rules:
        rank = _rank(rule, group)
        if rank is not None and rank < best.get(rule.fee_type_id, (4,))[0]:
            best[rule.fee_type_id] = (rank, rule)
    return {
        template.pk: (rule, template)
        for _rank_, rule in best.values()
        for template in rule.installments.all()
    }


def sync_charges(
    enrollments: QuerySet[Enrollment], *, actor: User | None, fee_type: FeeType | None = None
) -> int:
    """Remet les frais dus des inscriptions actives de `enrollments` d'accord avec les barèmes de
    leur année (tous, ou ceux de `fee_type`) : une ligne par tranche du barème le plus précis,
    montant et date à jour ; une tranche qui ne s'applique plus passe « retirée », une tranche
    retirée qui s'applique de nouveau redevient due. Un élève parti garde ses frais tels quels,
    comme un type de frais sous échéancier particulier (E4). Les frais déjà payés ne bougeront
    pas (3.1). En quelques requêtes, quel que soit le nombre d'élèves. Renvoie le nombre
    d'élèves dont les frais ont changé."""
    with transaction.atomic():
        enrollments = list(
            enrollments.filter(status=Enrollment.Status.ACTIVE)
            .select_related("class_group")
            .select_for_update(of=("self",))
        )
        if not enrollments:
            return 0
        rules = (
            FeeRule.objects.filter(academic_year_id__in={e.academic_year_id for e in enrollments})
            .select_related("fee_type")
            .prefetch_related("installments")
        )
        existing = StudentCharge.objects.filter(enrollment__in=enrollments)
        if fee_type is not None:
            rules, existing = rules.filter(fee_type=fee_type), existing.filter(fee_type=fee_type)
        existing = list(existing)
        rules_by_year, charges_by_enrollment = defaultdict(list), defaultdict(list)
        for rule in rules:
            rules_by_year[rule.academic_year_id].append(rule)
        custom = {
            (charge.enrollment_id, charge.fee_type_id)
            for charge in existing
            if charge.source == StudentCharge.Source.CUSTOM
        }
        for charge in existing:
            if (charge.enrollment_id, charge.fee_type_id) not in custom:
                charges_by_enrollment[charge.enrollment_id].append(charge)

        wanted_by_class: dict = {}
        to_create, to_update, changed = [], [], set()
        now = timezone.now()
        for enrollment in enrollments:
            group, current = enrollment.class_group, charges_by_enrollment[enrollment.pk]
            if group.pk not in wanted_by_class:
                year_rules = rules_by_year[enrollment.academic_year_id]
                wanted_by_class[group.pk] = _wanted(year_rules, group)
            wanted = wanted_by_class[group.pk]
            for charge in current:
                target = wanted.get(charge.installment_template_id)
                values = {"status": StudentCharge.Status.REMOVED}
                if target is not None:
                    rule, template = target
                    values = {
                        "status": StudentCharge.Status.ACTIVE,
                        "label": template.label,
                        "amount_minor": template.amount_minor,
                        "currency": rule.currency,
                        "due_on": template.due_on,
                    }
                if any(getattr(charge, field) != value for field, value in values.items()):
                    for field, value in values.items():
                        setattr(charge, field, value)
                    charge.updated_at = now
                    to_update.append(charge)
                    changed.add(enrollment.pk)
            have = {charge.installment_template_id for charge in current}
            for template_id, (rule, template) in wanted.items():
                if template_id not in have and (enrollment.pk, rule.fee_type_id) not in custom:
                    to_create.append(
                        StudentCharge(
                            enrollment=enrollment,
                            fee_type=rule.fee_type,
                            label=template.label,
                            amount_minor=template.amount_minor,
                            currency=rule.currency,
                            due_on=template.due_on,
                            source=StudentCharge.Source.RULE,
                            installment_template=template,
                            created_by=actor,
                        )
                    )
                    changed.add(enrollment.pk)
        StudentCharge.objects.bulk_create(to_create, batch_size=500)
        StudentCharge.objects.bulk_update(
            to_update,
            ["status", "label", "amount_minor", "currency", "due_on", "updated_at"],
            batch_size=500,
        )
    return len(changed)


def _sync_rule(rule: FeeRule, actor: User) -> int:
    """Frais dus des élèves de l'année pour le type de frais d'un barème créé, modifié ou
    supprimé : sa portée a pu changer, et un barème moins précis peut prendre le relais."""
    enrollments = Enrollment.objects.filter(academic_year_id=rule.academic_year_id)
    return sync_charges(enrollments, actor=actor, fee_type=rule.fee_type)


# Échéancier particulier (E4)


def _charge_data(label: str, amount_minor: int, due_on: date) -> dict:
    return {"label": label, "amount_minor": amount_minor, "due_on": due_on.isoformat()}


def reschedule_charges(
    enrollment: Enrollment,
    *,
    actor: User,
    fee_type: FeeType,
    installments: list[Installment],
    reason: str,
    parent_signed: bool,
) -> list[StudentCharge]:
    """Arrangement avec la famille (E4) : les frais dus de `fee_type` pas encore payés passent
    « remplacés », et `installments` (même devise, même total au centime près) deviennent ce que
    doit l'élève (`source=custom`). Rien n'est effacé ; ce type de frais ne suit plus les
    barèmes pour cet élève (`sync_charges`). Renvoie les nouveaux frais dus."""
    reason = reason.strip()
    if not reason:
        raise _invalid("reason", _("This field may not be blank."), "blank")
    if not installments:
        raise _invalid("installments", _("Add at least one installment."), "no_installment")
    with transaction.atomic():
        enrollment = (
            Enrollment.objects.select_related("student")
            .select_for_update(of=("self",))
            .get(pk=enrollment.pk)
        )
        if enrollment.status != Enrollment.Status.ACTIVE:
            message = _("Only a student enrolled this year can get a custom schedule.")
            raise _invalid("enrollment", message, "enrollment_not_active")
        # 3.1 : sans les frais déjà payés, même en partie (un paiement affecté ne bouge jamais).
        replaced = list(
            StudentCharge.objects.filter(
                enrollment=enrollment, fee_type=fee_type, status=StudentCharge.Status.ACTIVE
            ).order_by("due_on", "label")
        )
        if not replaced:
            message = _("The student owes nothing unpaid for this fee.")
            raise _invalid("fee_type", message, "nothing_to_reschedule")
        currency = replaced[0].currency
        if any(charge.currency != currency for charge in replaced):
            message = _("This fee is owed in several currencies: it cannot be rescheduled.")
            raise _invalid("fee_type", message, "mixed_currencies")
        remaining = sum(
            (Money(charge.amount_minor, currency) for charge in replaced), Money.zero(currency)
        )
        planned = sum((Money(i.amount_minor, currency) for i in installments), Money.zero(currency))
        if planned != remaining:
            message = _("The installments must add up to what is left to reschedule.")
            raise _invalid("installments", message, "schedule_total_mismatch")

        now = timezone.now()
        for charge in replaced:
            charge.status, charge.updated_at = StudentCharge.Status.REPLACED, now
        StudentCharge.objects.bulk_update(replaced, ["status", "updated_at"])
        created = StudentCharge.objects.bulk_create(
            [
                StudentCharge(
                    enrollment=enrollment,
                    fee_type=fee_type,
                    label=item.label,
                    amount_minor=item.amount_minor,
                    currency=currency,
                    due_on=item.due_on,
                    source=StudentCharge.Source.CUSTOM,
                    created_by=actor,
                )
                for item in installments
            ]
        )
        audit.record(
            Action.FINANCE_CHARGES_RESCHEDULED,
            enrollment,
            actor=actor,
            label=f"{enrollment.student} · {fee_type.name}",
            before={"charges": [_charge_data(c.label, c.amount_minor, c.due_on) for c in replaced]},
            after={
                "fee_type": fee_type.name,
                "currency": currency,
                "reason": reason,
                "parent_signed": parent_signed,
                "installments": [
                    _charge_data(i.label, i.amount_minor, i.due_on) for i in installments
                ],
            },
        )
    return created


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

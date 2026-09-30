"""Configuration des frais de l'école courante (E1, E2, E5) : types de frais, barèmes et leurs
tranches, taux de change de l'année, reprise des barèmes dans une nouvelle année (C1) ; frais
dus des élèves, tirés des barèmes (2.6) ou d'un échéancier particulier (E4) ; réductions (E3) ;
solde et retards d'un élève (2.7) ; caisses, sessions de caisse et encaissement (F1-F2).

Droits `finance.configure_fees`, `finance.set_exchange_rate`, `finance.grant_discount` et
`finance.collect_payment`, vérifiés par l'API. Chaque
changement va dans le journal de l'école (domaine `finance`), dans la transaction de l'action.
Montants en entiers dans la devise du barème (skill `argent`).
"""

import re
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import (
    BigIntegerField,
    Count,
    Exists,
    F,
    OuterRef,
    Prefetch,
    ProtectedError,
    Q,
    QuerySet,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.money import Currency, Money, percent_of, prorate
from apps.core.tenancy import require_current_school, use_school
from apps.finance.models import (
    CancellationRequest,
    CashClosing,
    CashRegister,
    CashSession,
    CreditAllocation,
    Discount,
    ExchangeRate,
    FeeRule,
    FeeType,
    InstallmentTemplate,
    Payment,
    PaymentAllocation,
    PaymentCancellation,
    StudentCharge,
    StudentCredit,
)
from apps.schools import organisation
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Track
from apps.students.models import Enrollment
from apps.sync import changes as sync_changes
from apps.sync.models import Device

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
DISCOUNT_REVOKED = ApiError("discount_revoked", _("This discount was already revoked."), 409)
CASH_REGISTER_TAKEN = ApiError(
    "cash_register_taken",
    _("The school already has a cash register with this name or code."),
    409,
)
CASH_REGISTER_INACTIVE = ApiError(
    "cash_register_inactive", _("This cash register is deactivated."), 409
)
CASH_REGISTER_BUSY = ApiError(
    "cash_register_busy", _("Another cashier already has this cash register open."), 409
)
SESSION_ALREADY_OPEN = ApiError(
    "session_already_open", _("You already have a cash register open: close it first."), 409
)
NO_OPEN_SESSION = ApiError(
    "no_open_session", _("Open a cash register before collecting payments."), 409
)
SESSION_CLOSED = ApiError("session_closed", _("This cash session is already closed."), 409)
NOT_YOUR_SESSION = ApiError(
    "not_your_session", _("Only the cashier of this session can close it."), 403
)
NO_EXCHANGE_RATE = ApiError(
    "no_exchange_rate", _("The accountant must first set the exchange rate of the year."), 409
)
PAYMENT_ID_TAKEN = ApiError(
    "payment_id_taken", _("Another payment already has this identifier."), 409
)
PAYMENT_CANCELLED = ApiError(
    "payment_cancelled", _("This payment was cancelled: its receipt is no longer valid."), 409
)
CREDIT_USED = ApiError("credit_used", _("This credit was already used."), 409)
CREDIT_VOIDED = ApiError(
    "credit_voided", _("This credit was voided: its discount was revoked."), 409
)
CANCELLATION_PENDING = ApiError(
    "cancellation_pending",
    _("A cancellation of this payment is already waiting for approval."),
    409,
)
CANCELLATION_DECIDED = ApiError(
    "cancellation_decided", _("This cancellation request was already decided."), 409
)
OWN_CANCELLATION = ApiError(
    "own_cancellation", _("Someone else must approve your own cancellation request."), 403
)
CANCELLATION_ID_TAKEN = ApiError(
    "cancellation_id_taken", _("This identifier belongs to another request."), 409
)
NOTHING_OWED = ApiError(
    "nothing_owed", _("The student owes nothing more in the currency of this credit."), 409
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
    comme un type de frais sous échéancier particulier (E4). Un frais déjà payé, même en partie,
    ne bouge plus ; s'il ne s'applique plus (changement de classe), il tient la place de la
    tranche de même rang et de même devise, qui n'est pas ajoutée. En quelques requêtes, quel
    que soit le nombre d'élèves. Renvoie le nombre d'élèves dont les frais ont changé."""
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
        paid = paid_charge_ids(existing)
        existing = list(existing.select_related("installment_template"))
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
            held = {
                (charge.fee_type_id, charge.currency, charge.installment_template.order)
                for charge in current
                if charge.pk in paid
                and charge.installment_template_id is not None
                and charge.installment_template_id not in wanted
            }
            for charge in current:
                if charge.pk in paid:
                    continue
                target = wanted.get(charge.installment_template_id)
                values = {"status": StudentCharge.Status.REMOVED}
                if target is not None and _slot(*target) not in held:
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
                if (
                    template_id not in have
                    and (enrollment.pk, rule.fee_type_id) not in custom
                    and _slot(rule, template) not in held
                ):
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
        sync_changes.touch_enrollments(changed)
    return len(changed)


def paid_charge_ids(charges: QuerySet) -> set:
    """Frais dus de `charges` qui ont reçu un paiement non annulé, même en partie."""
    return set(
        PaymentAllocation.objects.filter(
            student_charge__in=charges, payment__cancellation__isnull=True
        ).values_list("student_charge_id", flat=True)
    )


def _slot(rule: FeeRule, template: InstallmentTemplate) -> tuple:
    """Place d'une tranche parmi les frais dus de l'élève : type de frais, devise, rang."""
    return (rule.fee_type_id, rule.currency, template.order)


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
    """Arrangement avec la famille (E4) : les frais dus de `fee_type` sans aucun paiement passent
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
        # Sans les frais déjà payés, même en partie : un paiement affecté ne bouge jamais.
        active = StudentCharge.objects.filter(
            enrollment=enrollment, fee_type=fee_type, status=StudentCharge.Status.ACTIVE
        )
        replaced = list(active.exclude(pk__in=paid_charge_ids(active)).order_by("due_on", "label"))
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
        sync_changes.touch_enrollments([enrollment.pk])
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


# Réductions (E3)


def discount_shares(charges: list[StudentCharge], discounts: list[Discount]) -> dict:
    """Part de réduction de chaque frais dû actif d'une inscription, en entiers dans sa devise.
    Par type de frais (et devise), les réductions qui s'y appliquent s'additionnent — un
    pourcentage du total arrondi demi supérieur, un montant dans la même devise —, plafonnées
    au total, puis se répartissent au prorata des échéances (`prorate` : l'écart d'arrondi sur
    les dernières). Réductions retirées, frais retirés ou remplacés : ignorés. Même calcul dans
    `@mwangaza/money` (tableau « Effet sur ce que doit l'élève »). Renvoie {id du frais: part}."""
    groups = defaultdict(list)
    for charge in charges:
        if charge.status == StudentCharge.Status.ACTIVE:
            groups[charge.fee_type_id, charge.currency].append(charge)
    live = [discount for discount in discounts if discount.revoked_at is None]
    shares = {}
    for (fee_type_id, currency), group in groups.items():
        group.sort(key=lambda charge: (charge.due_on, charge.label, str(charge.pk)))
        total = sum(charge.amount_minor for charge in group)
        reduction = 0
        for discount in live:
            if discount.fee_type_id not in (None, fee_type_id):
                continue
            if discount.kind == Discount.Kind.PERCENT:
                reduction += percent_of(total, discount.percent)
            elif discount.currency == currency:
                reduction += discount.amount_minor
        weights = [charge.amount_minor for charge in group]
        for charge, share in zip(group, prorate(min(reduction, total), weights), strict=True):
            shares[charge.pk] = share
    return shares


def _discount_data(discount: Discount) -> dict:
    data = {
        "fee_type": discount.fee_type.name if discount.fee_type else None,
        "reason_code": discount.reason_code,
        "reason": discount.reason,
    }
    if discount.kind == Discount.Kind.PERCENT:
        return {**data, "percent": discount.percent}
    return {**data, "amount_minor": discount.amount_minor, "currency": discount.currency}


def _discount_label(enrollment: Enrollment, fee_type: FeeType | None) -> str:
    return f"{enrollment.student} · {fee_type.name}" if fee_type else str(enrollment.student)


def grant_discount(
    enrollment: Enrollment,
    *,
    actor: User,
    fee_type: FeeType | None,
    kind: str,
    reason_code: str,
    reason: str,
    percent: int | None = None,
    amount_minor: int | None = None,
) -> Discount:
    """Réduction pour l'année d'un élève inscrit (E3) : un pourcentage sur un frais ou sur tous,
    ou un montant dans la devise d'un frais, jamais plus que ce frais. Motif obligatoire ; qui et
    quand sont gardés, et l'action va dans l'historique de l'élève. Sur des échéances déjà
    payées, ce qui devient payé en trop est un crédit de l'élève (M14), par devise."""
    reason = reason.strip()
    if not reason:
        raise _invalid("reason", _("This field may not be blank."), "blank")
    with transaction.atomic():
        enrollment = (
            Enrollment.objects.select_related("student")
            .select_for_update(of=("self",))
            .get(pk=enrollment.pk)
        )
        if enrollment.status != Enrollment.Status.ACTIVE:
            message = _("Only a student enrolled this year can get a discount.")
            raise _invalid("enrollment", message, "enrollment_not_active")
        charges = StudentCharge.objects.filter(
            enrollment=enrollment, status=StudentCharge.Status.ACTIVE
        )
        if fee_type is not None:
            charges = charges.filter(fee_type=fee_type)
        charges = list(charges)
        if not charges:
            message = _("The student owes nothing for this fee.")
            raise _invalid("fee_type", message, "nothing_to_discount")
        currency = ""
        if kind == Discount.Kind.AMOUNT:
            currency = charges[0].currency
            if fee_type is None or any(charge.currency != currency for charge in charges):
                message = _("An amount applies to one fee, in its currency.")
                raise _invalid("fee_type", message, "fee_required")
            if amount_minor > sum(charge.amount_minor for charge in charges):
                message = _("A discount cannot be more than the fee.")
                raise _invalid("amount_minor", message, "discount_exceeds_fee")
        before = _excess(charges_of(enrollment.pk))
        discount = Discount.objects.create(
            enrollment=enrollment,
            fee_type=fee_type,
            kind=kind,
            percent=percent if kind == Discount.Kind.PERCENT else None,
            amount_minor=amount_minor if kind == Discount.Kind.AMOUNT else None,
            currency=currency,
            reason_code=reason_code,
            reason=reason,
            created_by=actor,
        )
        audit.record(
            Action.FINANCE_DISCOUNT_GRANTED,
            enrollment,
            actor=actor,
            label=_discount_label(enrollment, fee_type),
            after=_discount_data(discount),
        )
        for currency, excess in _excess(charges_of(enrollment.pk)).items():
            if excess > before.get(currency, 0):
                _create_credit(
                    enrollment,
                    actor=actor,
                    amount=Money(excess - before.get(currency, 0), currency),
                    source_discount=discount,
                )
    return discount


def revoke_discount(discount: Discount, *, actor: User, reason: str) -> Discount:
    """Retire une réduction (E3) : rien n'est effacé, le retrait est noté avec son motif ; ce que
    doit l'élève redevient ce qu'il était sans elle. Les crédits qu'elle a donnés sont annulés,
    et ce qu'ils ont payé redevient dû."""
    reason = reason.strip()
    if not reason:
        raise _invalid("reason", _("This field may not be blank."), "blank")
    with transaction.atomic():
        discount = (
            Discount.objects.select_related("enrollment__student", "fee_type")
            .select_for_update(of=("self",))
            .get(pk=discount.pk)
        )
        if discount.revoked_at is not None:
            raise BusinessError(DISCOUNT_REVOKED)
        discount.revoked_at, discount.revoked_by = timezone.now(), actor
        discount.revoke_reason = reason
        discount.save(update_fields=["revoked_at", "revoked_by", "revoke_reason", "updated_at"])
        audit.record(
            Action.FINANCE_DISCOUNT_REVOKED,
            discount.enrollment,
            actor=actor,
            label=_discount_label(discount.enrollment, discount.fee_type),
            before=_discount_data(discount),
            after={"revoke_reason": reason},
        )
        credits = StudentCredit.objects.filter(source_discount=discount, voided_at__isnull=True)
        for credit in credits.select_for_update():
            _void_credit(credit, discount.enrollment, actor=actor)
    return discount


# Solde et retards (2.7)

PAID, OVERDUE, UPCOMING = "paid", "overdue", "upcoming"
UP_TO_DATE, PARTIAL = "up_to_date", "partial"


def today() -> date:
    """Aujourd'hui dans le fuseau de l'école de l'adresse (activé par le middleware)."""
    return timezone.localdate()


def _settle(charges: list[StudentCharge], discounts: list[Discount], day: date) -> None:
    """Ajoute à chaque frais dû sa part des réductions (`discount_minor`), ce qui est payé
    (`paid_minor`), le reste (`remaining_minor`) et son état (`state`) : soldé, en retard
    (échéance passée, `due_on` < aujourd'hui, et reste > 0) ou à venir ; `None` pour un frais
    retiré ou remplacé, qui ne compte plus. Le payé s'arrête à ce qui est dû : le reste
    (`excess_minor`, après une réduction sur une échéance payée) est un crédit de l'élève."""
    shares = discount_shares(charges, discounts)
    for charge in charges:
        charge.discount_minor = shares.get(charge.pk, 0)
        charge.paid_minor = getattr(charge, "paid_total", 0)
        charge.excess_minor = 0
        if charge.status != StudentCharge.Status.ACTIVE:
            charge.remaining_minor, charge.state = 0, None
            continue
        due = charge.amount_minor - charge.discount_minor
        charge.excess_minor = max(charge.paid_minor - due, 0)
        charge.paid_minor -= charge.excess_minor
        charge.remaining_minor = due - charge.paid_minor
        if charge.remaining_minor == 0:
            charge.state = PAID
        else:
            charge.state = OVERDUE if charge.due_on < day else UPCOMING


# Plus grand que tout identifiant : avec `Moment`, tous les paiements de l'instant.
LAST_ID = UUID(int=2**128 - 1)


@dataclass(frozen=True)
class Moment:
    """Un instant pour `_ordered` : tous les paiements encaissés jusqu'à lui (`id` le plus grand
    possible), avec les annulations et les crédits de ce moment-là."""

    paid_at: datetime
    id: UUID = LAST_ID


def _credit_used(until: Moment | Payment | None = None) -> Coalesce:
    """Crédits utilisés sur le frais dû, s'ils ne sont pas annulés ; avec `until`, ceux utilisés
    avant lui et pas encore annulés à ce moment-là."""
    used = CreditAllocation.objects.filter(student_charge=OuterRef("pk"))
    if until is None:
        used = used.filter(credit__voided_at__isnull=True)
    else:
        used = used.filter(
            Q(credit__voided_at__isnull=True) | Q(credit__voided_at__gt=until.paid_at),
            created_at__lte=until.paid_at,
        )
    total = used.values("student_charge").annotate(total=Sum("amount_minor")).values("total")
    return Coalesce(Subquery(total), 0, output_field=BigIntegerField())


def _ordered(charges: QuerySet, until: Moment | Payment | None = None) -> QuerySet:
    """Avec `paid_total` : allocations des paiements non annulés et crédits utilisés ; avec
    `until`, ceux d'avant lui (lui compris) et pas encore annulés à ce moment-là."""
    counted = Q(allocations__payment__cancellation__isnull=True)
    if until is not None:
        counted = (
            counted | Q(allocations__payment__cancellation__approved_at__gt=until.paid_at)
        ) & (
            Q(allocations__payment__paid_at__lt=until.paid_at)
            | Q(allocations__payment__paid_at=until.paid_at, allocations__payment__id__lte=until.id)
        )
    paid = Sum("allocations__amount_minor", filter=counted)
    return (
        charges.select_related("fee_type")
        .annotate(
            paid_total=Coalesce(paid, 0, output_field=BigIntegerField()) + _credit_used(until)
        )
        .order_by("due_on", "fee_type__name", "label")
    )


def charges_of(enrollment_id) -> list[StudentCharge]:
    """Frais dus d'une inscription par date limite, retirés et remplacés compris, chacun avec
    sa part des réductions, ce qui est payé, le reste et son état (`_settle`). Deux requêtes."""
    charges = list(_ordered(StudentCharge.objects.filter(enrollment_id=enrollment_id)))
    discounts = list(Discount.objects.filter(enrollment_id=enrollment_id))
    _settle(charges, discounts, today())
    return charges


# Colonnes du solde et des listes : lire des milliers de frais dus (impayés) sans le reste.
BALANCE_FIELDS = (
    "enrollment",
    "fee_type__name",
    "label",
    "amount_minor",
    "currency",
    "due_on",
    "status",
)


def charges_by_enrollment(enrollment_ids, *, light: bool = False) -> dict:
    """`charges_of` pour plusieurs inscriptions (une classe), en deux requêtes :
    {id de l'inscription: frais dus} ; `light` : seulement `BALANCE_FIELDS`."""
    charges, discounts = defaultdict(list), defaultdict(list)
    queryset = StudentCharge.objects.filter(enrollment_id__in=enrollment_ids)
    if light:
        queryset = queryset.only(*BALANCE_FIELDS)
    for charge in _ordered(queryset):
        charges[charge.enrollment_id].append(charge)
    for discount in Discount.objects.filter(enrollment_id__in=enrollment_ids):
        discounts[discount.enrollment_id].append(discount)
    day = today()
    for enrollment_id, items in charges.items():
        _settle(items, discounts[enrollment_id], day)
    return charges


@dataclass
class CurrencyBalance:
    currency: str
    total_minor: int
    paid_minor: int
    remaining_minor: int
    overdue_minor: int
    next_due_minor: int


@dataclass
class Balance:
    situation: str
    next_due_on: date | None
    currencies: list[CurrencyBalance]


def balance(charges: list[StudentCharge]) -> Balance:
    """Solde d'un élève à partir de ses frais dus (`charges_of`), par devise et jamais additionné
    entre devises, dollars d'abord : dû pour l'année après réductions, déjà payé, reste, en
    retard, et reste de la prochaine échéance pas encore passée (même date pour toutes les
    devises). Situation : à jour (rien en retard), partielle (en retard, mais des paiements) ou
    en retard (rien payé)."""
    active = [charge for charge in charges if charge.state]
    next_due_on = min((c.due_on for c in active if c.state == UPCOMING), default=None)
    currencies = []
    for currency in Currency.values:
        items = [charge for charge in active if charge.currency == currency]
        if not items:
            continue
        currencies.append(
            CurrencyBalance(
                currency=currency,
                total_minor=sum(c.amount_minor - c.discount_minor for c in items),
                paid_minor=sum(c.paid_minor for c in items),
                remaining_minor=sum(c.remaining_minor for c in items),
                overdue_minor=sum(c.remaining_minor for c in items if c.state == OVERDUE),
                next_due_minor=sum(
                    c.remaining_minor
                    for c in items
                    if c.state == UPCOMING and c.due_on == next_due_on
                ),
            )
        )
    if not any(item.overdue_minor for item in currencies):
        situation = UP_TO_DATE
    else:
        situation = PARTIAL if any(item.paid_minor for item in currencies) else OVERDUE
    return Balance(situation, next_due_on, currencies)


def _balance_at(enrollment_id, until: Moment | Payment) -> Balance:
    charges = list(_ordered(StudentCharge.objects.filter(enrollment_id=enrollment_id), until))
    discounts = list(Discount.objects.filter(enrollment_id=enrollment_id))
    _settle(charges, discounts, timezone.localdate(until.paid_at))
    return balance(charges)


def balance_after(payment: Payment) -> Balance:
    """Solde de l'élève juste après ce paiement, pour son reçu et ses duplicatas : frais dus et
    réductions d'aujourd'hui, paiements encaissés jusqu'à lui, retard au jour du paiement. Deux
    requêtes."""
    return _balance_at(payment.enrollment_id, payment)


def balance_after_cancellation(cancellation: PaymentCancellation) -> Balance:
    """Solde de l'élève juste après cette annulation, pour le reçu d'annulation et ses
    duplicatas : le « reste dû après annulation »."""
    return _balance_at(cancellation.payment.enrollment_id, Moment(cancellation.approved_at))


# Devises utilisées (M5)


def currencies_in_use(school: School) -> set[str]:
    """Devises des barèmes et des paiements de l'école, toutes années confondues."""
    with use_school(school):
        rules = FeeRule.objects.values_list("currency", flat=True).distinct()
        payments = Payment.objects.values_list("received_currency", flat=True).distinct()
        return set(rules) | set(payments)


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


# Caisses et paiements (F1-F2)


def _cash_register_data(register: CashRegister) -> dict:
    return {"name": register.name, "code": register.code, "is_active": register.is_active}


# Série des reçus d'annulation (`ITIG-AN-26-000007`) : jamais le code d'une caisse.
CANCELLATION_SERIES = "AN"


def _check_cash_register(*, name: str, code: str = "", register_id=None) -> None:
    if code == CANCELLATION_SERIES:
        message = _("This code is kept for cancellation receipts.")
        raise _invalid("code", message, "code_reserved")
    taken = Q(name__iexact=name) | Q(code=code) if code else Q(name__iexact=name)
    if CashRegister.objects.filter(taken).exclude(pk=register_id).exists():
        raise BusinessError(CASH_REGISTER_TAKEN)


def create_cash_register(*, actor: User, name: str, code: str) -> CashRegister:
    require_current_school()
    with transaction.atomic():
        _check_cash_register(name=name, code=code)
        register = CashRegister.objects.create(name=name, code=code, created_by=actor)
        audit.record(
            Action.FINANCE_CASH_REGISTER_CREATED,
            register,
            actor=actor,
            after=_cash_register_data(register),
        )
    return register


def update_cash_register(register: CashRegister, *, actor: User, **fields) -> CashRegister:
    """Nom et activation ; le code, qui est dans les numéros des reçus, ne change pas."""
    with transaction.atomic():
        if "name" in fields:
            _check_cash_register(name=fields["name"], register_id=register.pk)
        before, label = _cash_register_data(register), str(register)
        for field, value in fields.items():
            setattr(register, field, value)
        before, after = audit.changes(before, _cash_register_data(register))
        if after:
            register.save()
            audit.record(
                Action.FINANCE_CASH_REGISTER_UPDATED,
                register,
                actor=actor,
                before=before,
                after=after,
                label=label,
            )
    return register


def open_session_of(user: User) -> CashSession | None:
    """La session de caisse ouverte du caissier, s'il en a une ; s'il en a deux (une ouverte hors
    ligne pendant qu'une autre l'était), la plus ancienne, à clôturer d'abord."""
    return (
        CashSession.objects.select_related("cash_register", "cashier")
        .filter(cashier=user, closed_at__isnull=True)
        .order_by("opened_at")
        .first()
    )


def open_cash_session(
    *,
    actor: User,
    cash_register: CashRegister,
    session_id=None,
    opened_at: datetime | None = None,
    device: Device | None = None,
) -> CashSession:
    """Ouvre une caisse pour le caissier (M13) : une seule session ouverte par caisse et par
    caissier, jusqu'à la clôture. `session_id` : identifiant donné par l'appareil ; la même
    ouverture envoyée deux fois renvoie la même session.

    Hors ligne (`device`, heure de l'appareil `opened_at`, 3.5.2) : l'argent est déjà encaissé
    sur cette session, elle n'est jamais refusée (caisse prise ou désactivée entre-temps, autre
    caisse ouverte ailleurs par le caissier, 3.8.2) ; chacun clôture ensuite la sienne."""
    with transaction.atomic():
        register = CashRegister.objects.select_for_update().get(pk=cash_register.pk)
        if session_id is not None:
            same = CashSession.objects.filter(pk=session_id, cashier=actor).first()
            if same is not None:
                return same
        if device is None:
            if not register.is_active:
                raise BusinessError(CASH_REGISTER_INACTIVE)
            if open_session_of(actor) is not None:
                raise BusinessError(SESSION_ALREADY_OPEN)
            if register.sessions.filter(closed_at__isnull=True).exists():
                raise BusinessError(CASH_REGISTER_BUSY)
        session = CashSession.objects.create(
            **({"id": session_id} if session_id else {}),
            **({"opened_at": opened_at} if opened_at else {}),
            cash_register=register,
            cashier=actor,
            device=device,
            created_by=actor,
        )
        audit.record(
            Action.FINANCE_CASH_SESSION_OPENED,
            session,
            actor=actor,
            after={"cash_register": register.code},
            label=str(register),
            device_time=opened_at,
        )
    return CashSession.objects.select_related("cash_register", "cashier").get(pk=session.pk)


def payment_rate() -> tuple[ExchangeRate | None, bool]:
    """Taux des encaissements (M13) : celui de l'année en cours, sinon le dernier connu de
    l'école (`True` : à signaler au comptable)."""
    year = organisation.current_year()
    rate = current_rate(year) if year is not None else None
    if rate is not None:
        return rate, False
    rate = ExchangeRate.objects.order_by("-created_at", "-id").first()
    return rate, rate is not None


def session_totals(session: CashSession) -> list[dict]:
    """Paiements non annulés de la session, par devise (dollars d'abord), jamais additionnés."""
    rows = {
        row["received_currency"]: row
        for row in Payment.objects.filter(cash_session=session, cancellation__isnull=True)
        .values("received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"), count=Count("id"))
        .order_by()
    }
    return [
        {
            "currency": currency,
            "amount_minor": rows[currency]["amount_minor"],
            "count": rows[currency]["count"],
        }
        for currency in Currency.values
        if currency in rows
    ]


@dataclass(frozen=True)
class Part:
    """Part du montant reçu pour un frais dû, dans la devise reçue (ajustement, F2)."""

    student_charge_id: UUID
    received_minor: int


def _convert(amount_minor: int, source: str, target: str, rate: Decimal | None) -> int:
    if source == target:
        return amount_minor
    return Money(amount_minor, source).convert(target, rate).amount_minor


def _part_for(charge: StudentCharge, currency: str, rate: Decimal | None) -> int:
    """Plus grande part de la devise reçue dont la conversion ne dépasse pas le reste dû."""
    part = _convert(charge.remaining_minor, charge.currency, currency, rate)
    while part > 0 and _convert(part, currency, charge.currency, rate) > charge.remaining_minor:
        part -= 1
    return part


def allocate(
    charges: list[StudentCharge], received: Money, rate: Decimal | None, *, convert: bool = False
) -> list[tuple[StudentCharge, int, int]]:
    """Répartition par défaut (F2) des frais dus d'un élève (`charges_of`) : ceux qui restent
    à payer dans la devise reçue d'abord, puis, avec `convert`, ceux de l'autre devise (au taux
    du paiement) ; échéances les plus anciennes d'abord. Renvoie (frais, part reçue, montant dans
    la devise du frais) ; le reste éventuel du montant reçu n'est affecté à rien."""
    owed = [charge for charge in charges if charge.state and charge.remaining_minor > 0]
    ordered = [charge for charge in owed if charge.currency == received.currency]
    if convert:
        ordered += [charge for charge in owed if charge.currency != received.currency]
    left, lines = received.amount_minor, []
    for charge in ordered:
        part = min(left, _part_for(charge, received.currency, rate))
        if part > 0:
            lines.append((charge, part, _convert(part, received.currency, charge.currency, rate)))
            left -= part
    return lines


def _check_parts(
    charges: list[StudentCharge], parts: list[Part], received: Money, rate: Decimal | None
) -> list[tuple[StudentCharge, int, int]]:
    """Répartition ajustée par le caissier : des frais que l'élève doit encore, chacun une fois,
    sans dépasser son reste, et dont les parts font le montant reçu."""
    owed = {charge.pk: charge for charge in charges if charge.state and charge.remaining_minor > 0}
    lines = []
    for index, part in enumerate(parts):
        charge = owed.pop(part.student_charge_id, None)
        if charge is None:
            message = _("The student does not owe this fee, or it appears twice.")
            raise _invalid(f"allocations.{index}.student_charge", message, "not_owed")
        if charge.currency != received.currency and rate is None:
            raise BusinessError(NO_EXCHANGE_RATE)
        amount = _convert(part.received_minor, received.currency, charge.currency, rate)
        if not 0 < amount <= charge.remaining_minor:
            message = _("This part is more than what is left to pay on this fee, or too small.")
            raise _invalid(f"allocations.{index}.received_minor", message, "not_within_due")
        lines.append((charge, part.received_minor, amount))
    if sum(part for _charge, part, _amount in lines) != received.amount_minor:
        message = _("The parts must add up to the amount received.")
        raise _invalid("allocations", message, "allocations_total_mismatch")
    return lines


def _next_receipt_number(school: School, register: CashRegister, year: AcademicYear) -> str:
    """`ITIG-C1-26-000184` : école, caisse, année scolaire de l'inscription, séquence. Appelé
    sous le verrou de la caisse."""
    prefix = f"{school.code.upper()}-{register.code}-{year.starts_on:%y}-"
    last = (
        Payment.objects.filter(receipt_number__startswith=prefix)
        .order_by("-receipt_number")
        .values_list("receipt_number", flat=True)
        .first()
    )
    sequence = int(last.removeprefix(prefix)) + 1 if last else 1
    return f"{prefix}{sequence:06d}"


@dataclass(frozen=True)
class Offline:
    """Paiement encaissé hors ligne, arrivé par la synchronisation (3.3.2) : la session, le
    numéro de reçu (`ITIG-P1-26-000184`) et l'heure viennent de l'appareil."""

    device: Device
    cash_session_id: UUID
    receipt_number: str
    paid_at: datetime


def _offline_session(actor: User, offline: Offline) -> CashSession | None:
    """La session du paiement, même clôturée depuis (ailleurs, ou par une clôture arrivée
    avant) : l'argent est reçu, le reçu donné ; il n'entre pas dans l'attendu déjà figé."""
    return (
        CashSession.objects.select_related("cash_register")
        .filter(pk=offline.cash_session_id, cashier=actor)
        .first()
    )


def _rate_at(when: datetime) -> ExchangeRate | None:
    """Taux en vigueur à l'heure d'un encaissement hors ligne : le dernier fixé avant elle pour
    l'année en cours, sinon celui des encaissements en ligne."""
    year = organisation.current_year()
    rate = (
        ExchangeRate.objects.filter(academic_year=year, created_at__lte=when)
        .order_by("-created_at", "-id")
        .first()
        if year is not None
        else None
    )
    return rate or payment_rate()[0]


def _offline_number(offline: Offline, school: School, year: AcademicYear) -> str:
    """Numéro donné par l'appareil : école, préfixe de l'appareil, année scolaire de
    l'inscription, séquence de l'appareil ; jamais celui d'un autre paiement."""
    prefix = f"{school.code.upper()}-{offline.device.prefix}-{year.starts_on:%y}-"
    number = offline.receipt_number
    if not number.startswith(prefix) or not re.fullmatch(r"[0-9]{6,}", number[len(prefix) :]):
        message = _("This receipt number was not given by this device.")
        raise _invalid("receipt_number", message, "receipt_number_invalid")
    if Payment.objects.filter(receipt_number=number).exists():
        message = _("Another payment already has this receipt number.")
        raise _invalid("receipt_number", message, "receipt_number_taken")
    return number


def _same_payment(payment: Payment, enrollment: Enrollment, actor: User, received: Money) -> bool:
    return (
        payment.enrollment_id == enrollment.pk
        and payment.cashier_id == actor.pk
        and Money(payment.received_amount_minor, payment.received_currency) == received
    )


def record_payment(
    enrollment: Enrollment,
    *,
    actor: User,
    received_amount_minor: int,
    received_currency: str,
    parts: list[Part] | None = None,
    convert: bool = False,
    note: str = "",
    payment_id=None,
    offline: Offline | None = None,
) -> tuple[Payment, bool]:
    """Encaisse un paiement (F2) dans la session ouverte du caissier, au taux de `payment_rate`,
    réparti par défaut (`allocate`) ou comme l'a ajusté le caissier (`parts`). Jamais plus que
    ce que doit l'élève. Le même `payment_id` envoyé deux fois (double
    clic, nouvel essai) ne donne qu'un paiement : renvoyé avec `False`.

    Hors ligne (`offline`) : session, numéro et heure de l'appareil, taux en vigueur à cette
    heure. L'argent est déjà dans la caisse : jamais refusé parce que l'élève doit moins
    qu'avant (une autre caisse a encaissé entre-temps), ni pour une caisse ou une devise retirée
    depuis ; la répartition ajustée qui ne tient plus devient celle par défaut, et ce qui dépasse
    le dû n'est affecté à rien : c'est un crédit de l'élève (M14)."""
    school = require_current_school()
    received = Money(received_amount_minor, received_currency)
    with transaction.atomic():
        session = _offline_session(actor, offline) if offline else open_session_of(actor)
        if session is None:
            raise BusinessError(NO_OPEN_SESSION)
        # Un paiement à la fois par caisse : séquence des reçus, double envoi.
        register = CashRegister.objects.select_for_update().get(pk=session.cash_register_id)
        existing = Payment.objects.filter(pk=payment_id).first() if payment_id else None
        if existing is not None:
            if not _same_payment(existing, enrollment, actor, received):
                raise BusinessError(PAYMENT_ID_TAKEN)
            return existing, False
        if offline is None and not register.is_active:
            raise BusinessError(CASH_REGISTER_INACTIVE)
        if offline is None and received_currency not in school.enabled_currencies:
            message = _("The school does not use this currency.")
            raise _invalid("received_currency", message, "currency_not_used")
        rate = _rate_at(offline.paid_at) if offline else payment_rate()[0]
        if rate is None and (convert or len(school.enabled_currencies) > 1):
            raise BusinessError(NO_EXCHANGE_RATE)
        rate_used = rate.rate if rate is not None else None
        # Deux caisses pour le même élève : l'une après l'autre, sur des restes à jour.
        enrollment = (
            Enrollment.objects.select_related("academic_year", "student")
            .select_for_update(of=("self",))
            .get(pk=enrollment.pk)
        )
        charges = charges_of(enrollment.pk)
        if parts is not None:
            try:
                lines = _check_parts(charges, parts, received, rate_used)
            except ValidationError:
                if offline is None:
                    raise
                parts = None
        if parts is None:
            lines = allocate(charges, received, rate_used, convert=convert)
            allocated = sum(part for _charge, part, _amount in lines)
            if offline is None and allocated != received_amount_minor:
                message = _("This is more than what the student owes: give back the change.")
                raise _invalid("received_amount_minor", message, "more_than_due")

        if offline is None:
            number = _next_receipt_number(school, register, enrollment.academic_year)
        else:
            number = _offline_number(offline, school, enrollment.academic_year)
        payment = Payment.objects.create(
            **({"id": payment_id} if payment_id else {}),
            enrollment=enrollment,
            cash_session=session,
            cashier=actor,
            received_amount_minor=received_amount_minor,
            received_currency=received_currency,
            rate_used=rate_used,
            paid_at=offline.paid_at if offline else timezone.now(),
            receipt_number=number,
            note=note.strip(),
            device=offline.device if offline else None,
            synced_at=timezone.now() if offline else None,
            created_by=actor,
        )
        PaymentAllocation.objects.bulk_create(
            PaymentAllocation(
                payment=payment,
                student_charge=charge,
                received_minor=part,
                amount_minor=amount,
                created_by=actor,
            )
            for charge, part, amount in lines
        )
        audit.record(
            Action.FINANCE_PAYMENT_RECORDED,
            payment,
            actor=actor,
            device_time=offline.paid_at if offline else None,
            label=f"{number} · {enrollment.student}",
            after={
                "receipt_number": number,
                "amount_minor": received_amount_minor,
                "currency": received_currency,
                **({"rate": _rate_text(rate_used)} if rate_used is not None else {}),
                "allocations": [
                    {
                        "fee": f"{charge.fee_type.name} — {charge.label}",
                        "amount_minor": amount,
                        "currency": charge.currency,
                    }
                    for charge, _part, amount in lines
                ],
            },
        )
        surplus = received_amount_minor - sum(part for _charge, part, _amount in lines)
        if surplus > 0:
            _create_credit(
                enrollment, actor=actor, amount=Money(surplus, received_currency), source=payment
            )
    return payment, True


def receipt_payments() -> QuerySet[Payment]:
    """Paiements avec ce que montre leur reçu (`PaymentSerializer`) sans requête de plus par
    paiement : élève, classe, caisse, caissier, répartition, annulé (quand) ou en attente
    d'annulation."""
    return (
        Payment.objects.select_related(
            "enrollment__student",
            "enrollment__academic_year",
            "enrollment__class_group__level",
            "enrollment__class_group__track",
            "cash_session__cash_register",
            "cashier",
        )
        .prefetch_related(
            Prefetch(
                "allocations",
                # Lignes du reçu dans un ordre fixe : échéance la plus ancienne d'abord.
                queryset=PaymentAllocation.objects.select_related(
                    "student_charge__fee_type"
                ).order_by("student_charge__due_on", "id"),
            )
        )
        .annotate(
            cancelled_at=Subquery(
                PaymentCancellation.objects.filter(payment=OuterRef("pk")).values("approved_at")
            ),
            cancellation_pending=Exists(
                CancellationRequest.objects.filter(
                    payment=OuterRef("pk"), status=CancellationRequest.Status.PENDING
                )
            ),
        )
        .order_by("-paid_at", "-id")
    )


def reprint_payment(payment: Payment, *, actor: User, device_time: datetime | None = None) -> None:
    """Réimpression d'un reçu (F6) : un duplicata, noté au journal ; refusée pour un paiement
    annulé (son reçu n'est plus valable). Hors ligne (`device_time`, 3.5.2), le duplicata est
    déjà imprimé : toujours noté, même si le paiement a été annulé depuis la dernière
    synchronisation de l'appareil (son QR code le dit annulé)."""
    if device_time is None and PaymentCancellation.objects.filter(payment=payment).exists():
        raise BusinessError(PAYMENT_CANCELLED)
    audit.record(
        Action.FINANCE_PAYMENT_REPRINTED,
        payment,
        actor=actor,
        label=f"{payment.receipt_number} · {payment.enrollment.student}",
        device_time=device_time,
    )


# Crédits d'élèves (3.6.1, M14)

TO_PROCESS, USED, VOIDED = "to_process", "used", "voided"


def _excess(charges: list[StudentCharge]) -> dict[str, int]:
    """Payé en trop sur les frais dus (`charges_of`), par devise."""
    totals = defaultdict(int)
    for charge in charges:
        totals[charge.currency] += charge.excess_minor
    return totals


def _credit_data(credit: StudentCredit) -> dict:
    data = {"origin": credit.origin, "amount_minor": credit.amount_minor}
    if credit.source_payment_id:
        data["receipt_number"] = credit.source_payment.receipt_number
    return {**data, "currency": credit.currency}


def _create_credit(
    enrollment: Enrollment,
    *,
    actor: User,
    amount: Money,
    source: Payment | None = None,
    source_discount: Discount | None = None,
) -> StudentCredit:
    credit = StudentCredit.objects.create(
        enrollment=enrollment,
        origin=StudentCredit.Origin.OFFLINE_SURPLUS if source else StudentCredit.Origin.DISCOUNT,
        amount_minor=amount.amount_minor,
        currency=amount.currency,
        source_payment=source,
        source_discount=source_discount,
        created_by=actor,
    )
    audit.record(
        Action.FINANCE_CREDIT_CREATED,
        enrollment,
        actor=actor,
        label=str(enrollment.student),
        after=_credit_data(credit),
    )
    return credit


def _void_credit(
    credit: StudentCredit, enrollment: Enrollment, *, actor: User, at: datetime | None = None
) -> None:
    credit.voided_at, credit.voided_by = at or timezone.now(), actor
    credit.save(update_fields=["voided_at", "voided_by", "updated_at"])
    audit.record(
        Action.FINANCE_CREDIT_VOIDED,
        enrollment,
        actor=actor,
        label=str(enrollment.student),
        before=_credit_data(credit),
    )


def credits() -> QuerySet[StudentCredit]:
    """Crédits avec ce que montre l'écran (M14), sans requête de plus par crédit : élève, classe,
    paiement ou réduction d'origine, et la part déjà utilisée (`used_minor`)."""
    used = (
        CreditAllocation.objects.filter(credit=OuterRef("pk"))
        .values("credit")
        .annotate(total=Sum("amount_minor"))
        .values("total")
    )
    return StudentCredit.objects.select_related(
        "enrollment__student",
        "enrollment__class_group__level",
        "enrollment__class_group__track",
        "source_payment__cash_session__cash_register",
        "source_discount__fee_type",
    ).annotate(used_minor=Coalesce(Subquery(used), 0, output_field=BigIntegerField()))


def with_state(items: QuerySet[StudentCredit], state: str) -> QuerySet[StudentCredit]:
    """À traiter (reste à utiliser), utilisés (en entier) ou annulés (réduction retirée)."""
    if state == VOIDED:
        return items.filter(voided_at__isnull=False)
    live = items.filter(voided_at__isnull=True)
    if state == USED:
        return live.filter(used_minor__gte=F("amount_minor"))
    return live.filter(used_minor__lt=F("amount_minor"))


def open_credits(enrollments: list) -> list[StudentCredit]:
    """Crédits à traiter de ces inscriptions, les plus anciens d'abord (une requête) : ceux que
    la caisse propose (3.6.2)."""
    items = with_state(credits().filter(enrollment_id__in=enrollments), TO_PROCESS)
    return list(items.order_by("created_at", "id"))


def credit_uses(enrollments: list) -> list[CreditAllocation]:
    """Parts de crédit utilisées de ces inscriptions, avec l'annulation du crédit (une
    requête) : un duplicata fait sur l'appareil les compte comme `balance_after` (3.8.3)."""
    return list(
        CreditAllocation.objects.filter(credit__enrollment_id__in=enrollments)
        .select_related("credit")
        .order_by("created_at", "id")
    )


def credit_state(credit: StudentCredit) -> str:
    if credit.voided_at is not None:
        return VOIDED
    return USED if credit.used_minor >= credit.amount_minor else TO_PROCESS


def credit_proposal(credit: StudentCredit) -> list[tuple[StudentCharge, int, int]]:
    """Ce que ferait « Utiliser le crédit » : son reste sur les échéances de sa devise que
    l'élève doit encore, les plus anciennes d'abord (comme à la caisse)."""
    if credit_state(credit) != TO_PROCESS:
        return []
    left = Money(credit.amount_minor - credit.used_minor, credit.currency)
    return allocate(charges_of(credit.enrollment_id), left, None)


def credits_summary(year: AcademicYear) -> dict:
    """Chiffres de l'écran : crédits à traiter, leur reste par devise, crédits utilisés depuis le
    début du mois (dans le fuseau de l'école)."""
    items = credits().filter(enrollment__academic_year=year)
    open_credits = with_state(items, TO_PROCESS)
    amounts = (
        open_credits.values("currency")
        .annotate(amount_minor=Sum(F("amount_minor") - F("used_minor")))
        .order_by("currency")
    )
    month = datetime.combine(today().replace(day=1), time.min, timezone.get_current_timezone())
    used = CreditAllocation.objects.filter(
        created_at__gte=month, credit__enrollment__academic_year=year
    )
    return {
        "to_process": open_credits.count(),
        "amounts": sorted(amounts, key=lambda row: Currency.values.index(row["currency"])),
        "used_this_month": used.values("credit").distinct().count(),
    }


def use_credit(credit: StudentCredit, *, actor: User) -> StudentCredit:
    """Utilise un crédit (M14) : son reste va aux échéances de sa devise que l'élève doit
    encore, les plus anciennes d'abord, sans paiement ni reçu (les totaux de caisse ne bougent
    pas). Ce qui dépasse ce qu'il doit reste à traiter ; rien n'est converti vers l'autre
    devise."""
    with transaction.atomic():
        # Comme un paiement : l'un après l'autre pour un même élève, sur des restes à jour.
        enrollment = (
            Enrollment.objects.select_related("student")
            .select_for_update(of=("self",))
            .get(pk=credit.enrollment_id)
        )
        credit = credits().select_for_update(of=("self",)).get(pk=credit.pk)
        state = credit_state(credit)
        if state != TO_PROCESS:
            raise BusinessError(CREDIT_VOIDED if state == VOIDED else CREDIT_USED)
        lines = credit_proposal(credit)
        if not lines:
            raise BusinessError(NOTHING_OWED)
        CreditAllocation.objects.bulk_create(
            CreditAllocation(
                credit=credit, student_charge=charge, amount_minor=amount, created_by=actor
            )
            for charge, _part, amount in lines
        )
        sync_changes.touch_enrollments([enrollment.pk])
        audit.record(
            Action.FINANCE_CREDIT_USED,
            enrollment,
            actor=actor,
            label=str(enrollment.student),
            after={
                "amount_minor": sum(amount for _charge, _part, amount in lines),
                "currency": credit.currency,
                "allocations": [
                    {"fee": f"{charge.fee_type.name} — {charge.label}", "amount_minor": amount}
                    for charge, _part, amount in lines
                ],
            },
        )
    return credit


# Annulations (3.8.1, F7)


def cancellation_requests() -> QuerySet[CancellationRequest]:
    """Demandes avec ce que montre l'écran (F7) sans requête de plus par demande : paiement
    (élève, classe, caisse, caissier, répartition), demandeur, décideur, annulation validée."""
    return CancellationRequest.objects.select_related(
        "payment__enrollment__student",
        "payment__enrollment__academic_year",
        "payment__enrollment__class_group__level",
        "payment__enrollment__class_group__track",
        "payment__cash_session__cash_register",
        "payment__cashier",
        "payment__cancellation__approved_by",
        "requested_by",
        "decided_by",
    ).prefetch_related(
        Prefetch(
            "payment__allocations",
            queryset=PaymentAllocation.objects.select_related("student_charge__fee_type"),
        )
    )


def _request_label(payment: Payment) -> str:
    return f"{payment.receipt_number} · {payment.enrollment.student}"


def _payment_data(payment: Payment) -> dict:
    return {
        "receipt_number": payment.receipt_number,
        "amount_minor": payment.received_amount_minor,
        "currency": payment.received_currency,
    }


def request_cancellation(
    payment: Payment,
    *,
    actor: User,
    reason: str,
    request_id=None,
    device: Device | None = None,
    requested_at: datetime | None = None,
) -> tuple[CancellationRequest, bool]:
    """Demande l'annulation d'un paiement (F7) avec son motif ; le paiement compte jusqu'à la
    décision. Hors ligne (`device`, `requested_at` : heure de l'appareil). Le même `request_id`
    envoyé deux fois ne donne qu'une demande : renvoyée avec `False`. 409 pour un paiement déjà
    annulé ou dont l'annulation attend déjà une décision."""
    reason = reason.strip()
    if not reason:
        raise _invalid("reason", _("This field may not be blank."), "blank")
    with transaction.atomic():
        # Une demande à la fois par paiement.
        payment = (
            Payment.objects.select_related("enrollment__student")
            .select_for_update(of=("self",))
            .get(pk=payment.pk)
        )
        existing = CancellationRequest.objects.filter(pk=request_id).first() if request_id else None
        if existing is not None:
            if existing.payment_id != payment.pk or existing.requested_by_id != actor.pk:
                raise BusinessError(CANCELLATION_ID_TAKEN)
            return existing, False
        if PaymentCancellation.objects.filter(payment=payment).exists():
            raise BusinessError(PAYMENT_CANCELLED)
        pending = CancellationRequest.Status.PENDING
        if CancellationRequest.objects.filter(payment=payment, status=pending).exists():
            raise BusinessError(CANCELLATION_PENDING)
        request = CancellationRequest.objects.create(
            **({"id": request_id} if request_id else {}),
            payment=payment,
            reason=reason,
            requested_by=actor,
            requested_at=requested_at or timezone.now(),
            device=device,
            created_by=actor,
        )
        audit.record(
            Action.FINANCE_CANCELLATION_REQUESTED,
            payment,
            actor=actor,
            device_time=requested_at if device else None,
            label=_request_label(payment),
            after={**_payment_data(payment), "reason": reason},
        )
    return request, True


def _next_cancellation_number(school: School, year: AcademicYear) -> str:
    """`ITIG-AN-26-000007` : école, série des annulations, année scolaire de l'inscription,
    séquence. Appelé sous le verrou de l'école."""
    prefix = f"{school.code.upper()}-{CANCELLATION_SERIES}-{year.starts_on:%y}-"
    last = (
        PaymentCancellation.objects.filter(receipt_number__startswith=prefix)
        .order_by("-receipt_number")
        .values_list("receipt_number", flat=True)
        .first()
    )
    sequence = int(last.removeprefix(prefix)) + 1 if last else 1
    return f"{prefix}{sequence:06d}"


def _void_discount_credits(
    enrollment: Enrollment, currency: str, gone: int, *, actor: User, at: datetime
) -> None:
    """Le trop-payé disparu avec un paiement annulé (tranche payée puis réduite, M14) : les
    crédits de réduction de cette devise sont annulés à hauteur de `gone`, les plus récents
    d'abord ; ce qu'un crédit a en plus redevient un crédit de la même réduction."""
    live = StudentCredit.objects.filter(
        enrollment=enrollment,
        currency=currency,
        origin=StudentCredit.Origin.DISCOUNT,
        voided_at__isnull=True,
    ).order_by("-created_at", "-id")
    for credit in live.select_for_update():
        if gone <= 0:
            return
        _void_credit(credit, enrollment, actor=actor, at=at)
        if credit.amount_minor > gone:
            _create_credit(
                enrollment,
                actor=actor,
                amount=Money(credit.amount_minor - gone, currency),
                source_discount=credit.source_discount,
            )
        gone -= credit.amount_minor


def _decided_request(request: CancellationRequest) -> CancellationRequest:
    request = (
        CancellationRequest.objects.select_related("payment__enrollment__student")
        .select_for_update(of=("self",))
        .get(pk=request.pk)
    )
    if request.status != CancellationRequest.Status.PENDING:
        raise BusinessError(CANCELLATION_DECIDED)
    return request


def approve_cancellation(
    request: CancellationRequest, *, actor: User, note: str = ""
) -> PaymentCancellation:
    """Valide une demande (F7), jamais la sienne : le paiement est annulé (ses allocations ne
    comptent plus), avec un reçu d'annulation numéroté. Les crédits qu'il a donnés sont annulés
    aussi : son surplus hors ligne, et les crédits de réduction à hauteur du trop-payé qui
    disparaît avec lui. L'argent est rendu au parent (ou encaissé pour le bon élève)."""
    school = require_current_school()
    with transaction.atomic():
        request = _decided_request(request)
        if request.requested_by_id == actor.pk:
            raise BusinessError(OWN_CANCELLATION)
        payment = request.payment
        # Comme un paiement : l'un après l'autre pour un même élève, sur des restes à jour.
        enrollment = (
            Enrollment.objects.select_related("academic_year", "student")
            .select_for_update(of=("self",))
            .get(pk=payment.enrollment_id)
        )
        before = _excess(charges_of(enrollment.pk))
        # Séquence des reçus d'annulation de l'école.
        School.objects.select_for_update().get(pk=school.pk)
        now = timezone.now()
        cancellation = PaymentCancellation.objects.create(
            payment=payment,
            receipt_number=_next_cancellation_number(school, enrollment.academic_year),
            reason=request.reason,
            requested_by_id=request.requested_by_id,
            approved_by=actor,
            approved_at=now,
            created_by=actor,
        )
        request.status = CancellationRequest.Status.APPROVED
        request.decided_by, request.decided_at = actor, now
        request.decision_note = note.strip()
        request.save(
            update_fields=["status", "decided_by", "decided_at", "decision_note", "updated_at"]
        )
        audit.record(
            Action.FINANCE_PAYMENT_CANCELLED,
            payment,
            actor=actor,
            label=_request_label(payment),
            before=_payment_data(payment),
            after={
                "cancellation_receipt_number": cancellation.receipt_number,
                "reason": request.reason,
                **({"note": request.decision_note} if request.decision_note else {}),
            },
        )
        surplus = StudentCredit.objects.filter(source_payment=payment, voided_at__isnull=True)
        for credit in surplus.select_for_update():
            _void_credit(credit, enrollment, actor=actor, at=now)
        after = _excess(charges_of(enrollment.pk))
        for currency, excess in before.items():
            gone = excess - after.get(currency, 0)
            if gone > 0:
                _void_discount_credits(enrollment, currency, gone, actor=actor, at=now)
    return cancellation


def reject_cancellation(
    request: CancellationRequest, *, actor: User, note: str = ""
) -> CancellationRequest:
    """Refuse une demande (F7) : le paiement reste valable ; une autre demande reste possible."""
    with transaction.atomic():
        request = _decided_request(request)
        request.status = CancellationRequest.Status.REJECTED
        request.decided_by, request.decided_at = actor, timezone.now()
        request.decision_note = note.strip()
        request.save(
            update_fields=["status", "decided_by", "decided_at", "decision_note", "updated_at"]
        )
        audit.record(
            Action.FINANCE_CANCELLATION_REJECTED,
            request.payment,
            actor=actor,
            label=_request_label(request.payment),
            after={"reason": request.reason, "note": request.decision_note},
        )
    return request


def reprint_cancellation(cancellation: PaymentCancellation, *, actor: User) -> None:
    """Réimpression d'un reçu d'annulation : un duplicata, noté au journal."""
    audit.record(
        Action.FINANCE_CANCELLATION_REPRINTED,
        cancellation.payment,
        actor=actor,
        label=f"{cancellation.receipt_number} · {cancellation.payment.enrollment.student}",
    )


# Clôture de caisse (F8, 3.8.2)


def _in_till_at(payments: QuerySet[Payment], until: datetime) -> QuerySet[Payment]:
    """Paiements encore dans la caisse à `until` : pas annulés, ou annulés après."""
    return payments.filter(Q(cancellation__isnull=True) | Q(cancellation__approved_at__gt=until))


def closing_summary(session: CashSession, *, until: datetime | None = None) -> dict:
    """Ce que montre la clôture (maquette `caisse-cloture`). Par devise (celles de l'école et
    celles des paiements, dollars d'abord, jamais additionnées), l'attendu : paiements de la
    session pas annulés à `until` (l'heure de clôture, sinon maintenant). Le détail par type de
    frais, dans la devise reçue, avec à part le trop-perçu devenu crédit de l'élève (`fee_type`
    vide). Reçus donnés (annulés compris), annulations validées et en attente ; la clôture une
    fois faite."""
    until = until or session.closed_at or timezone.now()
    school = require_current_school()
    closings = list(
        CashClosing.objects.filter(cash_session=session).select_related("closed_by", "device")
    )
    payments = Payment.objects.filter(cash_session=session)
    if closings:
        # Ce que la clôture a compté : les paiements reçus avant elle ; ceux arrivés après
        # (encaissés hors ligne sur un autre appareil) sont à part (`late_payments`).
        payments = payments.filter(created_at__lte=_received(closings))
    kept = _in_till_at(payments, until)
    expected = {
        row["received_currency"]: row
        for row in kept.values("received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"), count=Count("id"))
        .order_by()
    }
    currencies = [
        currency
        for currency in Currency.values
        if currency in expected or currency in school.enabled_currencies
    ]
    fee_rows = (
        PaymentAllocation.objects.filter(payment__in=kept)
        .values("student_charge__fee_type__name", "payment__received_currency")
        .annotate(amount_minor=Sum("received_minor"))
        .order_by("student_charge__fee_type__name")
    )
    fee_types = [
        {
            "fee_type": row["student_charge__fee_type__name"],
            "currency": row["payment__received_currency"],
            "amount_minor": row["amount_minor"],
        }
        for row in fee_rows
    ]
    for currency, row in expected.items():
        allocated = sum(item["amount_minor"] for item in fee_types if item["currency"] == currency)
        if row["amount_minor"] > allocated:
            fee_types.append(
                {
                    "fee_type": None,
                    "currency": currency,
                    "amount_minor": row["amount_minor"] - allocated,
                }
            )
    cancelled = {
        row["received_currency"]: row
        for row in payments.filter(cancellation__approved_at__lte=until)
        .values("received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"), count=Count("id"))
        .order_by()
    }
    receipts = list(payments.order_by("paid_at", "receipt_number").values_list("receipt_number"))
    return {
        "session": session,
        "currencies": [
            {
                "currency": currency,
                "expected_minor": expected[currency]["amount_minor"] if currency in expected else 0,
                "count": expected[currency]["count"] if currency in expected else 0,
            }
            for currency in currencies
        ],
        "fee_types": fee_types,
        "payments_count": len(receipts),
        "first_receipt": receipts[0][0] if receipts else None,
        "last_receipt": receipts[-1][0] if receipts else None,
        "cancelled": [
            {"currency": currency, **{k: cancelled[currency][k] for k in ("amount_minor", "count")}}
            for currency in Currency.values
            if currency in cancelled
        ],
        "cancellations_pending": CancellationRequest.objects.filter(
            payment__in=payments, status=CancellationRequest.Status.PENDING
        ).count(),
        "closing": _closing_data(closings) if closings else None,
    }


def _received(closings: list[CashClosing]) -> datetime:
    """Arrivée de la clôture au serveur (ses lignes sont écrites ensemble)."""
    return min(line.created_at for line in closings)


def _by_currency(lines: list[CashClosing]) -> list[CashClosing]:
    """Dollars d'abord, comme partout."""
    return sorted(lines, key=lambda line: Currency.values.index(line.currency))


def _closing_data(closings: list[CashClosing]) -> dict:
    first = closings[0]
    return {
        "lines": _by_currency(closings),
        "note": first.note,
        "closed_at": first.closed_at,
        "closed_by": first.closed_by,
        "offline": first.device_id is not None,
        "received_at": _received(closings),
    }


def close_cash_session(
    session: CashSession,
    *,
    actor: User,
    counted: dict[str, int],
    note: str = "",
    closed_at: datetime | None = None,
    device: Device | None = None,
) -> list[CashClosing]:
    """Clôture la session (F8) : par devise, l'attendu (`closing_summary` à l'heure de
    clôture), le compté et l'écart, figés ; plus d'encaissement en ligne dans cette session.
    Seul son caissier la clôture. En ligne, l'argent de chaque devise est compté et un écart est
    expliqué. Hors ligne (`device`, heure de l'appareil `closed_at`) : l'argent est déjà compté,
    rien n'est refusé (une devise pas comptée l'est à zéro, l'écart se voit)."""
    note = note.strip()
    with transaction.atomic():
        session = CashSession.objects.select_for_update().get(pk=session.pk)
        if session.cashier_id != actor.pk:
            raise BusinessError(NOT_YOUR_SESSION)
        if session.closed_at is not None:
            raise BusinessError(SESSION_CLOSED)
        when = closed_at or timezone.now()
        expected = {
            row["currency"]: row["expected_minor"]
            for row in closing_summary(session, until=when)["currencies"]
        }
        if device is None and set(counted) != set(expected):
            message = _("Count the money of each currency.")
            raise _invalid("counted", message, "counted_currencies")
        lines = [
            (currency, expected.get(currency, 0), counted.get(currency, 0))
            for currency in Currency.values
            if currency in expected or currency in counted
        ]
        if device is None and not note and any(want != got for _c, want, got in lines):
            message = _("Explain the difference: the accountant will see it.")
            raise _invalid("note", message, "note_required")
        closings = CashClosing.objects.bulk_create(
            CashClosing(
                cash_session=session,
                currency=currency,
                expected_minor=want,
                counted_minor=got,
                difference_minor=got - want,
                note=note,
                closed_by=actor,
                closed_at=when,
                device=device,
                created_by=actor,
            )
            for currency, want, got in lines
        )
        session.closed_at = when
        session.save(update_fields=["closed_at", "updated_at"])
        audit.record(
            Action.FINANCE_CASH_SESSION_CLOSED,
            session,
            actor=actor,
            device_time=closed_at if device else None,
            label=str(session.cash_register),
            after={
                "amounts": [
                    {
                        "currency": currency,
                        "expected_minor": want,
                        "counted_minor": got,
                        "difference_minor": got - want,
                    }
                    for currency, want, got in lines
                ],
                **({"note": note} if note else {}),
            },
        )
    return closings


# Clôtures vues par le comptable (M16, 3.8.3)

OPEN, UNCLOSED, BALANCED, DIFFERENCE = "open", "unclosed", "ok", "difference"


def month_range(month: date) -> tuple[datetime, datetime]:
    """Début et fin (exclue) du mois de `month`, dans le fuseau de l'école."""
    start = timezone.make_aware(datetime(month.year, month.month, 1))
    following = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return start, timezone.make_aware(datetime.combine(following, time()))


def cash_sessions(month: date, cash_register: CashRegister | None = None) -> QuerySet:
    """Sessions de caisse ouvertes dans le mois (tous les caissiers), les plus récentes
    d'abord, avec leur nombre de paiements (reçus donnés, annulés compris)."""
    start, end = month_range(month)
    sessions = CashSession.objects.filter(opened_at__gte=start, opened_at__lt=end)
    if cash_register is not None:
        sessions = sessions.filter(cash_register=cash_register)
    return (
        sessions.select_related("cash_register", "cashier")
        .annotate(payments_count=Count("payments"))
        .order_by("-opened_at", "cash_register__code")
    )


def _session_state(session: CashSession, closings: list[CashClosing]) -> str:
    if closings:
        return DIFFERENCE if any(line.difference_minor for line in closings) else BALANCED
    return OPEN if timezone.localdate(session.opened_at) >= today() else UNCLOSED


def _late(sessions: list[CashSession]) -> QuerySet[Payment]:
    """Paiements pas annulés de ces sessions arrivés au serveur après leur clôture."""
    received = (
        CashClosing.objects.filter(cash_session=OuterRef("cash_session"))
        .order_by("created_at")
        .values("created_at")[:1]
    )
    return (
        Payment.objects.filter(cash_session__in=sessions, cancellation__isnull=True)
        .annotate(closing_received=Subquery(received))
        .filter(created_at__gt=F("closing_received"))
    )


def with_closings(sessions: list[CashSession]) -> list[CashSession]:
    """Ajoute à chaque session son état, ses lignes par devise (`lines` : attendu, compté et
    écart figés à la clôture ; session ouverte : attendu à cette heure, rien de compté) et ses
    paiements arrivés après la clôture par devise (`late`). Trois requêtes pour la page."""
    closings: dict[UUID, list[CashClosing]] = defaultdict(list)
    for line in CashClosing.objects.filter(cash_session__in=sessions):
        closings[line.cash_session_id].append(line)
    live: dict[UUID, dict[str, int]] = defaultdict(dict)
    for row in (
        Payment.objects.filter(
            cash_session__in=[s for s in sessions if s.pk not in closings],
            cancellation__isnull=True,
        )
        .values("cash_session", "received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"))
        .order_by()
    ):
        live[row["cash_session"]][row["received_currency"]] = row["amount_minor"]
    late: dict[UUID, list[dict]] = defaultdict(list)
    for row in (
        _late([s for s in sessions if s.pk in closings])
        .values("cash_session", "received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"), count=Count("id"))
        .order_by()
    ):
        late[row["cash_session"]].append(
            {"currency": row["received_currency"], **{k: row[k] for k in ("amount_minor", "count")}}
        )
    enabled = require_current_school().enabled_currencies
    for session in sessions:
        lines = closings[session.pk]
        session.state = _session_state(session, lines)
        session.late = sorted(late[session.pk], key=lambda r: Currency.values.index(r["currency"]))
        if lines:
            session.lines = _by_currency(lines)
            continue
        amounts = live[session.pk]
        session.lines = [
            {
                "currency": currency,
                "expected_minor": amounts.get(currency, 0),
                "counted_minor": None,
                "difference_minor": None,
            }
            for currency in Currency.values
            if currency in amounts or currency in enabled
        ]
    return sessions


def closings_summary(month: date, cash_register: CashRegister | None = None) -> dict:
    """Chiffres de l'écran pour le mois : sessions et caisses, écart net par devise de l'école
    (et nombre de sessions avec un écart), les caisses de l'école (filtre) et toutes les
    sessions pas clôturées ouvertes avant aujourd'hui, quel que soit le mois (bandeau)."""
    sessions = cash_sessions(month, cash_register)
    differences = {
        row["currency"]: row
        for row in CashClosing.objects.filter(cash_session__in=sessions.values("pk"))
        .values("currency")
        .annotate(
            total_minor=Sum("difference_minor"),
            sessions=Count("cash_session", filter=~Q(difference_minor=0)),
        )
        .order_by()
    }
    enabled = require_current_school().enabled_currencies
    start_of_today = timezone.make_aware(datetime.combine(today(), time()))
    return {
        "sessions": sessions.count(),
        "cash_registers": sessions.values("cash_register").distinct().count(),
        "differences": [
            {
                "currency": currency,
                "difference_minor": differences.get(currency, {}).get("total_minor", 0),
                "sessions": differences.get(currency, {}).get("sessions", 0),
            }
            for currency in Currency.values
            if currency in differences or currency in enabled
        ],
        "registers": list(CashRegister.objects.order_by("code")),
        "unclosed": list(
            CashSession.objects.filter(closed_at__isnull=True, opened_at__lt=start_of_today)
            .select_related("cash_register", "cashier")
            .order_by("opened_at")
        ),
    }


def closing_detail(session: CashSession) -> dict:
    """La clôture de la session vue par le comptable : `closing_summary` (ce qu'imprime le
    bordereau), son état et les paiements arrivés après la clôture, annulés compris."""
    [session] = with_closings([session])
    summary = closing_summary(session)
    late = []
    if summary["closing"]:
        late = list(
            Payment.objects.filter(
                cash_session=session, created_at__gt=summary["closing"]["received_at"]
            )
            .select_related("enrollment__student")
            .annotate(cancelled=Exists(PaymentCancellation.objects.filter(payment=OuterRef("pk"))))
            .order_by("paid_at", "receipt_number")
        )
    return {**summary, "state": session.state, "late_payments": late}

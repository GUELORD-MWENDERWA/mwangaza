"""Sorties de caisse (FIN.2, `docs/04` § 4) : une dépense validée, à payer en espèces, sort de la
session de caisse ouverte du caissier, avec un bon numéroté et signé. La clôture la déduit de
l'attendu (`services.closing_summary`). Montants en entiers + devise, ceux de la dépense : rien
n'est converti (skill `argent`).

En ligne, l'argent doit être dans la caisse : une sortie ne dépasse pas ce que la session a reçu
dans cette devise (il n'y a pas de fond de caisse). Rien ne s'efface : annuler écrit une
`CashOutCancellation`, seulement tant que la session est ouverte (le caissier remet l'argent
dans sa caisse) ; la dépense redevient « à payer ».

Hors ligne (`OfflineCashOut`, opération `cash_out.create`) : l'argent est déjà sorti et le bon
signé, avec le numéro de l'appareil (`ITIG-P1-26-S0003`). Rien n'est refusé pour l'argent de la
caisse (l'attendu peut devenir négatif), une session clôturée depuis ou une dépense payée ou
annulée entre-temps : la sortie est gardée, et l'écart noté au journal (`conflict`)."""

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.finance import services
from apps.finance.expenses import EXPENSE_CANCELLED
from apps.finance.models import (
    CashOut,
    CashOutCancellation,
    CashRegister,
    CashSession,
    Expense,
    ExpenseCancellation,
)
from apps.schools import organisation
from apps.schools.models import School
from apps.sync.models import Device

CASH_OUT_ID_TAKEN = ApiError(
    "cash_out_id_taken", _("This identifier belongs to another cash-out."), 409
)
NOT_PAYABLE_IN_CASH = ApiError(
    "expense_not_payable_in_cash",
    _("Only an approved expense to be paid from the cash desk leaves the cash desk."),
    409,
)
EXPENSE_ALREADY_PAID = ApiError("expense_already_paid", _("This expense is already paid."), 409)
NOT_ENOUGH_CASH = ApiError(
    "not_enough_cash",
    _("There is not enough money of this currency in the cash desk for this expense."),
    409,
)
CASH_OUT_CANCELLED = ApiError("cash_out_cancelled", _("This cash-out is already cancelled."), 409)
CASH_OUT_SESSION_CLOSED = ApiError(
    "cash_out_session_closed",
    _("The cash session is closed: this cash-out can no longer be cancelled."),
    409,
)
OFFLINE_SESSION_UNKNOWN = ApiError(
    "cash_out_session_unknown", _("This cash-out comes from a session that is not yours."), 409
)
NUMBER_INVALID = ApiError(
    "cash_out_number_invalid", _("This slip number was not given by this device."), 409
)
NUMBER_TAKEN = ApiError(
    "cash_out_number_taken", _("Another cash-out already has this slip number."), 409
)


@dataclass(frozen=True)
class OfflineCashOut:
    """Sortie faite sur l'appareil, arrivée par la synchronisation : session, numéro du bon et
    heure de l'appareil."""

    device: Device
    cash_session_id: UUID
    number: str
    paid_at: datetime


def cash_outs():
    return CashOut.objects.select_related(
        "expense__category", "cash_session__cash_register", "cash_session__cashier", "cancellation"
    )


def payable_expenses():
    """Dépenses validées à payer en espèces, pas annulées : ce que la caisse peut sortir."""
    return (
        Expense.objects.select_related("category")
        .filter(
            status=Expense.Status.APPROVED,
            account=Expense.Account.CASH,
            cancellation__isnull=True,
        )
        .order_by("spent_on", "number")
    )


def _data(cash_out: CashOut) -> dict:
    return {
        "number": cash_out.number,
        "expense": cash_out.expense.number,
        "amount_minor": cash_out.amount_minor,
        "currency": cash_out.currency,
        "received_by": cash_out.received_by,
        "cash_register": cash_out.cash_session.cash_register.code,
    }


def _next_number(school: School, register: CashRegister) -> str:
    """`ITIG-C1-26-S0007` : école, caisse, année scolaire en cours (sinon l'année civile), « S »
    et la suite. Appelé sous le verrou de la caisse ; une sortie ne s'efface jamais."""
    year = organisation.current_year()
    yy = year.starts_on if year is not None else timezone.localdate()
    prefix = f"{school.code.upper()}-{register.code}-{yy:%y}-S"
    count = CashOut.objects.filter(number__startswith=prefix).count()
    return f"{prefix}{count + 1:04d}"


def _offline_number(school: School, offline: OfflineCashOut) -> str:
    """Numéro donné par l'appareil : école, préfixe de l'appareil (jamais le code d'une caisse),
    année, « S » et la séquence de l'appareil ; jamais celui d'une autre sortie."""
    prefix = re.escape(f"{school.code.upper()}-{offline.device.prefix}-")
    if not re.fullmatch(rf"{prefix}[0-9]{{2}}-S[0-9]{{4,}}", offline.number):
        raise BusinessError(NUMBER_INVALID)
    if CashOut.objects.filter(number=offline.number).exists():
        raise BusinessError(NUMBER_TAKEN)
    return offline.number


def device_sequence(device: Device) -> int:
    """Dernière séquence de bon donnée par l'appareil, rendue à l'instantané : un appareil
    réinstallé ne redonne pas un numéro que le serveur connaît (les opérations arrivent dans
    l'ordre : la dernière reçue a le plus grand)."""
    last = (
        CashOut.objects.filter(device=device)
        .order_by("-created_at")
        .values_list("number", flat=True)
        .first()
    )
    return int(last.rsplit("S", 1)[1]) if last else 0


def _conflict(expense: Expense, cancelled: bool) -> str | None:
    """Ce qui aurait refusé la sortie en ligne : gardée hors ligne, l'argent est parti."""
    if cancelled:
        return "expense_cancelled"
    if expense.status == Expense.Status.PAID:
        return "already_paid"
    if expense.status != Expense.Status.APPROVED or expense.account != Expense.Account.CASH:
        return "not_payable"
    return None


def record_cash_out(
    *,
    actor: User,
    expense: Expense,
    received_by: str,
    cash_out_id=None,
    offline: OfflineCashOut | None = None,
) -> tuple[CashOut, bool]:
    """Payer en espèces une dépense validée, depuis la session ouverte du caissier. Rejouer le
    même `cash_out_id` rend la sortie déjà enregistrée (`created` faux). Hors ligne
    (`offline`) : la session, le numéro et l'heure de l'appareil, jamais refusée pour l'argent
    (voir le module)."""
    school = require_current_school()
    with transaction.atomic():
        if cash_out_id is not None:
            existing = cash_outs().filter(pk=cash_out_id).first()
            if existing is not None:
                if existing.created_by_id != actor.pk or existing.expense_id != expense.pk:
                    raise BusinessError(CASH_OUT_ID_TAKEN)
                return existing, False
        if offline is not None:
            # Même clôturée depuis : l'argent est sorti, la clôture le montre à part.
            session = CashSession.objects.filter(pk=offline.cash_session_id, cashier=actor).first()
            if session is None:
                raise BusinessError(OFFLINE_SESSION_UNKNOWN)
        else:
            session = services.open_session_of(actor)
            if session is None:
                raise BusinessError(services.NO_OPEN_SESSION)
        # Même ordre de verrous que l'encaissement (la caisse) puis la clôture (la session).
        register = CashRegister.objects.select_for_update().get(pk=session.cash_register_id)
        session = CashSession.objects.select_for_update().get(pk=session.pk)
        expense = Expense.objects.select_for_update(of=("self",)).get(pk=expense.pk)
        cancelled = ExpenseCancellation.objects.filter(expense=expense).exists()
        conflict = None
        if offline is not None:
            conflict = _conflict(expense, cancelled)
            number = _offline_number(school, offline)
        else:
            if session.closed_at is not None:
                raise BusinessError(services.SESSION_CLOSED)
            if cancelled:
                raise BusinessError(EXPENSE_CANCELLED)
            if expense.account != Expense.Account.CASH:
                raise BusinessError(NOT_PAYABLE_IN_CASH)
            if expense.status == Expense.Status.PAID:
                raise BusinessError(EXPENSE_ALREADY_PAID)
            if expense.status != Expense.Status.APPROVED:
                raise BusinessError(NOT_PAYABLE_IN_CASH)
            if services.till(session).get(expense.currency, 0) < expense.amount_minor:
                raise BusinessError(NOT_ENOUGH_CASH)
            number = _next_number(school, register)
        cash_out = CashOut(
            expense=expense,
            cash_session=session,
            number=number,
            amount_minor=expense.amount_minor,
            currency=expense.currency,
            received_by=received_by,
            created_by=actor,
        )
        if cash_out_id is not None:
            cash_out.pk = cash_out_id
        if offline is not None:
            cash_out.paid_at, cash_out.device = offline.paid_at, offline.device
        cash_out.save()
        if conflict is None:
            expense.status = Expense.Status.PAID
            expense.paid_at = cash_out.paid_at
            expense.save(update_fields=["status", "paid_at", "updated_at"])
        audit.record(
            Action.FINANCE_CASH_OUT_RECORDED,
            cash_out,
            actor=actor,
            after={**_data(cash_out), **({"conflict": conflict} if conflict else {})},
            label=f"{cash_out.number} · {expense.number}",
            device_time=offline.paid_at if offline else None,
        )
    return cash_outs().get(pk=cash_out.pk), True


def cancel_cash_out(cash_out: CashOut, *, actor: User, reason: str) -> CashOutCancellation:
    """Annuler une sortie tant que sa session est ouverte : l'argent revient dans la caisse et la
    dépense redevient « à payer » (sauf si une autre sortie la paie encore)."""
    with transaction.atomic():
        session = CashSession.objects.select_for_update().get(pk=cash_out.cash_session_id)
        if session.closed_at is not None:
            raise BusinessError(CASH_OUT_SESSION_CLOSED)
        expense = Expense.objects.select_for_update(of=("self",)).get(pk=cash_out.expense_id)
        if CashOutCancellation.objects.filter(cash_out=cash_out).exists():
            raise BusinessError(CASH_OUT_CANCELLED)
        cancellation = CashOutCancellation.objects.create(
            cash_out=cash_out, reason=reason, cancelled_by=actor, created_by=actor
        )
        still_paid = (
            CashOut.objects.filter(expense=expense, cancellation__isnull=True)
            .exclude(pk=cash_out.pk)
            .exists()
        )
        if expense.status == Expense.Status.PAID and not still_paid:
            expense.status = Expense.Status.APPROVED
            expense.paid_at = None
            expense.save(update_fields=["status", "paid_at", "updated_at"])
        audit.record(
            Action.FINANCE_CASH_OUT_CANCELLED,
            cash_out,
            actor=actor,
            before=_data(cash_out),
            after={"cancelled": True, "reason": reason},
            label=f"{cash_out.number} · {expense.number}",
        )
    return cancellation

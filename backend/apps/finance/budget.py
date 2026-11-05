"""Budget et rapports (FIN.3, `docs/04` § 4) : budget prévu par catégorie, réalisé contre prévu,
entrées et sorties par mois, comptes de l'école (caisse, banque, Mobile Money) et export Excel.

Tout est par devise, jamais converti : un tableau en dollars, un en francs. Entrées = paiements
reçus à la caisse, non annulés (les paiements repris d'avant l'application sont dans le solde de
départ). Sorties = dépenses payées, non annulées, comptées à leur date. Chaque chiffre vient d'un
agrégat SQL : quelques requêtes par écran, quel que soit le nombre de paiements."""

from collections import defaultdict
from datetime import date
from io import BytesIO

from django.db import transaction
from django.db.models import BigIntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import formats
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.money import Currency, Money
from apps.core.tenancy import require_current_school
from apps.finance.models import (
    BudgetLine,
    Expense,
    ExpenseCategory,
    Payment,
    TreasuryMovement,
    TreasuryMovementCancellation,
)
from apps.schools.models import AcademicYear, School

OPENING_EXISTS = ApiError(
    "opening_balance_exists",
    _("This account already has an opening balance in this currency: cancel it first."),
    409,
)
MOVEMENT_CANCELLED = ApiError(
    "treasury_movement_cancelled", _("This movement is already cancelled."), 409
)
CURRENCY_NOT_USED = ApiError("currency_not_used", _("The school does not use this currency."), 400)

Account = Expense.Account
Kind = TreasuryMovement.Kind


def currencies(school: School, present=()) -> list[str]:
    """Devises de l'école et celles qui ont un montant, dollars d'abord."""
    return [c for c in Currency.values if c in school.enabled_currencies or c in present]


def _check_currency(currency: str) -> None:
    if currency not in require_current_school().enabled_currencies:
        raise BusinessError(CURRENCY_NOT_USED)


def _receipts(year: AcademicYear):
    """Argent reçu à la caisse pour l'année, sans les paiements annulés ni les reprises."""
    return Payment.objects.filter(
        enrollment__academic_year=year,
        origin=Payment.Origin.CASH,
        cancellation__isnull=True,
    )


def _spent(year: AcademicYear):
    """Dépenses payées et non annulées, datées dans l'année."""
    return Expense.objects.filter(
        status=Expense.Status.PAID,
        cancellation__isnull=True,
        spent_on__range=(year.starts_on, year.ends_on),
    )


# Budget


def budget_rows(year: AcademicYear, currency: str) -> list[dict]:
    """Une ligne par catégorie (en service, ou avec un budget ou une dépense) : prévu et dépensé.
    Une seule requête (deux sous-requêtes agrégées)."""
    planned = BudgetLine.objects.filter(
        academic_year=year, currency=currency, category=OuterRef("pk")
    ).values("amount_minor")
    spent = (
        _spent(year)
        .filter(currency=currency, category=OuterRef("pk"))
        .values("category")
        .annotate(total=Sum("amount_minor"))
        .values("total")
    )
    rows = (
        ExpenseCategory.objects.annotate(
            planned_minor=Coalesce(Subquery(planned), 0, output_field=BigIntegerField()),
            spent_minor=Coalesce(Subquery(spent), 0, output_field=BigIntegerField()),
        )
        .filter(Q(is_active=True) | Q(planned_minor__gt=0) | Q(spent_minor__gt=0))
        .order_by("name")
        .values("id", "name", "is_active", "planned_minor", "spent_minor")
    )
    return [{"category": row.pop("id"), **row} for row in rows]


def set_budget(
    *, actor: User, academic_year: AcademicYear, currency: str, amounts: dict
) -> list[dict]:
    """Prévu de chaque catégorie donnée (`{catégorie: montant}`) pour l'année et la devise ; zéro
    retire la ligne, les catégories absentes ne changent pas. Une entrée d'audit avec ce qui a
    changé."""
    _check_currency(currency)
    with transaction.atomic():
        lines = {
            line.category_id: line
            for line in BudgetLine.objects.select_for_update().filter(
                academic_year=academic_year, currency=currency, category__in=list(amounts)
            )
        }
        before, after = {}, {}
        for category, amount in amounts.items():
            line = lines.get(category.pk)
            old = line.amount_minor if line else 0
            if old == amount:
                continue
            before[category.name], after[category.name] = old, amount
            if amount == 0:
                line.delete()
            elif line is None:
                BudgetLine.objects.create(
                    academic_year=academic_year,
                    category=category,
                    currency=currency,
                    amount_minor=amount,
                    created_by=actor,
                )
            else:
                line.amount_minor = amount
                line.save(update_fields=["amount_minor", "updated_at"])
        if after:
            audit.record(
                Action.FINANCE_BUDGET_UPDATED,
                academic_year,
                actor=actor,
                before={"currency": currency, **before},
                after={"currency": currency, **after},
                label=f"{academic_year} · {currency}",
            )
    return budget_rows(academic_year, currency)


# Entrées et sorties par mois


def months(year: AcademicYear, currency: str) -> list[dict]:
    """Entrées (caisse) et sorties (dépenses payées) de chaque mois qui en a : deux requêtes.
    Le mois d'un paiement est pris dans le fuseau de l'école (activé par le middleware)."""
    receipts = (
        _receipts(year)
        .filter(received_currency=currency)
        .annotate(month=TruncMonth("paid_at"))
        .values("month")
        .annotate(total=Sum("received_amount_minor"))
    )
    spent = (
        _spent(year)
        .filter(currency=currency)
        .annotate(month=TruncMonth("spent_on"))
        .values("month")
        .annotate(total=Sum("amount_minor"))
    )
    table: dict[date, dict] = defaultdict(lambda: {"receipts_minor": 0, "expenses_minor": 0})
    for row in receipts:
        month = row["month"]
        table[month.date() if hasattr(month, "date") else month]["receipts_minor"] = row["total"]
    for row in spent:
        table[row["month"]]["expenses_minor"] = row["total"]
    return [
        {
            **values,
            "month": month,
            "balance_minor": values["receipts_minor"] - values["expenses_minor"],
        }
        for month, values in sorted(table.items())
    ]


# Comptes de l'école


def accounts(year: AcademicYear) -> list[dict]:
    """Solde de chaque compte et devise : départ + caisse reçue + virements reçus - virements
    faits - dépenses payées. Trois requêtes, un dictionnaire par compte et par devise."""
    school = require_current_school()
    table: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "opening_minor": 0,
            "receipts_minor": 0,
            "transfers_in_minor": 0,
            "transfers_out_minor": 0,
            "expenses_minor": 0,
        }
    )
    movements = (
        TreasuryMovement.objects.filter(academic_year=year, cancellation__isnull=True)
        .values("kind", "from_account", "to_account", "currency")
        .annotate(total=Sum("amount_minor"))
    )
    for row in movements:
        if row["kind"] == Kind.OPENING:
            table[row["to_account"], row["currency"]]["opening_minor"] += row["total"]
        else:
            table[row["to_account"], row["currency"]]["transfers_in_minor"] += row["total"]
            table[row["from_account"], row["currency"]]["transfers_out_minor"] += row["total"]
    receipts = (
        _receipts(year).values("received_currency").annotate(total=Sum("received_amount_minor"))
    )
    for row in receipts:
        table[Account.CASH, row["received_currency"]]["receipts_minor"] = row["total"]
    spent = _spent(year).values("account", "currency").annotate(total=Sum("amount_minor"))
    for row in spent:
        table[row["account"], row["currency"]]["expenses_minor"] = row["total"]
    present = {currency for _account, currency in table}
    result = []
    for account in Account.values:
        for currency in currencies(school, present):
            values = table[account, currency]
            balance = (
                values["opening_minor"]
                + values["receipts_minor"]
                + values["transfers_in_minor"]
                - values["transfers_out_minor"]
                - values["expenses_minor"]
            )
            result.append(
                {"account": account, "currency": currency, **values, "balance_minor": balance}
            )
    return result


def report(year: AcademicYear, currency: str) -> dict:
    """Ce que montre l'écran « Budget et rapports » pour une année et une devise : six requêtes."""
    rows = budget_rows(year, currency)
    return {
        "academic_year": year.pk,
        "currency": currency,
        "currencies": currencies(require_current_school()),
        "budget": rows,
        "planned_minor": sum(row["planned_minor"] for row in rows),
        "spent_minor": sum(row["spent_minor"] for row in rows),
        "months": months(year, currency),
        "accounts": accounts(year),
    }


# Mouvements entre comptes


def movements(year: AcademicYear):
    return (
        TreasuryMovement.objects.filter(academic_year=year)
        .select_related("recorded_by", "cancellation")
        .order_by("-made_on", "-created_at")
    )


def _data(movement: TreasuryMovement) -> dict:
    return {
        "kind": movement.kind,
        "from_account": movement.from_account,
        "to_account": movement.to_account,
        "amount_minor": movement.amount_minor,
        "currency": movement.currency,
        "made_on": movement.made_on.isoformat(),
    }


def record_movement(
    *,
    actor: User,
    academic_year: AcademicYear,
    kind: str,
    to_account: str,
    amount_minor: int,
    currency: str,
    made_on: date,
    from_account: str = "",
    note: str = "",
) -> TreasuryMovement:
    """Solde de départ d'un compte (un seul en service par compte, devise et année) ou virement
    entre deux comptes. Un virement n'est pas refusé faute d'argent : le solde affiché le dira."""
    school = require_current_school()
    _check_currency(currency)
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        if (
            kind == Kind.OPENING
            and TreasuryMovement.objects.filter(
                academic_year=academic_year,
                kind=Kind.OPENING,
                to_account=to_account,
                currency=currency,
                cancellation__isnull=True,
            ).exists()
        ):
            raise BusinessError(OPENING_EXISTS)
        movement = TreasuryMovement.objects.create(
            academic_year=academic_year,
            kind=kind,
            from_account=from_account if kind == Kind.TRANSFER else "",
            to_account=to_account,
            amount_minor=amount_minor,
            currency=currency,
            made_on=made_on,
            note=note,
            recorded_by=actor,
            created_by=actor,
        )
        audit.record(
            Action.FINANCE_TREASURY_MOVEMENT_RECORDED, movement, actor=actor, after=_data(movement)
        )
    return movement


def cancel_movement(
    movement: TreasuryMovement, *, actor: User, reason: str
) -> TreasuryMovementCancellation:
    """Annuler : une ligne liée avec motif, le mouvement reste dans la liste."""
    with transaction.atomic():
        movement = TreasuryMovement.objects.select_for_update().get(pk=movement.pk)
        if TreasuryMovementCancellation.objects.filter(movement=movement).exists():
            raise BusinessError(MOVEMENT_CANCELLED)
        cancellation = TreasuryMovementCancellation.objects.create(
            movement=movement, reason=reason, cancelled_by=actor, created_by=actor
        )
        audit.record(
            Action.FINANCE_TREASURY_MOVEMENT_CANCELLED,
            movement,
            actor=actor,
            before=_data(movement),
            after={"cancelled": True, "reason": reason},
        )
    return cancellation


# Excel


def _major(amount_minor: int, currency: str):
    return Money(amount_minor, currency).to_major()


def workbook(year: AcademicYear) -> bytes:
    """Classeur de l'année, toutes devises : budget, entrées et sorties par mois, comptes. Les
    montants sont des nombres (unité de la devise), avec la devise dans sa colonne."""
    from openpyxl import Workbook  # chargé ici : pas dans chaque processus (PERF.8)

    school = require_current_school()
    book = Workbook()
    budget = book.active
    budget.title = gettext("Budget")[:31]
    budget.append(
        [
            gettext("Category"),
            gettext("Currency"),
            gettext("Planned"),
            gettext("Spent"),
            gettext("Left"),
            gettext("Used (%)"),
        ]
    )
    flows = book.create_sheet(gettext("Income and spending")[:31])
    flows.append(
        [
            gettext("Month"),
            gettext("Currency"),
            gettext("Income"),
            gettext("Spending"),
            gettext("Balance"),
        ]
    )
    for currency in currencies(school):
        for row in budget_rows(year, currency):
            planned, spent = row["planned_minor"], row["spent_minor"]
            if not planned and not spent:
                continue
            budget.append(
                [
                    row["name"],
                    currency,
                    _major(planned, currency),
                    _major(spent, currency),
                    _major(planned - spent, currency),
                    (spent * 100 + planned // 2) // planned if planned else None,
                ]
            )
        for row in months(year, currency):
            flows.append(
                [
                    formats.date_format(row["month"], "F Y"),
                    currency,
                    _major(row["receipts_minor"], currency),
                    _major(row["expenses_minor"], currency),
                    _major(row["balance_minor"], currency),
                ]
            )
    sheet = book.create_sheet(gettext("Accounts")[:31])
    sheet.append(
        [
            gettext("Account"),
            gettext("Currency"),
            gettext("Opening balance"),
            gettext("Received at the cash desk"),
            gettext("Transfers in"),
            gettext("Transfers out"),
            gettext("Expenses"),
            gettext("Balance"),
        ]
    )
    for row in accounts(year):
        currency = row["currency"]
        sheet.append(
            [str(Account(row["account"]).label), currency]
            + [
                _major(row[key], currency)
                for key in (
                    "opening_minor",
                    "receipts_minor",
                    "transfers_in_minor",
                    "transfers_out_minor",
                    "expenses_minor",
                    "balance_minor",
                )
            ]
        )
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()

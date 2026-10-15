"""Registre des reçus (DOC.3) : un reçu par ligne, sur une période et pour une caisse ou toutes,
avec les totaux par caisse et par devise (jamais additionnés entre devises). Remplace la souche
de l'ancien carnet : le reçu ne s'imprime plus qu'en un exemplaire. Les reçus annulés restent
listés (le registre garde tout) mais ne comptent pas dans les totaux, qui les montrent à part.
Les paiements de reprise n'ont ni caisse ni reçu : ils n'y figurent pas."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.db.models import QuerySet
from django.utils import timezone

from apps.core.money import Currency
from apps.finance.models import CashRegister, Payment

MAX_DAYS = 366
# Un PDF de plus de reçus devient trop lourd à produire pendant la requête : l'Excel, écrit ligne
# à ligne, va plus loin.
MAX_PDF_ROWS = 3000
MAX_XLSX_ROWS = 50000


@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    cash_register: CashRegister | None = None


@dataclass
class Totals:
    """Une caisse et une devise : reçus valides, reçus annulés."""

    currency: str
    count: int = 0
    minor: int = 0
    cancelled_count: int = 0
    cancelled_minor: int = 0


@dataclass
class Group:
    cash_register: CashRegister
    payments: list[Payment] = field(default_factory=list)
    totals: dict[str, Totals] = field(default_factory=dict)


def payments(filters: Filters) -> QuerySet[Payment]:
    """Reçus de caisse de la période (jours inclus, heure locale), par caisse puis par heure."""
    first = timezone.make_aware(datetime.combine(filters.start, time.min))
    after = timezone.make_aware(datetime.combine(filters.end + timedelta(days=1), time.min))
    queryset = (
        Payment.objects.filter(origin=Payment.Origin.CASH, paid_at__gte=first, paid_at__lt=after)
        .select_related(
            "enrollment__student",
            "enrollment__class_group",
            "cashier",
            "cash_session__cash_register",
            "cancellation",
        )
        .order_by(
            "cash_session__cash_register__name", "cash_session__cash_register", "paid_at", "id"
        )
    )
    if filters.cash_register:
        queryset = queryset.filter(cash_session__cash_register=filters.cash_register)
    return queryset


def is_cancelled(payment: Payment) -> bool:
    return hasattr(payment, "cancellation")


def groups(rows: list[Payment]) -> list[Group]:
    """Les reçus rangés par caisse (déjà triés), avec leurs totaux par devise."""
    result: dict[object, Group] = {}
    for payment in rows:
        register = payment.cash_session.cash_register
        group = result.setdefault(register.pk, Group(register))
        group.payments.append(payment)
        totals = group.totals.setdefault(
            payment.received_currency, Totals(payment.received_currency)
        )
        if is_cancelled(payment):
            totals.cancelled_count += 1
            totals.cancelled_minor += payment.received_amount_minor
        else:
            totals.count += 1
            totals.minor += payment.received_amount_minor
    for group in result.values():
        group.totals = dict(
            sorted(group.totals.items(), key=lambda item: list(Currency.values).index(item[0]))
        )
    return list(result.values())


def grand_totals(found: list[Group]) -> list[Totals]:
    """Toutes caisses ensemble, une ligne par devise."""
    result: dict[str, Totals] = {}
    for group in found:
        for currency, totals in group.totals.items():
            total = result.setdefault(currency, Totals(currency))
            total.count += totals.count
            total.minor += totals.minor
            total.cancelled_count += totals.cancelled_count
            total.cancelled_minor += totals.cancelled_minor
    return sorted(result.values(), key=lambda total: list(Currency.values).index(total.currency))

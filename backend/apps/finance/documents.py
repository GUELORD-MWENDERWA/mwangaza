"""Documents produits par le serveur pour les finances : export Excel des clôtures de caisse
(M16). Montants en nombres (Decimal exact, jamais de float), au format de leur devise."""

from datetime import date

from django.utils import timezone
from django.utils.translation import gettext

from apps.core.documents import workbook
from apps.core.money import DECIMALS, SYMBOLS, Currency, Money
from apps.core.tenancy import require_current_school
from apps.finance import services
from apps.finance.models import CashClosing, CashRegister


def _amount_format(currency: str) -> str:
    decimals = DECIMALS[currency]
    return "#,##0" + (f".{'0' * decimals}" if decimals else "")


def closings_workbook(month: date, cash_register: CashRegister | None = None) -> bytes:
    """Une ligne par session du mois, comme à l'écran : attendu, compté et écart par devise
    (jamais additionnés), état, paiements arrivés après la clôture, explication de l'écart."""
    sessions = services.with_closings(list(services.cash_sessions(month, cash_register)))
    notes = dict(
        CashClosing.objects.filter(cash_session__in=sessions).values_list("cash_session", "note")
    )
    enabled = require_current_school().enabled_currencies
    used = {_get(line, "currency") for session in sessions for line in session.lines}
    currencies = [c for c in Currency.values if c in enabled or c in used]
    states = {
        services.OPEN: gettext("Open"),
        services.UNCLOSED: gettext("Not closed"),
        services.BALANCED: gettext("Balanced"),
        services.DIFFERENCE: gettext("Difference"),
    }

    def local(moment):
        return timezone.localtime(moment).replace(tzinfo=None) if moment else None

    def row(session) -> list:
        lines = {_get(line, "currency"): line for line in session.lines}
        amounts = []
        for currency in currencies:
            line = lines.get(currency)
            for field in ("expected_minor", "counted_minor", "difference_minor"):
                minor = _get(line, field) if line else None
                amounts.append(None if minor is None else Money(minor, currency).to_major())
        return [
            local(session.opened_at),
            session.cash_register.name,
            session.cashier.get_full_name() or session.cashier.phone,
            local(session.opened_at),
            local(session.closed_at),
            session.payments_count,
            *amounts,
            states[session.state],
            sum(item["count"] for item in session.late),
            notes.get(session.pk, ""),
        ]

    headers = [
        gettext("Date"),
        gettext("Cash register"),
        gettext("Cashier"),
        gettext("Opened at"),
        gettext("Closed at"),
        gettext("Payments"),
    ]
    formats: list[str | None] = ["dd/mm/yyyy", None, None, "hh:mm", "dd/mm/yyyy hh:mm", None]
    for currency in currencies:
        symbol = SYMBOLS[currency]
        headers += [
            gettext("Expected (%(currency)s)") % {"currency": symbol},
            gettext("Counted (%(currency)s)") % {"currency": symbol},
            gettext("Difference (%(currency)s)") % {"currency": symbol},
        ]
        formats += [_amount_format(currency)] * 3
    headers += [gettext("State"), gettext("Arrived after closing"), gettext("Explanation")]
    return workbook(
        headers,
        (row(session) for session in sessions),
        title=gettext("Cash closings"),
        widths=[12, 16, 24, 10, 17, 10, *[14] * (3 * len(currencies)), 14, 12, 40],
        formats=formats,
    )


def _get(line, field: str):
    """Ligne figée (`CashClosing`) ou d'une session ouverte (dict)."""
    return line[field] if isinstance(line, dict) else getattr(line, field)

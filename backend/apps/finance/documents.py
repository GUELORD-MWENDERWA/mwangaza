"""Documents produits par le serveur pour les finances : export Excel des clôtures de caisse
(M16), impayés en Excel et en PDF (G1). Montants en nombres (Decimal exact, jamais de float), au
format de leur devise."""

from datetime import date

from django.utils import timezone
from django.utils.translation import gettext

from apps.accounts.phone import format_phone
from apps.core.documents import Formatted, school_header, workbook
from apps.core.money import DECIMALS, SYMBOLS, Currency, Money, format_amount
from apps.core.tenancy import require_current_school
from apps.finance import services, unpaid
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


# Impayés (4.1.1, G1)


def _money(minor: int, currency: str) -> Formatted:
    return Formatted(Money(minor, currency).to_major(), _amount_format(currency))


def _student_name(student) -> str:
    """« AMANI SEBUHIRE Gloire », comme sur les listes de classe."""
    surname = " ".join(part for part in (student.last_name, student.middle_name) if part)
    return f"{surname.upper()} {student.first_name}".strip()


def _fee(charge) -> str:
    """« Minerval · 1re tranche » ; le libellé seul quand il répète le type (« Fonctionnement »)."""
    name = charge.fee_type.name
    return name if charge.label == name else f"{name} · {charge.label}"


def unpaid_workbook(rows: list[unpaid.UnpaidStudent]) -> bytes:
    """Une ligne par élève et par frais en retard, pour trier et filtrer dans Excel : montants en
    nombres au format de leur devise, devise dans sa colonne (jamais additionnés)."""

    def lines():
        for row in rows:
            student, guardian = row.enrollment.student, row.guardian
            for charge in row.charges:
                currency = charge.currency
                yield [
                    row.enrollment.class_group.name,
                    student.matricule,
                    _student_name(student),
                    guardian.full_name if guardian else "",
                    format_phone(str(guardian.phone)) if guardian and guardian.phone else "",
                    charge.fee_type.name,
                    charge.label,
                    charge.due_on,
                    _money(charge.amount_minor - charge.discount_minor, currency),
                    _money(charge.paid_minor, currency),
                    _money(charge.remaining_minor, currency),
                    SYMBOLS[currency],
                    charge.days_late,
                ]

    return workbook(
        [
            gettext("Class"),
            gettext("Student number"),
            gettext("Student"),
            gettext("Guardian"),
            gettext("Phone"),
            gettext("Fee"),
            gettext("Installment"),
            gettext("Due date"),
            gettext("Amount"),
            gettext("Paid"),
            gettext("Remaining"),
            gettext("Currency"),
            gettext("Days late"),
        ],
        lines(),
        title=gettext("Unpaid fees"),
        widths=[20, 16, 32, 26, 18, 22, 14, 12, 12, 12, 12, 8, 10],
        formats=[None] * 7 + ["dd/mm/yyyy"],
    )


def _filters_text(filters: unpaid.Filters) -> str:
    """Les filtres choisis, sous le titre : « Minerval · 1re tranche · plus de 30 jours »."""
    parts = []
    if filters.fee_type:
        parts.append(filters.fee_type.name)
    if filters.installment:
        parts.append(filters.installment)
    if filters.over_days:
        parts.append(gettext("more than %(days)s days late") % {"days": filters.over_days})
    if filters.currency:
        parts.append(SYMBOLS[filters.currency])
    return " · ".join(parts)


def _unpaid_row(number: int, row: unpaid.UnpaidStudent, currencies: list[str]) -> dict:
    owed = {amount.currency: amount.overdue_minor for amount in row.amounts}
    guardian, payment = row.guardian, row.last_payment
    contact = ""
    if guardian:
        phone = format_phone(str(guardian.phone)) if guardian.phone else ""
        contact = " · ".join(part for part in (guardian.full_name, phone) if part)
    return {
        "number": number,
        "name": _student_name(row.enrollment.student),
        "class_group": row.enrollment.class_group.name,
        "guardian": guardian.full_name if guardian else "",
        "contact": contact,
        "fees": " · ".join(_fee(charge) for charge in row.charges),
        "charges": [
            {
                "fee": _fee(charge),
                "due_on": charge.due_on,
                "amounts": [
                    format_amount(charge.remaining_minor, c) if charge.currency == c else "—"
                    for c in currencies
                ],
                "days": charge.days_late,
            }
            for charge in row.charges
        ],
        "amounts": [format_amount(owed[c], c) if c in owed else "—" for c in currencies],
        "days": row.days_late,
        "last_payment": (
            f"{timezone.localtime(payment.paid_at):%d/%m} · "
            f"{format_amount(payment.received_amount_minor, payment.received_currency)}"
            if payment
            else "—"
        ),
    }


def unpaid_document(
    rows: list[unpaid.UnpaidStudent], filters: unpaid.Filters, *, by_class: bool, **options
) -> dict:
    """Contenu du PDF A4 à l'italienne : une partie par classe (titulaire, élèves en retard sur
    les inscrits, total par devise) ou une liste unique ; `options` : `page_per_class`, `phone`
    et `detail` (une ligne par tranche)."""
    school = require_current_school()
    used = {amount.currency for row in rows for amount in row.amounts}
    currencies = [c for c in Currency.values if c in school.enabled_currencies or c in used]
    if by_class:
        pages = unpaid.by_class(rows, filters)
    else:
        pages = [
            unpaid.ClassPage(
                class_group=filters.class_group,
                rows=rows,
                enrolled=unpaid.enrolled(filters),
                teacher="",
                totals=unpaid.totals(rows),
            )
        ]
    return {
        **school_header(school),
        **options,
        "year": filters.academic_year,
        "filters": _filters_text(filters),
        "by_class": by_class,
        "currencies": [SYMBOLS[c] for c in currencies],
        "pages": [
            {
                "class_group": page.class_group,
                "teacher": page.teacher,
                "enrolled": page.enrolled,
                "rows": [
                    _unpaid_row(number, row, currencies)
                    for number, row in enumerate(page.rows, start=1)
                ],
                "totals": [
                    next(
                        (format_amount(t.overdue_minor, c) for t in page.totals if t.currency == c),
                        "—",
                    )
                    for c in currencies
                ],
            }
            for page in pages
        ],
    }

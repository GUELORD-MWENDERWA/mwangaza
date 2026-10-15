"""Registre des reçus (DOC.3) : droits, isolation entre écoles, annulés listés mais hors totaux,
totaux par caisse et par devise, période et caisse, audit des fichiers, plafonds."""

import io

import openpyxl
import pytest
from django.utils import timezone

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.money import format_amount
from apps.core.tenancy import use_school
from apps.finance import receipt_register, services
from apps.finance.models import CashRegister
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

REGISTER = "/api/receipt-register/"


def today() -> str:
    return timezone.localdate().isoformat()


@pytest.fixture
def paid(school, head, cashier):
    """Caisse 1 (Alice) : 100,00 $, 12 000 FC, puis 40,00 $ annulés. Caisse 2 : 50,00 $."""
    alpha = school_with_fees(school, head)
    second = MembershipFactory(school=school, roles=["cashier"]).user
    with use_school(school):
        services.create_cash_register(actor=head, name="Caisse 2", code="C2")
    group = alpha["group"]
    student = enrolled(school, head, group, last_name="Paluku")
    with use_school(school):
        other = student.enrollments.get()
    pay(school, cashier, alpha["enrollment"], 10000, "USD")
    pay(school, cashier, alpha["enrollment"], 12000, "CDF")
    cancelled = pay(school, cashier, other, 4000, "USD")
    pay(school, second, other, 5000, "USD", code="C2")
    with use_school(school):
        request, _created = services.request_cancellation(
            cancelled, actor=cashier, reason="Mauvais élève sélectionné (homonyme)"
        )
        services.approve_cancellation(request, actor=head)
        cancellation = cancelled.cancellation
    return {**alpha, "cancelled": cancelled, "cancellation": cancellation}


def test_register_lists_every_receipt_and_totals_leave_out_cancelled_ones(api, school, head, paid):
    with use_school(school):
        filters = receipt_register.Filters(timezone.localdate(), timezone.localdate())
        found = receipt_register.groups(list(receipt_register.payments(filters)))
        by_register = {
            group.cash_register.code: {
                currency: (t.count, t.minor, t.cancelled_count, t.cancelled_minor)
                for currency, t in group.totals.items()
            }
            for group in found
        }
        grand = {t.currency: (t.count, t.minor) for t in receipt_register.grand_totals(found)}
    assert by_register == {
        "C1": {"USD": (1, 10000, 1, 4000), "CDF": (1, 12000, 0, 0)},
        "C2": {"USD": (1, 5000, 0, 0)},
    }
    # Dollars et francs ne s'additionnent jamais ; les annulés ne comptent pas.
    assert grand == {"USD": (2, 15000), "CDF": (1, 12000)}

    html = api(head).get(REGISTER, start=today(), end=today(), output="html").content.decode()
    assert html.count('class="cancelled"') == 1
    assert paid["cancelled"].receipt_number in html
    assert format_amount(15000, "USD") in html


def test_excel_has_one_line_per_receipt_then_the_totals(api, school, head, paid):
    response = api(head).get(REGISTER, start=today(), end=today(), output="xlsx")
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    rows = [[cell.value for cell in row] for row in sheet.iter_rows(min_row=2)]
    receipts = [row for row in rows if row[1]]
    assert [(row[0], row[7], row[8]) for row in receipts] == [
        ("Caisse 1", 100, "$"),
        ("Caisse 1", 12000, "FC"),
        ("Caisse 1", 40, "$"),
        ("Caisse 2", 50, "$"),
    ]
    cancelled = next(row for row in receipts if row[7] == 40)
    assert cancelled[11] == paid["cancellation"].receipt_number
    totals = [row for row in rows if not row[1] and row[0]]
    assert [(row[7], row[8]) for row in totals][-2:] == [(150, "$"), (12000, "FC")]


def test_period_and_cash_register_filters_and_one_audit_line_per_file(api, school, head, paid):
    client = api(head)
    with use_school(school):
        second = CashRegister.objects.get(code="C2")
    html = client.get(
        REGISTER, start=today(), end=today(), output="html", cash_register=str(second.pk)
    ).content.decode()
    assert "Caisse 2" in html
    assert "Caisse 1" not in html

    tomorrow = (timezone.localdate() + timezone.timedelta(days=1)).isoformat()
    empty = client.get(REGISTER, start=tomorrow, end=tomorrow, output="html").content.decode()
    assert 'class="cancelled"' not in empty
    assert paid["cancelled"].receipt_number not in empty

    assert client.get(REGISTER, start=today(), end=today(), output="pdf")["Content-Type"] == (
        "application/pdf"
    )
    client.get(REGISTER, start=today(), end=today(), output="xlsx")
    with use_school(school):
        logs = AuditLog.objects.filter(action=Action.FINANCE_RECEIPT_REGISTER_EXPORTED)
        # L'aperçu à l'écran n'est pas noté ; les fichiers le sont.
        assert sorted((log.actor, log.after["output"], log.after["receipts"]) for log in logs) == [
            (head, "pdf", 4),
            (head, "xlsx", 4),
        ]


def test_only_those_who_see_reports_get_the_register(api, school, cashier, paid):
    response = api(cashier).get(REGISTER, start=today(), end=today(), output="html")
    assert response.status_code == 403


def test_a_school_never_sees_the_receipts_or_cash_registers_of_another(
    api, school, other_school, head, other_head, paid
):
    beta = school_with_fees(other_school, other_head)
    client = api(other_head, host="beta.localhost")
    html = client.get(REGISTER, start=today(), end=today(), output="html").content.decode()
    assert paid["cancelled"].receipt_number not in html
    assert "Caisse 2" not in html

    # La caisse d'une autre école n'existe pas pour cette école : refus, pas un registre vide.
    response = client.get(
        REGISTER,
        start=today(),
        end=today(),
        output="html",
        cash_register=str(paid["register"].pk),
    )
    assert response.status_code == 400
    assert beta["register"].pk != paid["register"].pk


def test_period_must_be_ordered_and_within_a_year(api, head):
    client = api(head)
    backwards = client.get(REGISTER, start="2026-10-10", end="2026-10-01", output="pdf")
    too_long = client.get(REGISTER, start="2025-01-01", end="2026-10-01", output="pdf")
    assert (backwards.status_code, too_long.status_code) == (400, 400)


def test_a_pdf_with_too_many_receipts_is_refused_but_the_excel_still_comes(
    api, head, paid, monkeypatch
):
    monkeypatch.setattr(receipt_register, "MAX_PDF_ROWS", 3)
    client = api(head)
    assert client.get(REGISTER, start=today(), end=today(), output="pdf").status_code == 400
    assert client.get(REGISTER, start=today(), end=today(), output="xlsx").status_code == 200

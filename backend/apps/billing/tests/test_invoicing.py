# ruff: noqa: F811
"""Factures, avoirs, paiements, relevé et PDF (ABO.2) : montants en entiers, rien ne se modifie
(avoir, annulation liée), droits de la console, journal, isolation entre écoles."""

import pytest

from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.billing import invoicing, services
from apps.billing.models import Invoice, InvoicePayment
from apps.billing.tests.test_billing import CONSOLE, END, START, essential, finance, member  # noqa: F401
from apps.core.errors import BusinessError
from apps.core.tenancy import use_all_schools, use_school

pytestmark = pytest.mark.django_db


@pytest.fixture
def contract(finance, essential, school):
    draft = services.draft_contract(
        actor=finance, school=school, plan=essential, start_date=START, end_date=END
    )
    return services.activate_contract(draft, actor=finance, signature="online", signer_name="A")


@pytest.fixture
def invoice(finance, contract):
    return invoicing.issue_invoice(contract, actor=finance, students=40, issued_on=START)


def fresh(invoice):
    with use_all_schools():
        return Invoice.all_schools.get(pk=invoice.pk)


def balance(invoice) -> int:
    with use_all_schools():
        return invoicing.balance(fresh(invoice))


def count_payments() -> int:
    with use_all_schools():
        return InvoicePayment.all_schools.count()


def code(error) -> str:
    return error.value.error.code


def test_invoice_is_students_times_price_in_whole_units(invoice, finance):
    assert invoice.number.startswith("FA-") and invoice.total == 40 * 150
    assert invoice.currency == "USD"
    with use_school(invoice.school):
        assert invoice.lines.count() == 1
    assert PlatformAuditLog.objects.filter(action=PlatformAction.INVOICE_ISSUED).count() == 1
    with pytest.raises(BusinessError) as err:  # rien à facturer
        invoicing.issue_invoice(invoice.contract, actor=finance, students=0)
    assert code(err) == "invoice_empty"


def test_payment_never_exceeds_the_balance_and_is_cancelled_by_a_linked_entry(invoice, finance):
    pay = lambda amount: invoicing.record_payment(  # noqa: E731
        invoice, actor=finance, amount=amount, method="bank", paid_on=START
    )
    first = pay(2000)
    assert balance(invoice) == 4000
    with pytest.raises(BusinessError) as err:
        pay(4001)
    assert code(err) == "payment_exceeds_balance"

    reversal = invoicing.reverse_payment(first, actor=finance, reason="Virement rejeté")
    assert reversal.reverses_id == first.pk and count_payments() == 2
    assert balance(invoice) == 6000
    with pytest.raises(BusinessError) as err:  # une seule annulation par paiement
        invoicing.reverse_payment(first, actor=finance, reason="Encore")
    assert code(err) == "payment_reversed"
    with pytest.raises(BusinessError):  # le motif est obligatoire
        invoicing.reverse_payment(pay(100), actor=finance, reason=" ")
    assert PlatformAuditLog.objects.filter(action=PlatformAction.INVOICE_PAYMENT_REVERSED).exists()


def test_credit_note_cancels_the_invoice_without_touching_it(invoice, finance):
    payment = invoicing.record_payment(
        invoice, actor=finance, amount=100, method="cash", paid_on=START
    )
    with pytest.raises(BusinessError) as err:  # d'abord annuler le paiement reçu
        invoicing.cancel_invoice(invoice, actor=finance, reason="Erreur d'effectif")
    assert code(err) == "invoice_has_payments"
    invoicing.reverse_payment(payment, actor=finance, reason="Remboursé")

    note = invoicing.cancel_invoice(invoice, actor=finance, reason="Erreur d'effectif")
    with use_all_schools():
        invoice.refresh_from_db()
    assert note.number.startswith("AV-") and note.credit_for_id == invoice.pk
    assert invoice.total == 6000 and balance(invoice) == 0
    with pytest.raises(BusinessError) as err:
        invoicing.cancel_invoice(invoice, actor=finance, reason="Encore")
    assert code(err) == "invoice_credited"
    with pytest.raises(BusinessError) as err:  # plus de paiement sur une facture annulée
        invoicing.record_payment(invoice, actor=finance, amount=1, method="cash", paid_on=START)
    assert code(err) == "invoice_not_payable"


def test_statement_shows_the_running_balance_of_one_school_only(
    invoice, finance, essential, other_school
):
    invoicing.record_payment(
        invoice, actor=finance, amount=1500, method="mobile_money", paid_on=START
    )
    other = services.activate_contract(
        services.draft_contract(
            actor=finance, school=other_school, plan=essential, start_date=START, end_date=END
        ),
        actor=finance,
        signature="online",
        signer_name="B",
    )
    invoicing.issue_invoice(other, actor=finance, students=10)
    rows = invoicing.statement(invoice.school)["USD"]
    assert [(r["kind"], r["balance"]) for r in rows] == [("invoice", 6000), ("payment", 4500)]
    with use_school(other_school):
        assert [i.school_id for i in Invoice.objects.all()] == [other_school.pk]


def test_console_rights_and_pdfs(api, invoice, contract):
    support = api(member("support"), host=CONSOLE)
    body = {"amount": 100, "method": "cash", "paid_on": "2026-11-02"}
    assert support.post(f"/api/console/billing/invoices/{invoice.pk}/pay/", body).status_code == 403
    assert (
        support.get("/api/console/billing/invoices/").status_code == 403
    )  # chiffres de la finance

    finance_api = api(member("finance"), host=CONSOLE)
    assert (
        finance_api.post(f"/api/console/billing/invoices/{invoice.pk}/pay/", body).status_code
        == 201
    )
    shown = finance_api.get(f"/api/console/billing/invoices/{invoice.pk}/").json()
    assert shown["paid"] == 100 and shown["balance"] == 5900 and shown["total"] == 6000
    for url in (
        f"/api/console/billing/invoices/{invoice.pk}/pdf/",
        f"/api/console/billing/contracts/{contract.pk}/pdf/",
    ):
        response = finance_api.get(url)
        assert response.status_code == 200 and response.content.startswith(b"%PDF")

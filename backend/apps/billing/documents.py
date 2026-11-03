"""Contrat et facture en PDF (CTR.1, ABO.2) : parties tirées de l'identité de la plateforme (I20)
et de l'école, offre, modules, prix. Aucune valeur en dur : « à compléter » si l'identité manque."""

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.modules import MODULE_CHOICES
from apps.billing import invoicing
from apps.billing.models import Contract, Invoice
from apps.core import printing
from apps.core.documents import PDF, file_response
from apps.core.models import PlatformSettings
from apps.core.money import format_amount
from apps.core.tenancy import use_school

MODULE_NAMES = dict(MODULE_CHOICES)


def _base() -> dict:
    return {
        "platform": PlatformSettings.load(),
        "print_fonts": "",
        "serif_fonts": "",
        "printed_at": timezone.localdate(),
    }


def contract_pdf(contract: Contract) -> HttpResponse:
    school = contract.school
    html = render_to_string(
        "billing/contract.html",
        {
            **_base(),
            "contract": contract,
            "school": school,
            "plan": contract.plan,
            "modules": [str(MODULE_NAMES.get(m, m)) for m in contract.modules],
            "price": format_amount(contract.price_per_student, contract.currency),
        },
    )
    return file_response(printing.to_pdf(html), PDF, f"{contract.number}.pdf", inline=True)


def invoice_pdf(invoice: Invoice) -> HttpResponse:
    with use_school(invoice.school):
        lines = [
            {
                "description": line.description,
                "quantity": line.quantity,
                "unit": format_amount(line.unit_amount, invoice.currency),
                "amount": format_amount(line.amount, invoice.currency),
            }
            for line in invoice.lines.all()
        ]
        paid_rows = list(invoice.payments.values_list("amount", "reverses_id"))
    paid = sum(-a if r else a for a, r in paid_rows)
    html = render_to_string(
        "billing/invoice.html",
        {
            **_base(),
            "invoice": invoice,
            "school": invoice.school,
            "lines": lines,
            "total": format_amount(invoice.total, invoice.currency),
            "paid": format_amount(paid, invoice.currency),
            "due": format_amount(invoicing.balance(invoice), invoice.currency),
            "is_credit": invoice.kind == Invoice.Kind.CREDIT_NOTE,
        },
    )
    return file_response(printing.to_pdf(html), PDF, f"{invoice.number}.pdf", inline=True)

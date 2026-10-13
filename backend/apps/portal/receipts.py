"""Reçu d'un paiement en PDF pour la famille (H3) : même contenu que le reçu de la caisse (F3),
mis en page en A5 par le serveur (WeasyPrint), avec la mention qu'il a été téléchargé sur le
portail et le QR code de vérification (`/v/{id}` à l'adresse de l'école). Jamais pour un paiement
annulé. Pas noté au journal : la famille lit ses propres reçus, ce n'est pas une réimpression de
la caisse (F6)."""

from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.core.documents import qr_code, school_header
from apps.core.money import amount_in_words, format_amount, format_rate
from apps.core.tenancy import require_current_school
from apps.finance import services as finance
from apps.finance.models import Payment
from apps.portal.children import fee_label, linked_to
from apps.schools.models import School
from apps.schools.receipts import receipt_settings


def find_payment(user: User, payment_id) -> Payment:
    """Paiement non annulé d'un enfant d'une famille reliée à ce compte ; sinon 404. Une
    reprise (E6, payé avant que l'école n'utilise l'application) n'a pas de reçu."""
    payment = (
        Payment.all_schools.filter(
            pk=payment_id,
            cancellation__isnull=True,
            origin=Payment.Origin.CASH,
            **linked_to(user, "enrollment__student__family"),
        )
        .exclude(School.portal_closed("school__"))
        .select_related("school")
        .first()
    )
    if payment is None:
        raise NotFound
    return payment


def _amounts(items: list[tuple[int, str]], nothing: str) -> str:
    """« 210,00 $ + 25 000 FC », jamais additionnés ; `nothing` si rien n'est dû."""
    due = [format_amount(minor, currency) for minor, currency in items if minor > 0]
    return " + ".join(due) or nothing


def receipt_document(payment: Payment) -> dict:
    """Contexte du gabarit `portal/receipt.html` ; à appeler et rendre dans l'école du paiement
    (`children.in_school` : ses données, son fuseau)."""
    school = require_current_school()
    payment = finance.receipt_payments().get(pk=payment.pk)
    balance = finance.balance_after(payment).currencies
    enrollment = payment.enrollment
    received = payment.received_currency
    lines = list(payment.allocations.all())
    converted = any(line.student_charge.currency != received for line in lines)
    nothing = gettext("nothing")
    settings = receipt_settings(school.settings)
    verify_url = f"{school.url}/v/{payment.pk}"
    return {
        **school_header(school),
        "header_lines": [line for line in settings["header"].splitlines() if line.strip()],
        "footer": settings["footer"],
        "paper": "a5",
        "number": payment.receipt_number,
        "paid_at": timezone.localtime(payment.paid_at),
        "year": enrollment.academic_year.name,
        "student": enrollment.student.full_name,
        "matricule": enrollment.student.matricule,
        "class_group": enrollment.class_group.name,
        "lines": [
            {
                "fee": fee_label(line.student_charge),
                "due_on": line.student_charge.due_on,
                "amount": format_amount(line.amount_minor, line.student_charge.currency),
            }
            for line in lines
        ],
        "total": format_amount(payment.received_amount_minor, received),
        "words": amount_in_words(payment.received_amount_minor, received),
        "rate": format_rate(payment.rate_used) if converted and payment.rate_used else "",
        "overdue": _amounts([(item.overdue_minor, item.currency) for item in balance], nothing),
        "remaining": _amounts([(item.remaining_minor, item.currency) for item in balance], nothing),
        "note": payment.note,
        "cashier": str(payment.cashier),
        "cash_register": payment.cash_session.cash_register.name,
        "verify_url": verify_url,
        "qr": qr_code(verify_url),
    }

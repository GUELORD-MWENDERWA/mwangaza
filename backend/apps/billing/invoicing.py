"""Factures, avoirs, paiements et relevé d'une école (ABO.2). Entiers uniquement (règle 2) ; une
facture et un paiement ne changent jamais (règle 3) : l'erreur se corrige par un avoir ou par une
écriture d'annulation liée. Tout est au journal de la plateforme (règle 5)."""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.billing.models import Contract, Invoice, InvoiceLine, InvoicePayment
from apps.billing.services import next_number
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_all_schools, use_school
from apps.schools.models import School

PAYMENT_DAYS = 30

NOT_ACTIVE = ApiError("invoice_contract_not_active", _("Only an active contract is invoiced."), 409)
EMPTY = ApiError("invoice_empty", _("An invoice needs at least one line above zero."), 400)
NOT_INVOICE = ApiError("invoice_not_invoice", _("This document is already a credit note."), 409)
ALREADY_CREDITED = ApiError("invoice_credited", _("This invoice is already cancelled."), 409)
HAS_PAYMENTS = ApiError(
    "invoice_has_payments", _("Cancel the payments of this invoice before cancelling it."), 409
)
OVERPAID = ApiError("payment_exceeds_balance", _("The amount is above what is still due."), 400)
NOT_PAYABLE = ApiError("invoice_not_payable", _("This invoice is cancelled."), 409)
ALREADY_REVERSED = ApiError("payment_reversed", _("This payment is already cancelled."), 409)
REASON_NEEDED = ApiError("reason_required", _("Give the reason."), 400)


def enrolled_count(school: School) -> int:
    """Élèves inscrits (actifs) de l'année en cours : la base de la facture."""
    from apps.students.models import Enrollment

    with use_school(school):
        return Enrollment.objects.filter(
            academic_year__is_current=True, status=Enrollment.Status.ACTIVE
        ).count()


def with_balance(invoices):
    """Annote chaque facture de ce qui est payé (net des annulations) : pas de requête par ligne."""
    paid = Coalesce(
        Sum("payments__amount", filter=Q(payments__reverses__isnull=True)), 0
    ) - Coalesce(Sum("payments__amount", filter=Q(payments__reverses__isnull=False)), 0)
    return invoices.annotate(paid=paid)


def balance(invoice: Invoice) -> int:
    """Reste dû : 0 pour un avoir et pour une facture annulée."""
    if invoice.kind == Invoice.Kind.CREDIT_NOTE or hasattr(invoice, "credit_note"):
        return 0
    paid = getattr(invoice, "paid", None)
    if paid is None:
        rows = InvoicePayment.all_schools.filter(invoice=invoice).values_list(
            "amount", "reverses_id"
        )
        paid = sum(-a if r else a for a, r in rows)
    return invoice.total - paid


def _write(
    *, actor, school, contract, kind, lines, issued_on, credit_for=None, **period
) -> Invoice:
    year = issued_on.year
    prefix, key = ("FA", "invoice") if kind == Invoice.Kind.INVOICE else ("AV", "credit")
    with use_school(school):
        invoice = Invoice.objects.create(
            school=school,
            created_by=actor,
            number=next_number(f"{key}-{year}", f"{prefix}-{year}"),
            kind=kind,
            contract=contract,
            credit_for=credit_for,
            issued_on=issued_on,
            due_on=issued_on + timedelta(days=PAYMENT_DAYS),
            currency=contract.currency,
            total=sum(amount for _d, _q, _u, amount in lines),
            **period,
        )
        InvoiceLine.objects.bulk_create(
            InvoiceLine(
                school=school,
                created_by=actor,
                invoice=invoice,
                description=description,
                quantity=quantity,
                unit_amount=unit,
                amount=amount,
            )
            for description, quantity, unit, amount in lines
        )
    return invoice


def issue_invoice(
    contract: Contract,
    *,
    actor,
    students: int | None = None,
    extra_lines: list[tuple[str, int, int]] | None = None,
    issued_on: date | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> Invoice:
    """Facture d'une période : « élèves inscrits x prix du contrat » (si `students` est 0, pas de
    ligne) plus des lignes libres `(description, quantité, prix unitaire)`."""
    issued_on = issued_on or date.today()
    with transaction.atomic(), use_all_schools():
        contract = Contract.all_schools.select_related("school", "plan").get(pk=contract.pk)
        if contract.status != Contract.Status.ACTIVE:
            raise BusinessError(NOT_ACTIVE)
        school = contract.school
        count = enrolled_count(school) if students is None else students
        lines = []
        if count:
            lines.append(
                (
                    gettext("%(plan)s — %(count)s enrolled students")
                    % {
                        "plan": contract.plan.name,
                        "count": count,
                    },
                    count,
                    contract.price_per_student,
                    count * contract.price_per_student,
                )
            )
        for description, quantity, unit in extra_lines or []:
            lines.append((description, quantity, unit, quantity * unit))
        if not lines or sum(line[3] for line in lines) <= 0:
            raise BusinessError(EMPTY)
        invoice = _write(
            actor=actor,
            school=school,
            contract=contract,
            kind=Invoice.Kind.INVOICE,
            lines=lines,
            issued_on=issued_on,
            period_start=period_start,
            period_end=period_end,
        )
        audit.record_platform(
            PlatformAction.INVOICE_ISSUED,
            invoice,
            actor=actor,
            after={"school": school.code, "total": invoice.total, "currency": invoice.currency},
        )
    return invoice


def cancel_invoice(invoice: Invoice, *, actor, reason: str) -> Invoice:
    """Avoir complet lié à la facture : la facture ne bouge pas, son reste dû tombe à 0. Les
    paiements reçus doivent d'abord être annulés."""
    if not reason.strip():
        raise BusinessError(REASON_NEEDED)
    with transaction.atomic(), use_all_schools():
        invoice = (
            Invoice.all_schools.select_for_update()
            .select_related("school", "contract")
            .get(pk=invoice.pk)
        )
        if invoice.kind != Invoice.Kind.INVOICE:
            raise BusinessError(NOT_INVOICE)
        if hasattr(invoice, "credit_note"):
            raise BusinessError(ALREADY_CREDITED)
        if balance(invoice) != invoice.total:
            raise BusinessError(HAS_PAYMENTS)
        lines = [
            (line.description, line.quantity, line.unit_amount, line.amount)
            for line in InvoiceLine.all_schools.filter(invoice=invoice)
        ]
        note = _write(
            actor=actor,
            school=invoice.school,
            contract=invoice.contract,
            kind=Invoice.Kind.CREDIT_NOTE,
            lines=lines,
            issued_on=date.today(),
            credit_for=invoice,
        )
        audit.record_platform(
            PlatformAction.CREDIT_NOTE_ISSUED,
            note,
            actor=actor,
            after={"invoice": invoice.number, "total": note.total, "reason": reason.strip()},
        )
        _refresh(invoice.school, actor)
    return note


def _refresh(school: School, actor) -> None:
    """Un paiement, une annulation de paiement ou un avoir change peut-être l'état de l'école
    (lecture seule, ABO.3) : on le dit tout de suite, sans attendre le passage du matin."""
    from apps.billing import reminders

    reminders.refresh(school, actor=actor)


def record_payment(
    invoice: Invoice, *, actor, amount: int, method: str, paid_on: date, reference: str = ""
) -> InvoicePayment:
    """Paiement reçu, jamais au-delà de ce qui reste dû."""
    with transaction.atomic(), use_all_schools():
        invoice = (
            Invoice.all_schools.select_for_update().select_related("school").get(pk=invoice.pk)
        )
        if invoice.kind != Invoice.Kind.INVOICE or hasattr(invoice, "credit_note"):
            raise BusinessError(NOT_PAYABLE)
        if amount <= 0 or amount > balance(invoice):
            raise BusinessError(OVERPAID)
        with use_school(invoice.school):
            payment = InvoicePayment(
                school=invoice.school,
                created_by=actor,
                invoice=invoice,
                amount=amount,
                method=method,
                reference=reference.strip(),
                paid_on=paid_on,
            )
            payment.full_clean()
            payment.save()
        audit.record_platform(
            PlatformAction.INVOICE_PAYMENT,
            payment,
            actor=actor,
            after={"invoice": invoice.number, "amount": amount, "method": method},
        )
        _refresh(invoice.school, actor)
    return payment


def reverse_payment(payment: InvoicePayment, *, actor, reason: str) -> InvoicePayment:
    """Annulation d'un paiement : nouvelle écriture liée, avec motif ; l'original reste."""
    if not reason.strip():
        raise BusinessError(REASON_NEEDED)
    with transaction.atomic(), use_all_schools():
        payment = (
            InvoicePayment.all_schools.select_for_update()
            .select_related("invoice", "school")
            .get(pk=payment.pk)
        )
        if payment.reverses_id or hasattr(payment, "reversal"):
            raise BusinessError(ALREADY_REVERSED)
        with use_school(payment.school):
            reversal = InvoicePayment.objects.create(
                school=payment.school,
                created_by=actor,
                invoice=payment.invoice,
                amount=payment.amount,
                method=payment.method,
                reference=payment.reference,
                paid_on=date.today(),
                reverses=payment,
                reason=reason.strip(),
            )
        audit.record_platform(
            PlatformAction.INVOICE_PAYMENT_REVERSED,
            reversal,
            actor=actor,
            after={"invoice": payment.invoice.number, "amount": payment.amount, "reason": reason},
        )
        _refresh(payment.invoice.school, actor)
    return reversal


def statement(school: School) -> dict[str, list[dict]]:
    """Relevé de l'école, par devise : factures et annulations (débit), paiements (crédit),
    avec le solde après chaque écriture. Une facture et son avoir s'annulent."""
    entries = []
    with use_school(school):
        for inv in Invoice.objects.all():
            credit = inv.kind == Invoice.Kind.CREDIT_NOTE
            entries.append(
                (inv.issued_on, inv.created_at, inv.currency, inv.kind, inv.number, "",
                 0 if credit else inv.total, inv.total if credit else 0)
            )  # fmt: skip
        for pay in InvoicePayment.objects.select_related("invoice"):
            back = pay.reverses_id is not None
            kind, amount = ("reversal", (pay.amount, 0)) if back else ("payment", (0, pay.amount))
            entries.append(
                (pay.paid_on, pay.created_at, pay.invoice.currency, kind, pay.invoice.number,
                 pay.reference, *amount)
            )  # fmt: skip
    result: dict[str, list[dict]] = {}
    for when, _at, currency, kind, number, reference, debit, credit in sorted(
        entries, key=lambda e: (e[0], e[1])
    ):
        rows = result.setdefault(currency, [])
        previous = rows[-1]["balance"] if rows else 0
        rows.append(
            {
                "date": when,
                "kind": kind,
                "number": number,
                "reference": reference,
                "debit": debit,
                "credit": credit,
                "balance": previous + debit - credit,
            }
        )
    return result

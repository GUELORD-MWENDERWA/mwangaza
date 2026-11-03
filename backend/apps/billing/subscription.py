"""« Mon abonnement » (ABO.4) : ce que l'école voit de son contrat avec la plateforme. Lecture
seule, dans l'école courante : factures, solde par devise, prochaine échéance, comment payer, et
la demande d'ajout d'un module (rangée pour la console, rien n'est activé ni facturé)."""

from django.utils.translation import gettext_lazy as _

from apps.billing import invoicing
from apps.billing.models import Contract, Invoice, ModuleRequest
from apps.core.errors import ApiError, BusinessError
from apps.core.models import PlatformSettings

MODULE_UNKNOWN = ApiError("module_unknown", _("This module does not exist."), 400)
MODULE_OWNED = ApiError("module_owned", _("Your school already has this module."), 400)
MODULE_ALREADY_ASKED = ApiError(
    "module_already_requested", _("You have already asked for this module."), 400
)


def current_contract() -> Contract | None:
    return Contract.objects.filter(status=Contract.Status.ACTIVE).select_related("plan").first()


def invoices():
    """Factures et avoirs de l'école, récents d'abord, avec ce qui est payé."""
    return invoicing.with_balance(
        Invoice.objects.select_related("contract", "credit_for")
        .prefetch_related("lines", "payments")
        .order_by("-issued_on", "-created_at")
    )


def summary(school) -> dict:
    """Solde par devise (factures non annulées moins paiements), prochaine échéance, et si
    quelque chose est en retard. Une requête de factures, pas de calcul par ligne."""
    due, next_due = {}, None
    from datetime import date

    today = date.today()
    late = False
    for invoice in invoices().filter(kind=Invoice.Kind.INVOICE):
        left = invoicing.balance(invoice)
        if left <= 0:
            continue
        due[invoice.currency] = due.get(invoice.currency, 0) + left
        late = late or invoice.due_on < today
        if next_due is None or invoice.due_on < next_due["due_on"]:
            next_due = {
                "number": invoice.number,
                "due_on": invoice.due_on,
                "currency": invoice.currency,
                "amount": left,
            }
    return {
        "balance": [{"currency": c, "amount": a} for c, a in due.items()],
        "next_due": next_due,
        "late": late,
        "payment_details": PlatformSettings.load().payment_details,
        "read_only": school.status == school.Status.READ_ONLY,
        "open_requests": list(
            ModuleRequest.objects.filter(status=ModuleRequest.Status.OPEN).values_list(
                "module", flat=True
            )
        ),
    }


def handle_request(module_request: ModuleRequest, *, actor) -> ModuleRequest:
    """La plateforme a traité la demande (avenant fait, ou refus parlé) : elle sort de la liste
    des demandes ouvertes et l'école peut en refaire une. Sans effet si déjà traitée."""
    from apps.audit import services as audit
    from apps.audit.actions import PlatformAction

    if module_request.status == ModuleRequest.Status.DONE:
        return module_request
    module_request.status = ModuleRequest.Status.DONE
    module_request.save(update_fields=["status", "updated_at"])
    audit.record_platform(
        PlatformAction.MODULE_REQUEST_HANDLED,
        module_request,
        actor=actor,
        after={"school": module_request.school.code, "module": module_request.module},
    )
    return module_request


def request_module(school, *, user, module: str, note: str = "") -> ModuleRequest:
    from apps.accounts.modules import MODULES

    if module not in MODULES:
        raise BusinessError(MODULE_UNKNOWN)
    if module in school.modules:
        raise BusinessError(MODULE_OWNED)
    if ModuleRequest.objects.filter(module=module, status=ModuleRequest.Status.OPEN).exists():
        raise BusinessError(MODULE_ALREADY_ASKED)
    return ModuleRequest.objects.create(
        school=school, module=module, note=note.strip(), created_by=user
    )

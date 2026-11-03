"""Données de démonstration de la facturation (ABO.1, ABO.2, CTR.1) : deux offres inventées (le
tarif réel, T6, se règle dans la console), les textes légaux en première version, et un contrat
signé de l'ITIG de démonstration avec une facture à moitié payée. Une seule fois."""

import datetime

from django.utils import timezone

from apps.accounts.modules import ALL_MODULES
from apps.billing import invoicing, services
from apps.billing.legal_texts import TEXTS
from apps.billing.models import Contract, LegalDocument, Plan


def create_demo_legal() -> None:
    """Première version des trois textes, publiée sans journal (aucun compte ne l'a fait)."""
    for kind, text in TEXTS.items():
        LegalDocument.objects.get_or_create(
            kind=kind, version=1, defaults={"published_at": timezone.now(), **text}
        )


def create_demo_billing(spaces, admin) -> None:
    if Plan.objects.exists():
        return
    services.save_plan(
        actor=admin, code="essentiel", name="Essentiel", modules=["students", "finance"],
        description="Élèves, frais scolaires et caisse.", price_per_student=300,
        currency="USD", period="year",
    )  # fmt: skip
    complete = services.save_plan(
        actor=admin, code="complet", name="Complet", modules=ALL_MODULES,
        description="Tous les modules.", price_per_student=600, currency="USD", period="year",
    )  # fmt: skip
    itig = next((s.school for s in spaces if s.school.code == "itig-demo"), None)
    if itig is None:
        return
    today = datetime.date.today()
    start = datetime.date(today.year if today.month >= 9 else today.year - 1, 9, 1)
    draft = services.draft_contract(
        actor=admin, school=itig, plan=complete, start_date=start,
        end_date=datetime.date(start.year + 1, 8, 31),
    )  # fmt: skip
    contract = services.activate_contract(
        draft, actor=admin, signature=Contract.Signature.ONLINE, signer_name="Le préfet (fictif)"
    )
    invoice = invoicing.issue_invoice(contract, actor=admin, issued_on=start)
    invoicing.record_payment(
        invoice, actor=admin, amount=invoice.total // 2, method="bank", paid_on=start,
        reference="VIR-DEMO-001",
    )  # fmt: skip

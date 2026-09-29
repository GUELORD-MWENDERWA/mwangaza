"""Page publique de vérification d'un reçu `/v/{id}` (F4, maquette `portail/verification-recu`),
ouverte par le QR code du reçu sur l'adresse de l'école. Page HTML sans JavaScript ni connexion :
légère sur n'importe quel téléphone. Le minimum : école, numéro, date, montant, état ; l'élève en
initiales seulement.

Un reçu imprimé sur un appareil mémorisé (3.5.2) porte dans son QR code ce qu'il affiche (`n`
numéro, `t` heure en secondes, `a` montant, `c` devise, `r` caisse), signé par l'appareil (`s`,
ECDSA P-256) : un reçu pas encore synchronisé reste vérifiable ; un reçu enregistré dont le QR
code dit autre chose que la base est falsifié."""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.core.money import Currency, format_amount
from apps.finance.models import Payment
from apps.schools.models import School
from apps.students.models import Student
from apps.sync.models import Device, SyncOperation
from apps.sync.services import verify_signature

VALID, CANCELLED, PENDING, FORGED, UNKNOWN = "valid", "cancelled", "pending", "forged", "unknown"


def initials(student: Student) -> str:
    """« KASEREKA Muhindo Jean » → « K. M. J. » : nom, post-nom, prénom."""
    names = [student.last_name, student.middle_name, student.first_name]
    return " ".join(f"{word[0].upper()}." for name in names for word in name.split())


@dataclass(frozen=True)
class Claim:
    """Ce que le QR code d'un reçu dit de lui, signé par l'appareil qui l'a imprimé."""

    number: str
    time: int
    amount: int
    currency: str
    register: str
    signature: bytes

    @classmethod
    def read(cls, params: QueryDict) -> "Claim | None":
        """`None` : QR code sans contenu (reçu imprimé hors d'un appareil mémorisé). Contenu
        incomplet ou illisible : `ValueError` (base64 invalide compris)."""
        if "n" not in params:
            return None
        try:
            signature = base64.urlsafe_b64decode(params.get("s", "") + "==")
            return cls(
                number=params["n"],
                time=int(params["t"]),
                amount=int(params["a"]),
                currency=params["c"],
                register=params.get("r", ""),
                signature=signature,
            )
        except KeyError as exc:
            raise ValueError from exc

    def message(self, payment_id: UUID) -> bytes:
        """Texte signé par l'appareil (`features/cash/receiptQr.ts`)."""
        fields = [payment_id, self.number, self.time, self.amount, self.currency, self.register]
        return "|".join(str(field) for field in fields).encode()

    def matches(self, payment: Payment) -> bool:
        return (self.number, self.time, self.amount, self.currency, self.register) == (
            payment.receipt_number,
            int(payment.paid_at.timestamp()),
            payment.received_amount_minor,
            payment.received_currency,
            payment.cash_session.cash_register.code,
        )


def _offline_state(school: School, payment_id: UUID, claim: Claim) -> str:
    """Reçu pas (encore) sur le serveur : authentique s'il est signé par l'appareil dont le
    préfixe est dans son numéro (`ITIG-P1-26-000184`). Appareil inconnu ou déconnecté par
    l'école, encaissement refusé à la synchronisation : inconnu."""
    parts = claim.number.split("-")
    if len(parts) != 4 or parts[0] != school.code.upper():
        return UNKNOWN
    device = Device.objects.filter(prefix=parts[1]).first()
    if device is None or device.revoked_at is not None:
        return UNKNOWN
    if SyncOperation.objects.filter(
        op_id=payment_id, status=SyncOperation.Status.REJECTED
    ).exists():
        return UNKNOWN
    if claim.currency not in Currency.values:
        return FORGED
    return (
        PENDING if verify_signature(device, claim.message(payment_id), claim.signature) else FORGED
    )


@require_GET
@never_cache
def verify_receipt(request: HttpRequest, payment_id: UUID) -> HttpResponse:
    """Reçu de l'école de l'adresse seulement : celui d'une autre école est « inconnu » (404).
    Jamais en cache : un reçu peut être annulé ou arriver par la synchronisation ; jamais indexé
    par les moteurs de recherche."""
    if request.school is None:
        raise Http404
    payment = (
        Payment.objects.select_related(
            "enrollment__student",
            "enrollment__class_group__level",
            "enrollment__class_group__track",
            "cash_session__cash_register",
            "cancellation",
        )
        .filter(pk=payment_id)
        .first()
    )
    try:
        claim = Claim.read(request.GET)
    except ValueError:
        state = FORGED
    else:
        if payment is None:
            state = _offline_state(request.school, payment_id, claim) if claim else UNKNOWN
        elif claim is not None and not claim.matches(payment):
            state = FORGED
        else:
            state = CANCELLED if hasattr(payment, "cancellation") else VALID
    context = {"school_name": request.school.name, "state": state}
    if state in (VALID, CANCELLED):
        context.update(
            cancelled_at=payment.cancellation.approved_at if state == CANCELLED else None,
            receipt_number=payment.receipt_number,
            paid_at=payment.paid_at,
            student=initials(payment.enrollment.student),
            class_group=payment.enrollment.class_group.name,
            amount=format_amount(payment.received_amount_minor, payment.received_currency),
        )
    elif state == PENDING:
        context.update(
            receipt_number=claim.number,
            paid_at=datetime.fromtimestamp(claim.time, UTC),
            register=claim.register,
            amount=format_amount(claim.amount, claim.currency),
        )
    response = render(
        request,
        "finance/receipt_verification.html",
        context,
        status=404 if state == UNKNOWN else 200,
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response

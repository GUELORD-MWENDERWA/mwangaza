"""Page publique de vérification d'un reçu `/v/{id}` (F4, maquette `portail/verification-recu`),
ouverte par le QR code du reçu sur l'adresse de l'école. Page HTML sans JavaScript ni connexion :
légère sur n'importe quel téléphone. Le minimum : école, numéro, date, montant, état ; l'élève en
initiales seulement. Reçu émis hors ligne (signature de l'appareil) et reçu falsifié : 3.3."""

from uuid import UUID

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.core.money import format_amount
from apps.finance.models import Payment
from apps.students.models import Student

VALID, CANCELLED, UNKNOWN = "valid", "cancelled", "unknown"


def initials(student: Student) -> str:
    """« KASEREKA Muhindo Jean » → « K. M. J. » : nom, post-nom, prénom."""
    names = [student.last_name, student.middle_name, student.first_name]
    return " ".join(f"{word[0].upper()}." for name in names for word in name.split())


@require_GET
@never_cache
def verify_receipt(request: HttpRequest, payment_id: UUID) -> HttpResponse:
    """Reçu de l'école de l'adresse seulement : celui d'une autre école est « inconnu » (404).
    Jamais en cache : un reçu peut être annulé ; jamais indexé par les moteurs de recherche."""
    if request.school is None:
        raise Http404
    payment = (
        Payment.objects.select_related(
            "enrollment__student",
            "enrollment__class_group__level",
            "enrollment__class_group__track",
            "cancellation",
        )
        .filter(pk=payment_id)
        .first()
    )
    context = {"school_name": request.school.name, "state": UNKNOWN}
    if payment is not None:
        cancellation = getattr(payment, "cancellation", None)
        context.update(
            state=CANCELLED if cancellation else VALID,
            cancelled_at=cancellation.approved_at if cancellation else None,
            receipt_number=payment.receipt_number,
            paid_at=payment.paid_at,
            student=initials(payment.enrollment.student),
            class_group=payment.enrollment.class_group.name,
            amount=format_amount(payment.received_amount_minor, payment.received_currency),
        )
    response = render(
        request,
        "finance/receipt_verification.html",
        context,
        status=404 if payment is None else 200,
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response

"""Page publique de vérification d'un bulletin imprimé `/v/b/<jeton>` (8.3.2), ouverte par le QR
code du bulletin sur l'adresse de l'école : école, élève en initiales, classe, année, résultat
(pourcentage, place) tel qu'imprimé à la date du bulletin. Page HTML sans JavaScript ni
connexion."""

from datetime import date
from decimal import Decimal

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.academics import report_card_documents
from apps.finance.verification import UNKNOWN, VALID, initials
from apps.students.models import Enrollment


@require_GET
@never_cache
def verify_report_card(request: HttpRequest, token: str) -> HttpResponse:
    """Bulletin imprimé : ce que disait le document (date, pourcentage, place), l'élève en
    initiales. Jeton modifié, signé pour une autre école ou inscription inconnue : « inconnu »
    (404)."""
    if request.school is None:
        raise Http404
    data = report_card_documents.read_token(token)
    enrollment = None
    if data is not None:
        enrollment = (
            Enrollment.objects.select_related("student", "class_group__academic_year")
            .filter(pk=data["e"])
            .first()
        )
    context = {"school_name": request.school.name, "state": VALID if enrollment else UNKNOWN}
    if enrollment is not None:
        context.update(
            day=date.fromisoformat(data["d"]),
            student=initials(enrollment.student),
            class_group=enrollment.class_group.name,
            year=enrollment.class_group.academic_year.name,
            percent=Decimal(data["p"]) if data["p"] else None,
            place=data["r"],
            size=data["n"],
        )
    response = render(
        request,
        "academics/report_card_verification.html",
        context,
        status=200 if enrollment else 404,
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response

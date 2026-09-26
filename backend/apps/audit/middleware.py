from django.http import HttpRequest, HttpResponse

from apps.accounts import support
from apps.audit.context import RequestInfo, use_request_info
from apps.core.http import client_ip, user_agent


class AuditMiddleware:
    """Adresse IP et navigateur de la requête (colonne « Appareil » de M6) et session support
    en cours dans l'école de l'adresse (A3), pour les entrées du journal écrites pendant
    celle-ci."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        session = support.current(request)
        info = RequestInfo(
            ip=client_ip(request),
            user_agent=user_agent(request),
            impersonated_by=request.user if session else None,
            support_school_id=session.school.pk if session else None,
        )
        with use_request_info(info):
            return self.get_response(request)

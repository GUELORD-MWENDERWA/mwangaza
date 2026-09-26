from django.http import HttpRequest, HttpResponse

from apps.audit.context import RequestInfo, use_request_info
from apps.core.http import client_ip, user_agent


class AuditMiddleware:
    """Adresse IP et navigateur de la requête, pour les entrées du journal écrites pendant
    celle-ci (colonne « Appareil » de M6)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        with use_request_info(RequestInfo(ip=client_ip(request), user_agent=user_agent(request))):
            return self.get_response(request)

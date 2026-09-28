from django.http import HttpRequest, HttpResponse

from apps.accounts import support
from apps.audit.context import RequestInfo, use_request_info
from apps.core.http import client_ip, user_agent
from apps.sync.services import session_device


class AuditMiddleware:
    """Adresse IP, navigateur et appareil enregistré de la requête (colonne « Appareil » de M6) et
    session support
    en cours dans l'école de l'adresse (A3), pour les entrées du journal écrites pendant
    celle-ci."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        session = support.current(request)
        school = getattr(request, "school", None)
        info = RequestInfo(
            ip=client_ip(request),
            user_agent=user_agent(request),
            impersonated_by=request.user if session else None,
            support_school_id=session.school.pk if session else None,
            device_id=session_device(getattr(request, "session", {}), school),
            device_school_id=school.pk if school else None,
        )
        with use_request_info(info):
            return self.get_response(request)

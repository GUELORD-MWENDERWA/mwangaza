"""École de chaque requête, lue dans le sous-domaine : {code}.mwangaza.school.

En développement : {code}.localhost (réglage `SCHOOL_BASE_DOMAINS`).
"""

from contextlib import nullcontext
from zoneinfo import ZoneInfo

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.http.request import split_domain_port
from django.utils import timezone

from apps.core.errors import SCHOOL_NOT_FOUND, SCHOOL_STOPPED, SCHOOL_SUSPENDED, ApiError
from apps.core.tenancy import CONSOLE_SUBDOMAIN, RESERVED_SUBDOMAINS, use_school
from apps.schools.models import School


def school_code_from_host(host: str) -> str | None:
    """Code de l'école, ou None pour un hôte de la plateforme (portail, super-admin, santé)."""
    domain, _port = split_domain_port(host)
    for base_domain in settings.SCHOOL_BASE_DOMAINS:
        suffix = f".{base_domain}"
        if domain.endswith(suffix):
            code = domain.removesuffix(suffix)
            return None if code in RESERVED_SUBDOMAINS else code
    return None


def is_console_host(host: str) -> bool:
    """Adresse de la console de la plateforme (`admin.mwangaza.school`, 5.2) : celle du
    super-admin, sans école."""
    domain, _port = split_domain_port(host)
    return any(domain == f"{CONSOLE_SUBDOMAIN}.{base}" for base in settings.SCHOOL_BASE_DOMAINS)


def _error_response(error: ApiError) -> JsonResponse:
    return JsonResponse(error.body(), status=error.status)


def _school_timezone(school: School | None):
    # Dates et heures de l'école (filtres par jour, affichage) ; sinon `TIME_ZONE`.
    return timezone.override(ZoneInfo(school.timezone)) if school else nullcontext()


# Identité de la plateforme : l'écran « école suspendue » donne le contact du support.
PLATFORM_PATH = "/api/platform/"


class TenantMiddleware:
    """Charge l'école du sous-domaine dans `request.school` et en fait l'école courante pendant la
    requête, avec son fuseau horaire. École inconnue : 404 ; suspendue ou arrêtée : 403, sauf
    l'identité de la plateforme (`PLATFORM_PATH`), lisible partout. Le rôle de l'utilisateur dans
    l'école est vérifié par les permissions de l'API (tâches 1.2 et 1.3), après
    l'authentification."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        school = None
        code = school_code_from_host(request.get_host())
        if code is not None and not request.path.startswith(PLATFORM_PATH):
            school = School.objects.filter(code=code).first()
            if school is None:
                return _error_response(SCHOOL_NOT_FOUND)
            if school.status == School.Status.STOPPED:
                return _error_response(SCHOOL_STOPPED)
            if school.status == School.Status.SUSPENDED:
                return _error_response(SCHOOL_SUSPENDED)
        request.school = school
        with use_school(school), _school_timezone(school):
            return self.get_response(request)

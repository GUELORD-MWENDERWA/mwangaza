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
from apps.core.tenancy import (
    CONSOLE_SUBDOMAIN,
    RESERVED_SUBDOMAINS,
    use_all_schools,
    use_school,
    use_schools,
)
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
            # En cours de suppression (4.16) : pour tout le monde, l'espace n'existe déjà plus.
            if school is None or school.status == School.Status.DELETING:
                return _error_response(SCHOOL_NOT_FOUND)
            if school.status == School.Status.STOPPED:
                return _error_response(SCHOOL_STOPPED)
            if school.status == School.Status.SUSPENDED:
                return _error_response(SCHOOL_SUSPENDED)
        request.school = school
        with use_school(school), _school_timezone(school):
            return self.get_response(request)


PORTAL_PATH = "/api/portal/"
ADMIN_PATH = "/admin/"


def _db_scope(request: HttpRequest):
    """Portée de la base d'une requête sans école (S.6) : toutes les écoles pour l'équipe de la
    plateforme avec au moins un droit (console, administration Django), les écoles de ses familles
    pour un parent (Portail), aucune sinon."""
    user = request.user
    if not user.is_authenticated:
        return nullcontext()
    # Membre de l'équipe avec au moins un droit (EQ.1) ; chaque point vérifie ensuite le sien.
    if user.platform_permissions and (
        is_console_host(request.get_host()) or request.path.startswith(ADMIN_PATH)
    ):
        return use_all_schools()
    if request.path.startswith(PORTAL_PATH):
        from apps.students.models import Family

        with use_all_schools():
            school_ids = list(
                Family.all_schools.filter(primary_user=user).values_list("school_id", flat=True)
            )
        return use_schools(school_ids)
    return nullcontext()


class RowSecurityMiddleware:
    """Après l'authentification : portée de la base des requêtes sans école (`_db_scope`). Celles
    d'une école ont déjà la sienne (`TenantMiddleware`)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.school is not None:
            return self.get_response(request)
        with _db_scope(request):
            return self.get_response(request)

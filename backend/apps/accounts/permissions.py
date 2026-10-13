"""Permission serveur des points d'API d'une école (règle 6 de `CLAUDE.md`)."""

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts import support
from apps.accounts.login import MFA_SESSION_KEY
from apps.accounts.roles import TOTP_PERMISSIONS
from apps.accounts.services import SchoolAccess, get_school_access
from apps.core.errors import SCHOOL_NOT_FOUND
from apps.core.middleware import is_console_host


def school_access(request) -> SchoolAccess | None:
    """Droits du compte dans l'école de l'adresse, calculés une fois par requête : ceux de la
    session support si elle est ouverte (`support.py`), sinon ceux de ses rôles."""
    if not hasattr(request, "_school_access"):
        request._school_access = support.access(request) or get_school_access(
            request.user, request.school
        )
    return request._school_access


def ensure_module(school, view) -> None:
    """Vue réservée à un module (`required_module`) que l'école n'a pas : 403 `module_missing`,
    sans toucher aux données."""
    module = getattr(view, "required_module", None)
    if module and not school.has_module(module):
        raise PermissionDenied(_("This school does not have this feature."), code="module_missing")


class HasSchoolPermission(BasePermission):
    """Accès seulement depuis l'adresse d'une école, avec un compte actif qui y a une appartenance
    active et un rôle portant le code `required_permission` de la vue (ex. `roles.manage`), ou un
    des codes quand la vue en donne plusieurs (ex. lire les classes : `classes.manage` ou
    `students.view`).
    L'interface ne fait que masquer ce qui est refusé ici.

    Des droits qui exigent la double authentification (B4) demandent aussi une session passée
    par elle : sinon `totp_required` (ex. rôle de caissier donné pendant la session), et
    l'interface renvoie vers la connexion."""

    def has_permission(self, request, view) -> bool:
        if request.school is None:
            raise NotFound(SCHOOL_NOT_FOUND.detail, code=SCHOOL_NOT_FOUND.code)
        access = school_access(request)
        if access is None:
            return False
        # Sauf dans un espace de démonstration, où elle n'est pas demandée (`03` § 4 bis).
        if (
            access.permissions & TOTP_PERMISSIONS
            and not request.school.is_demo
            and not request.session.get(MFA_SESSION_KEY)
        ):
            raise PermissionDenied(
                _("Your roles in this school require two-factor authentication: log in again."),
                code="totp_required",
            )
        ensure_module(request.school, view)
        required = view.required_permission
        if isinstance(required, str):
            return required in access.permissions
        return not access.permissions.isdisjoint(required)


class HasSchoolAccess(BasePermission):
    """Tout compte qui a des droits dans l'école de l'adresse, quels qu'ils soient (appartenance
    active ou session support) : ce que tout le personnel lit (annonces de la plateforme)."""

    def has_permission(self, request, view) -> bool:
        if request.school is None:
            raise NotFound(SCHOOL_NOT_FOUND.detail, code=SCHOOL_NOT_FOUND.code)
        return school_access(request) is not None


class IsPlatformAdmin(BasePermission):
    """Console de la plateforme (5.2) : seulement à son adresse (`admin.mwangaza.school`), pour
    un super-admin actif dont la session est passée par la double authentification. Ailleurs (une
    école, le portail), ces points d'API n'existent pas."""

    def has_permission(self, request, view) -> bool:
        if not is_console_host(request.get_host()):
            raise NotFound
        user = request.user
        return bool(
            user.is_authenticated
            and user.is_active
            and user.is_platform_admin
            and request.session.get(MFA_SESSION_KEY)
        )

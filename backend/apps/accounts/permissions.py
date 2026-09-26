"""Permission serveur des points d'API d'une école (règle 6 de `CLAUDE.md`)."""

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts import support
from apps.accounts.login import MFA_SESSION_KEY
from apps.accounts.roles import TOTP_PERMISSIONS
from apps.accounts.services import SchoolAccess, get_school_access
from apps.core.errors import SCHOOL_NOT_FOUND


def school_access(request) -> SchoolAccess | None:
    """Droits du compte dans l'école de l'adresse, calculés une fois par requête : ceux de la
    session support si elle est ouverte (`support.py`), sinon ceux de ses rôles."""
    if not hasattr(request, "_school_access"):
        request._school_access = support.access(request) or get_school_access(
            request.user, request.school
        )
    return request._school_access


class HasSchoolPermission(BasePermission):
    """Accès seulement depuis l'adresse d'une école, avec un compte actif qui y a une appartenance
    active et un rôle portant le code `required_permission` de la vue (ex. `roles.manage`).
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
        if access.permissions & TOTP_PERMISSIONS and not request.session.get(MFA_SESSION_KEY):
            raise PermissionDenied(
                _("Your roles in this school require two-factor authentication: log in again."),
                code="totp_required",
            )
        return view.required_permission in access.permissions

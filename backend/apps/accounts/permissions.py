"""Permission serveur des points d'API d'une école (règle 6 de `CLAUDE.md`)."""

from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission

from apps.accounts.services import SchoolAccess, get_school_access
from apps.core.errors import SCHOOL_NOT_FOUND


def school_access(request) -> SchoolAccess | None:
    """Droits du compte dans l'école de l'adresse, calculés une fois par requête."""
    if not hasattr(request, "_school_access"):
        request._school_access = get_school_access(request.user, request.school)
    return request._school_access


class HasSchoolPermission(BasePermission):
    """Accès seulement depuis l'adresse d'une école, avec un compte actif qui y a une appartenance
    active et un rôle portant le code `required_permission` de la vue (ex. `roles.manage`).
    L'interface ne fait que masquer ce qui est refusé ici."""

    def has_permission(self, request, view) -> bool:
        if request.school is None:
            raise NotFound(SCHOOL_NOT_FOUND.detail, code=SCHOOL_NOT_FOUND.code)
        access = school_access(request)
        return access is not None and view.required_permission in access.permissions

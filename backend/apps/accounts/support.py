"""Session support « en tant qu'école » (A3, maquette `gestion/superadmin-ecoles`).

Le super-admin se connecte **à l'adresse de l'école** comme tout le monde (mot de passe et code),
puis ouvre une session support avec un motif. Pendant une heure au plus, il a les droits de
l'école, sauf la caisse (`SUPPORT_PERMISSIONS`) ; l'interface affiche un bandeau rouge
permanent (`/api/me/`). Ouverture, fermeture et chaque action de la session vont dans le journal
de l'école, avec `impersonated_by` ; l'école y voit « Support » suivi du nom de la plateforme.

La session est gardée dans la session Django de cette adresse : elle ne donne rien dans une autre
école.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from django.utils.translation import gettext_lazy as _

from apps.accounts.login import MFA_SESSION_KEY
from apps.accounts.roles import PERMISSIONS
from apps.accounts.services import SchoolAccess
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import SCHOOL_NOT_FOUND, ApiError, BusinessError
from apps.schools.models import School

SUPPORT_SESSION_KEY = "accounts.support"
SUPPORT_DURATION = 60 * 60
# Le support ne touche pas à l'argent de la caisse.
SUPPORT_EXCLUDED_PERMISSIONS = frozenset(
    {
        "finance.collect_payment",
        "finance.request_cancellation",
        "finance.approve_cancellation",
        "finance.close_register",
    }
)
SUPPORT_PERMISSIONS = frozenset(PERMISSIONS) - SUPPORT_EXCLUDED_PERMISSIONS

NOT_PLATFORM_ADMIN = ApiError(
    "not_platform_admin", _("Only the platform support can open a support session."), 403
)
SUPPORT_TOTP_REQUIRED = ApiError(
    "totp_required", _("Log in again with two-factor authentication."), 403
)
NO_SUPPORT_SESSION = ApiError(
    "no_support_session", _("No support session is open in this school."), 404
)


@dataclass(frozen=True)
class SupportSession:
    school: School
    reason: str
    started_at: datetime
    expires_at: datetime


def _datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


def current(request) -> SupportSession | None:
    """La session support ouverte à l'adresse de cette école, si elle vaut encore : compte
    toujours super-admin et actif, session passée par la double authentification, moins d'une
    heure. Expirée ou plus valable : oubliée."""
    session = getattr(request, "session", None)
    data = session.get(SUPPORT_SESSION_KEY) if session is not None else None
    school = getattr(request, "school", None)
    if data is None or school is None or data["school"] != str(school.pk):
        return None
    user = request.user
    valid = (
        user.is_authenticated
        and user.is_active
        and user.is_platform_admin
        and request.session.get(MFA_SESSION_KEY)
        and time.time() < data["expires"]
        and school.status != School.Status.SUSPENDED
    )
    if not valid:
        del request.session[SUPPORT_SESSION_KEY]
        return None
    return SupportSession(
        school=school,
        reason=data["reason"],
        started_at=_datetime(data["started"]),
        expires_at=_datetime(data["expires"]),
    )


def access(request) -> SchoolAccess | None:
    """Droits dans l'école pendant la session support : tous, sauf la caisse."""
    if current(request) is None:
        return None
    return SchoolAccess(membership=None, roles=(), permissions=SUPPORT_PERMISSIONS)


def start(request, reason: str) -> SupportSession:
    """Ouvrir (ou rouvrir) la session support dans l'école de l'adresse."""
    school = request.school
    if school is None:
        raise BusinessError(SCHOOL_NOT_FOUND)
    user = request.user
    if not user.is_platform_admin:
        raise BusinessError(NOT_PLATFORM_ADMIN)
    if not request.session.get(MFA_SESSION_KEY):
        raise BusinessError(SUPPORT_TOTP_REQUIRED)
    end(request)
    now = time.time()
    request.session[SUPPORT_SESSION_KEY] = {
        "school": str(school.pk),
        "reason": reason,
        "started": now,
        "expires": now + SUPPORT_DURATION,
    }
    session = current(request)
    audit.record(
        Action.SUPPORT_STARTED,
        school,
        actor=user,
        impersonated_by=user,
        after={"reason": reason, "expires_at": session.expires_at},
    )
    return session


def end(request) -> bool:
    """Fermer la session support (bouton du bandeau, déconnexion) ; False s'il n'y en a pas."""
    session = current(request)
    if session is None:
        return False
    del request.session[SUPPORT_SESSION_KEY]
    user = request.user
    audit.record(Action.SUPPORT_ENDED, session.school, actor=user, impersonated_by=user)
    return True

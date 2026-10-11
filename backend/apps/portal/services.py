"""Accès au portail des familles (H1, M19) : activation avec le code famille, nouveau mot de passe
avec un nouveau code (« Mot de passe oublié »).

Le portail n'a pas d'école : une famille se cherche sur toute la plateforme (`all_schools`),
seulement par son code, et seulement avec le numéro qui lui correspond. Jamais par le numéro seul
(un numéro mal saisi par une école ne doit rien ouvrir, `03` § 4)."""

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts import attempts, login
from apps.accounts.models import Membership, User
from apps.accounts.phone import InvalidPhoneError, normalize_phone
from apps.accounts.services import ensure_number_fits_space
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.http import client_ip
from apps.core.tenancy import use_school
from apps.students.models import Family, Guardian

INVALID_FAMILY_CODE = ApiError("invalid_family_code", _("Wrong phone number or family code."), 400)
ALREADY_ACTIVATED = ApiError(
    "already_activated",
    _("This family already has an account: log in, or ask the school for a new code."),
    409,
)
NOT_ACTIVATED = ApiError(
    "not_activated", _("This family has no account yet: activate it with this code."), 409
)
ACCOUNT_EXISTS = ApiError(
    "account_exists", _("This phone number already has an account: log in."), 409
)
STAFF_ACCOUNT = ApiError(
    "staff_account",
    _("This account is also used by school staff: ask the platform support for a new password."),
    403,
)
SCHOOL_UNAVAILABLE = ApiError(
    "school_unavailable", _("This school's service is temporarily unavailable."), 403
)
PORTAL_SUSPENDED = ApiError(
    "portal_suspended",
    _("The school has suspended portal access for this family: contact its office."),
    403,
)
# Le numéro n'est pas tapé : un message qui ne dit pas lequel des deux ne va pas.
INVALID_LINK_CODE = ApiError(
    "invalid_link_code",
    _("Unknown family code, or the school has another phone number for the main contact."),
    400,
)


def _clean_code(code: str) -> str:
    """« k7m4-p9tx » comme imprimé, en deux groupes de 4 : « K7M4P9TX »."""
    return code.replace("-", "").replace(" ", "").upper()


def _expected_phone(family: Family) -> str | None:
    """Le numéro du compte relié, sinon celui du tuteur principal (fiche de l'école)."""
    if family.primary_user is not None:
        return family.primary_user.phone
    primary = next((g for g in family.guardians.all() if g.is_primary), None)
    try:
        return normalize_phone(primary.phone) if primary and primary.phone else None
    except InvalidPhoneError:
        return None


def _family(
    request, phone: str, code: str, *, renewed_only: bool, error: ApiError = INVALID_FAMILY_CODE
) -> Family:
    """La famille de ce code, s'il est encore valable et que `phone` lui correspond. Sinon, une
    seule erreur pour tous les cas (rien à deviner) et un essai compté pour ce numéro.
    `renewed_only` : seulement un code donné par « Nouveau code » (le premier code, imprimé sur la
    fiche d'inscription, ne change jamais un mot de passe)."""
    key, ip = attempts.phone_key(phone), client_ip(request)
    attempts.ensure_allowed(key, ip)
    family = (
        Family.all_schools.select_related("school", "primary_user")
        # Tuteurs de cette famille seulement (le portail n'a pas d'école courante).
        .prefetch_related(Prefetch("guardians", queryset=Guardian.all_schools.all()))
        .filter(code=_clean_code(code))
        .first()
    )
    expires = family.code_expires_at if family else None
    valid = family is not None and (expires > timezone.now() if expires else not renewed_only)
    if not valid or _expected_phone(family) != phone:
        attempts.record_failure(key, ip)
        raise BusinessError(error)
    if family.school.is_closed:
        raise BusinessError(SCHOOL_UNAVAILABLE)
    # Numéro et code justes : rien à deviner, on peut dire pourquoi ce compte n'entre pas ici.
    ensure_number_fits_space(phone, family.school)
    if family.portal_suspended_at is not None:
        raise BusinessError(PORTAL_SUSPENDED)
    return family


def _link(family: Family, user: User) -> None:
    """Relie la famille (verrouillée) au compte ; son code a servi."""
    family.primary_user = user
    family.activated_at = timezone.now()
    family.code_expires_at = None
    family.save(update_fields=["primary_user", "activated_at", "code_expires_at", "updated_at"])
    audit.record(Action.PORTAL_ACTIVATED, family, actor=user, label=str(user))


def activate(request, *, phone: str, code: str, password: str, remember: bool) -> User:
    """Première visite : le numéro du tuteur principal et le code famille créent le compte, relié
    à cette famille, et le connectent. Numéro qui a déjà un compte : il se connecte (relier une
    autre école : « Ajouter un enfant d'une autre école »)."""
    family = _family(request, phone, code, renewed_only=False)
    if family.primary_user_id is not None:
        raise BusinessError(ALREADY_ACTIVATED)
    if User.objects.filter(phone=phone).exists():
        raise BusinessError(ACCOUNT_EXISTS)
    primary = next(g for g in family.guardians.all() if g.is_primary)
    with transaction.atomic(), use_school(family.school):
        # Deux activations en même temps : la seconde trouve la famille déjà reliée.
        locked = Family.objects.select_for_update().get(pk=family.pk)
        if locked.primary_user_id is not None:
            raise BusinessError(ALREADY_ACTIVATED)
        user = User.objects.create_user(phone, password, last_name=primary.full_name[:100])
        _link(locked, user)
    login.open_portal_session(request, user, remember=remember)
    return user


def link_family(request, *, code: str) -> Family:
    """« Ajouter un enfant d'une autre école » (H2) : le code famille remis par cette école, si
    son tuteur principal a le numéro du compte (comme l'activation). Jamais par le numéro seul.
    Une famille déjà reliée à ce compte le reste."""
    user = request.user
    family = _family(request, user.phone, code, renewed_only=False, error=INVALID_LINK_CODE)
    if family.primary_user_id == user.pk:
        return family
    with transaction.atomic(), use_school(family.school):
        locked = Family.objects.select_for_update().get(pk=family.pk)
        if locked.primary_user_id is not None:
            raise BusinessError(ALREADY_ACTIVATED)
        _link(locked, user)
    return locked


def reset_password(request, *, phone: str, code: str, password: str, remember: bool) -> User:
    """« Mot de passe oublié » : le numéro du compte et le nouveau code donné par l'école (une
    seule fois) ; les autres sessions du compte sont fermées (mot de passe changé), celle-ci
    s'ouvre. Pas pour un compte du personnel : il sert dans une école (`03` § 4, support)."""
    family = _family(request, phone, code, renewed_only=True)
    user = family.primary_user
    if user is None:
        raise BusinessError(NOT_ACTIVATED)
    if user.is_platform_admin or Membership.objects.filter(user=user, is_active=True).exists():
        raise BusinessError(STAFF_ACCOUNT)
    with transaction.atomic(), use_school(family.school):
        locked = Family.objects.select_for_update().get(pk=family.pk)
        if locked.code_expires_at is None or locked.code != family.code:
            raise BusinessError(INVALID_FAMILY_CODE)
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])
        locked.code_expires_at = None
        locked.save(update_fields=["code_expires_at", "updated_at"])
        audit.record(Action.PORTAL_PASSWORD_RESET, locked, actor=user, label=str(user))
    login.open_portal_session(request, user, remember=remember)
    return user

"""Comptes, rôles et appartenances : règles métier (`docs/04-modele-de-donnees.md` § 1 et § 8).

Les services qui changent les rôles et les comptes d'une école travaillent dans l'école courante
(requête sur son sous-domaine, ou `use_school`). L'audit de ces changements arrive avec
`AuditLog` (tâche 1.4) : rôles, comptes du personnel, mot de passe et double authentification.
"""

import logging
import secrets
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext_lazy as _

from apps.accounts import totp
from apps.accounts.models import Membership, RecoveryCode, Role, User
from apps.accounts.phone import normalize_phone
from apps.accounts.roles import ROLES_MANAGE, SYSTEM_ROLES, TOTP_PERMISSIONS, sorted_permissions
from apps.core.crypto import DecryptionError, decrypt, encrypt
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import CrossSchoolError, require_current_school, use_school
from apps.schools.models import School

logger = logging.getLogger(__name__)

LAST_ROLE_MANAGER = ApiError(
    "last_role_manager",
    _("This change would leave the school without an active account that can manage roles."),
    409,
)
SYSTEM_ROLE = ApiError("system_role", _("A system role cannot be deleted."), 409)
ROLE_IN_USE = ApiError(
    "role_in_use", _("This role is still given to accounts: remove it from them first."), 409
)
ROLE_NAME_TAKEN = ApiError(
    "role_name_taken", _("The school already has a role with this name."), 409
)
ROLE_NAME_REQUIRED = ApiError(
    "role_name_required", _("A role created by the school needs a name."), 400
)
ALREADY_MEMBER = ApiError(
    "already_member", _("This phone number already has an account in this school."), 409
)
NAMES_REQUIRED = ApiError(
    "names_required", _("This phone number has no account yet: enter the last name."), 400
)
ACCOUNT_USED_ELSEWHERE = ApiError(
    "account_used_elsewhere",
    _("This account is also used outside this school: only Mwangaza support can change it."),
    409,
)
PHONE_TAKEN = ApiError("phone_taken", _("This phone number already has an account."), 409)
INVALID_CODE = ApiError(
    "invalid_code", _("This code is not valid, or it has already been used."), 400
)
WRONG_PASSWORD = ApiError("wrong_password", _("The current password is not correct."), 400)
TOTP_STILL_REQUIRED = ApiError(
    "totp_still_required",
    _("One of your roles requires two-factor authentication: it cannot be turned off."),
    409,
)

# Sans lettres ni chiffres qu'on confond en les dictant ou en les recopiant (l, 1, o, 0, i).
_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


# Rôles système


def create_system_roles(school: School) -> list[Role]:
    """Copie dans l'école les rôles système qui lui manquent, avec leurs permissions par défaut
    (`docs/04` § 8). Relançable : un rôle déjà là n'est pas touché."""
    with use_school(school):
        existing = set(Role.objects.exclude(code="").values_list("code", flat=True))
        return Role.objects.bulk_create(
            Role(code=code, permissions=list(role.permissions))
            for code, role in SYSTEM_ROLES.items()
            if code not in existing
        )


# Droits dans une école


@dataclass(frozen=True)
class SchoolAccess:
    membership: Membership
    roles: tuple[Role, ...]
    permissions: frozenset[str]


def get_school_access(user, school: School | None) -> SchoolAccess | None:
    """Rôles et permissions du compte dans l'école ; None s'il n'y a pas d'appartenance active
    (compte désactivé, retiré de l'école, ou pas d'école). Le super-admin n'a aucun droit dans
    une école sans y avoir de rôle."""
    if school is None or not user.is_authenticated or not user.is_active:
        return None
    membership = Membership.objects.filter(user=user, school=school, is_active=True).first()
    if membership is None:
        return None
    with use_school(school):
        roles = tuple(Role.objects.filter(memberships=membership))
    permissions = frozenset(code for role in roles for code in role.permissions)
    return SchoolAccess(membership, roles, permissions)


def _has_role_manager(school: School) -> bool:
    return Membership.objects.filter(
        school=school,
        is_active=True,
        user__is_active=True,
        roles__permissions__contains=[ROLES_MANAGE],
    ).exists()


@contextmanager
def _keeping_a_role_manager(school: School) -> Iterator[None]:
    """Refuse un changement qui laisserait l'école sans compte actif capable de gérer les rôles
    (maquette M3 : « impossible de se retirer soi-même le dernier rôle de directeur »). À utiliser
    dans une transaction : le refus annule le changement."""
    # Les changements de rôles d'une école passent un par un : deux directeurs qui se retirent
    # le rôle en même temps ne peuvent pas laisser l'école sans gestionnaire.
    School.objects.select_for_update().get(pk=school.pk)
    had_one = _has_role_manager(school)
    yield
    if had_one and not _has_role_manager(school):
        raise BusinessError(LAST_ROLE_MANAGER)


# Rôles


def _check_role_name(name: str, *, is_system: bool, role_id=None) -> None:
    if not name:
        if not is_system:
            raise BusinessError(ROLE_NAME_REQUIRED)
        return
    if Role.objects.filter(name__iexact=name).exclude(pk=role_id).exists():
        raise BusinessError(ROLE_NAME_TAKEN)


def create_role(*, actor: User, name: str, permissions: Iterable[str]) -> Role:
    """Rôle propre à l'école courante (B2), ex. « Chef d'atelier »."""
    require_current_school()
    name = name.strip()
    with transaction.atomic():
        _check_role_name(name, is_system=False)
        return Role.objects.create(
            name=name, permissions=sorted_permissions(permissions), created_by=actor
        )


def update_role(
    role: Role, *, actor: User, name: str | None = None, permissions: Iterable[str] | None = None
) -> Role:
    """Renommer un rôle (nom vide pour un rôle système = son nom traduit) ou changer ses
    permissions."""
    with transaction.atomic(), _keeping_a_role_manager(role.school):
        fields = ["updated_at"]
        if name is not None:
            role.name = name.strip()
            _check_role_name(role.name, is_system=role.is_system, role_id=role.pk)
            fields.append("name")
        if permissions is not None:
            role.permissions = sorted_permissions(permissions)
            fields.append("permissions")
        role.save(update_fields=fields)
    return role


def delete_role(role: Role, *, actor: User) -> None:
    """Supprimer un rôle créé par l'école, s'il n'est plus donné à personne."""
    if role.is_system:
        raise BusinessError(SYSTEM_ROLE)
    with transaction.atomic():
        if role.memberships.exists():
            raise BusinessError(ROLE_IN_USE)
        role.delete()


# Comptes du personnel


def make_temporary_password() -> str:
    """Mot de passe provisoire facile à dicter : 3 groupes de 4 caractères (≈ 59 bits)."""
    groups = ("".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(4)) for _ in range(3))
    return "-".join(groups)


def add_staff_member(
    *,
    actor: User,
    phone: str,
    roles: Iterable[Role],
    last_name: str = "",
    middle_name: str = "",
    first_name: str = "",
) -> tuple[Membership, str | None]:
    """Donner accès à l'école courante à une personne, avec ses rôles.

    Numéro inconnu : nouveau compte, avec un mot de passe provisoire renvoyé une seule fois (à
    changer à la première connexion). Numéro connu : le compte existant est ajouté à l'école, sans
    nouveau mot de passe ni changement de ses noms, et sans rien dire de ses autres écoles (B3)."""
    school = require_current_school()
    phone = normalize_phone(phone)
    with transaction.atomic():
        user = User.objects.filter(phone=phone).first()
        temporary_password = None
        if user is None:
            if not last_name.strip():
                raise BusinessError(NAMES_REQUIRED)
            temporary_password = make_temporary_password()
            user = User.objects.create_user(
                phone,
                temporary_password,
                last_name=last_name.strip(),
                middle_name=middle_name.strip(),
                first_name=first_name.strip(),
                must_change_password=True,
                created_by=actor,
            )
        elif Membership.objects.filter(user=user, school=school).exists():
            raise BusinessError(ALREADY_MEMBER)
        membership = Membership.objects.create(user=user, school=school, created_by=actor)
        membership.roles.set(roles)
    return membership, temporary_password


def account_managed_by(user: User, school: School) -> bool:
    """L'école peut-elle modifier le compte lui-même (noms, téléphone, mot de passe, double
    authentification) ? Seulement s'il ne sert dans aucune autre école et n'est pas celui d'un
    super-admin : sinon, une école prendrait la main sur un compte qui donne accès ailleurs
    (`03` § 4). Aucune autre école n'est nommée."""
    if user.is_platform_admin:
        return False
    return not Membership.objects.filter(user=user).exclude(school=school).exists()


def _account_of(membership: Membership) -> User:
    school = require_current_school()
    if membership.school_id != school.pk:
        raise CrossSchoolError("Appartenance d'une autre école que l'école courante.")
    if not account_managed_by(membership.user, school):
        raise BusinessError(ACCOUNT_USED_ELSEWHERE)
    return membership.user


def update_staff_member(
    membership: Membership,
    *,
    actor: User,
    roles: Iterable[Role] | None = None,
    is_active: bool | None = None,
    **account: str,
) -> Membership:
    """Changer les rôles d'une personne dans l'école, la désactiver (plus aucun accès à cette
    école, son compte reste valable ailleurs) ou la réactiver. On ne supprime pas un compte.

    `account` : `last_name`, `middle_name`, `first_name`, `phone` du compte, seulement s'il ne
    sert que dans cette école (M4 : « adressez-vous au directeur »)."""
    school = require_current_school()
    if membership.school_id != school.pk:
        raise CrossSchoolError("Appartenance d'une autre école que l'école courante.")
    with transaction.atomic(), _keeping_a_role_manager(school):
        if account:
            _update_account(_account_of(membership), **account)
        if roles is not None:
            membership.roles.set(roles)
        if is_active is not None and is_active != membership.is_active:
            membership.is_active = is_active
            membership.save(update_fields=["is_active", "updated_at"])
    return membership


_ACCOUNT_FIELDS = {"last_name", "middle_name", "first_name", "phone"}


def _update_account(user: User, **fields: str) -> None:
    unknown = fields.keys() - _ACCOUNT_FIELDS
    if unknown:
        raise TypeError(f"Champs du compte inconnus : {sorted(unknown)}")
    if "phone" in fields:
        fields["phone"] = normalize_phone(fields["phone"])
        if User.objects.filter(phone=fields["phone"]).exclude(pk=user.pk).exists():
            raise BusinessError(PHONE_TAKEN)
    for field, value in fields.items():
        setattr(user, field, value.strip())
    user.save(update_fields=[*fields, "updated_at"])


def set_temporary_password(membership: Membership, *, actor: User) -> str:
    """« Nouveau mot de passe » (M3) : mot de passe provisoire renvoyé une seule fois, à changer
    à la prochaine connexion. Les sessions ouvertes de la personne sont fermées (Django lie la
    session au mot de passe)."""
    user = _account_of(membership)
    password = make_temporary_password()
    user.set_password(password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password", "updated_at"])
    return password


def reset_staff_totp(membership: Membership, *, actor: User) -> None:
    """« Réinitialiser la double auth. » (M3), ex. téléphone perdu : la personne la réactive à sa
    prochaine connexion si l'un de ses rôles l'exige."""
    reset_totp(_account_of(membership))


# Mot de passe


def change_password(user: User, new_password: str, *, current_password: str | None = None) -> None:
    """Nouveau mot de passe choisi par la personne (déjà validé par le serializer), après le mot
    de passe actuel s'il est donné (compte connecté). Les autres sessions du compte sont
    fermées ; la vue garde la session en cours."""
    if current_password is not None and not user.check_password(current_password):
        raise BusinessError(WRONG_PASSWORD)
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password", "updated_at"])


# Double authentification (B4)


def totp_required(user: User) -> bool:
    """Exigée si, dans une école où il est actif, le compte a un rôle portant un droit sensible
    (`roles.TOTP_PERMISSIONS`). Le compte étant unique, elle le protège alors partout."""
    return Membership.objects.filter(
        user=user, is_active=True, roles__permissions__overlap=sorted(TOTP_PERMISSIONS)
    ).exists()


_RECOVERY_SALT = "apps.accounts.recovery-code"


def _recovery_digests(code: str) -> list[str]:
    # Empreinte avec la clé du serveur ; aussi avec les anciennes clés après une rotation.
    raw = totp.normalize_recovery_code(code)
    if raw is None:
        return []
    return [
        salted_hmac(_RECOVERY_SALT, raw, secret=key, algorithm="sha256").hexdigest()
        for key in (settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS)
    ]


def _new_recovery_codes(user: User) -> list[str]:
    RecoveryCode.objects.filter(user=user).delete()
    codes = totp.new_recovery_codes()
    RecoveryCode.objects.bulk_create(
        RecoveryCode(user=user, digest=_recovery_digests(code)[0]) for code in codes
    )
    return codes


def recovery_codes_left(user: User) -> int:
    return RecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


def _totp_key(user: User) -> str | None:
    try:
        return decrypt(user.totp_secret)
    except DecryptionError:
        logger.error("Clé TOTP illisible pour le compte %s (SECRET_KEY changée ?)", user.pk)
        return None


def verify_second_factor(user: User, code: str) -> None:
    """Code TOTP du moment ou code de secours pas encore utilisé ; chacun ne sert qu'une fois
    (`INVALID_CODE` sinon). Les essais ratés sont comptés par l'appelant (`attempts.py`)."""
    with transaction.atomic():
        # Deux requêtes avec le même code en même temps : une seule passe.
        locked = User.objects.select_for_update().get(pk=user.pk)
        key = _totp_key(locked) if locked.totp_enabled else None
        step = totp.matching_step(key, code, after=locked.totp_last_step) if key else None
        if step is not None:
            locked.totp_last_step = user.totp_last_step = step
            locked.save(update_fields=["totp_last_step", "updated_at"])
            return
        digests = _recovery_digests(code)
        if digests and locked.totp_enabled:
            used = RecoveryCode.objects.filter(
                user=locked, digest__in=digests, used_at__isnull=True
            ).update(used_at=timezone.now())
            if used:
                return
    raise BusinessError(INVALID_CODE)


def enable_totp(user: User, secret: str, code: str) -> list[str]:
    """Activer la double authentification avec la clé montrée à la personne (M1), une fois le
    premier code vérifié ; aussi pour « changer de téléphone ». Renvoie les 8 codes de secours,
    affichés une seule fois."""
    step = totp.matching_step(secret, code)
    if step is None:
        raise BusinessError(INVALID_CODE)
    with transaction.atomic():
        user.totp_secret = encrypt(secret)
        user.totp_enabled_at = timezone.now()
        user.totp_last_step = step
        user.save(update_fields=["totp_secret", "totp_enabled_at", "totp_last_step", "updated_at"])
        return _new_recovery_codes(user)


def regenerate_recovery_codes(user: User, code: str) -> list[str]:
    """8 nouveaux codes de secours ; les anciens ne servent plus."""
    verify_second_factor(user, code)
    return _new_recovery_codes(user)


def disable_totp(user: User, code: str) -> None:
    """Refusé si l'un des rôles du compte l'exige (M4)."""
    if totp_required(user):
        raise BusinessError(TOTP_STILL_REQUIRED)
    verify_second_factor(user, code)
    reset_totp(user)


def reset_totp(user: User) -> None:
    """Sans code : par l'école (compte qui ne sert que chez elle) ou par le support."""
    with transaction.atomic():
        user.totp_secret = ""
        user.totp_enabled_at = None
        user.totp_last_step = 0
        user.save(update_fields=["totp_secret", "totp_enabled_at", "totp_last_step", "updated_at"])
        RecoveryCode.objects.filter(user=user).delete()

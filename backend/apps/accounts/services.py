"""Comptes, rôles et appartenances : règles métier (`docs/04-modele-de-donnees.md` § 1 et § 8).

Les services qui changent les rôles et les comptes d'une école travaillent dans l'école courante
(requête sur son sous-domaine, ou `use_school`).

Journal d'audit (1.4) : les changements de rôles et de comptes du personnel vont dans le journal
de l'école ; ce qui change un compte (mot de passe, double authentification, changements du
support dans l'administration Django) va dans le journal de chaque école où la personne est
active, sans dire où l'action a été faite (`_audit_account`).
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

from apps.accounts import modules, totp
from apps.accounts.models import Membership, RecoveryCode, Role, User
from apps.accounts.phone import demo_block, is_demo_phone, normalize_phone
from apps.accounts.roles import (
    ROLES_MANAGE,
    STARTER_ROLES,
    TOTP_PERMISSIONS,
    sorted_permissions,
    starter_role_name,
)
from apps.audit import services as audit
from apps.audit.actions import Action, PlatformAction
from apps.core.crypto import DecryptionError, decrypt, encrypt
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import CrossSchoolError, require_current_school, use_school
from apps.schools.models import Demonstration, School

logger = logging.getLogger(__name__)

LAST_ROLE_MANAGER = ApiError(
    "last_role_manager",
    _("This change would leave the school without an active account that can manage roles."),
    409,
)
ROLE_IN_USE = ApiError(
    "role_in_use", _("This role is still given to accounts: remove it from them first."), 409
)
ROLE_NAME_TAKEN = ApiError(
    "role_name_taken", _("The school already has a role with this name."), 409
)
ROLE_NAME_REQUIRED = ApiError("role_name_required", _("A role needs a name."), 400)
ALREADY_MEMBER = ApiError(
    "already_member", _("This phone number already has an account in this school."), 409
)
DEMO_NUMBER = ApiError(
    "demo_number",
    _("Numbers starting with 000 are kept for demonstration spaces."),
    400,
)
DEMO_SPACE_NUMBERS = ApiError(
    "demo_space_numbers",
    _(
        "A demonstration space only takes made-up numbers starting with 000 (for example "
        "0001234567): never a real number."
    ),
    400,
)
NAMES_REQUIRED = ApiError(
    "names_required", _("This phone number has no account yet: enter the last name."), 400
)
ACCOUNT_USED_ELSEWHERE = ApiError(
    "account_used_elsewhere",
    _("This account is also used outside this school: only the platform support can change it."),
    409,
)
PHONE_TAKEN = ApiError("phone_taken", _("This phone number already has an account."), 409)
PLATFORM_ACCOUNT = ApiError(
    "platform_account",
    _("A platform administrator account is changed in the Django administration only."),
    409,
)
PORTAL_ONLY_ACCOUNT = ApiError(
    "portal_only_account",
    _(
        "This account is only used for the parent portal: its school gives the parent a new "
        "family code instead."
    ),
    409,
)
INVALID_CODE = ApiError(
    "invalid_code", _("This code is not valid, or it has already been used."), 400
)
WRONG_PASSWORD = ApiError("wrong_password", _("The current password is not correct."), 400)
SHARED_ACCOUNT = ApiError(
    "shared_demo_account",
    _(
        "This demonstration account is shared between visitors: its password and its two-step "
        "verification do not change."
    ),
    409,
)
TOTP_STILL_REQUIRED = ApiError(
    "totp_still_required",
    _("One of your roles requires two-factor authentication: it cannot be turned off."),
    409,
)

# Sans lettres ni chiffres qu'on confond en les dictant ou en les recopiant (l, 1, o, 0, i).
_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


# Modèle de départ


def create_starter_roles(school: School) -> list[Role]:
    """Copie le modèle de départ (`docs/04` § 8) dans une école neuve : des rôles ordinaires,
    qu'elle renomme, modifie et supprime ensuite. Une seule fois, à sa création."""
    with use_school(school):
        return Role.objects.bulk_create(
            Role(name=starter_role_name(key), permissions=list(role.permissions))
            for key, role in STARTER_ROLES.items()
        )


def first_manager_role() -> Role:
    """Rôle du premier compte de l'école courante : le premier du modèle de départ qui gère les
    comptes et les rôles (`roles.manage`). Choisi par ce droit, pas par son code : sans lui,
    l'école ne pourrait donner de droit à personne."""
    require_current_school()
    return Role.objects.filter(permissions__contains=[ROLES_MANAGE]).earliest("id")


# Droits dans une école


@dataclass(frozen=True)
class SchoolAccess:
    # Vide pendant une session support (`support.py`).
    membership: Membership | None
    roles: tuple[Role, ...]
    permissions: frozenset[str]


def get_school_access(user, school: School | None) -> SchoolAccess | None:
    """Rôles et permissions du compte dans l'école ; None s'il n'y a pas d'appartenance active
    (compte désactivé, retiré de l'école, école suspendue, ou pas d'école). Le super-admin n'a
    aucun droit dans une école sans y avoir de rôle, hors session support (`support.py`)."""
    if school is None or school.is_closed:
        return None
    if not user.is_authenticated or not user.is_active:
        return None
    membership = Membership.objects.filter(user=user, school=school, is_active=True).first()
    if membership is None:
        return None
    with use_school(school):
        roles = tuple(Role.objects.filter(memberships=membership))
    granted = frozenset(code for role in roles for code in role.permissions)
    return SchoolAccess(membership, roles, granted & modules.permissions_of(school.modules))


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


def _check_role_name(name: str, *, role_id=None) -> None:
    if not name:
        raise BusinessError(ROLE_NAME_REQUIRED)
    if Role.objects.filter(name__iexact=name).exclude(pk=role_id).exists():
        raise BusinessError(ROLE_NAME_TAKEN)


def _role_data(role: Role) -> dict:
    return {"name": role.name, "permissions": list(role.permissions)}


def _role_summary(role: Role) -> dict:
    return {"id": str(role.pk), "name": role.name}


def _role_summaries(roles: Iterable[Role]) -> list[dict]:
    return [_role_summary(role) for role in sorted(roles, key=lambda role: role.pk)]


def create_role(*, actor: User, name: str, permissions: Iterable[str]) -> Role:
    """Nouveau rôle de l'école courante (B2), ex. « Chef d'atelier »."""
    require_current_school()
    name = name.strip()
    with transaction.atomic():
        _check_role_name(name)
        role = Role.objects.create(
            name=name, permissions=sorted_permissions(permissions), created_by=actor
        )
        audit.record(
            Action.ROLES_CREATED, role, actor=actor, after=_role_data(role), label=role.name
        )
        return role


def update_role(
    role: Role, *, actor: User, name: str | None = None, permissions: Iterable[str] | None = None
) -> Role:
    """Renommer un rôle ou changer ses permissions."""
    with transaction.atomic(), _keeping_a_role_manager(role.school):
        before = _role_data(role)
        fields = ["updated_at"]
        if name is not None:
            role.name = name.strip()
            _check_role_name(role.name, role_id=role.pk)
            fields.append("name")
        if permissions is not None:
            role.permissions = sorted_permissions(permissions)
            fields.append("permissions")
        role.save(update_fields=fields)
        old, new = audit.changes(before, _role_data(role))
        if new:
            audit.record(
                Action.ROLES_UPDATED, role, actor=actor, before=old, after=new, label=role.name
            )
    return role


def delete_role(role: Role, *, actor: User) -> None:
    """Supprimer un rôle, s'il n'est plus donné à personne : l'école garde donc toujours celui
    de son dernier gestionnaire des rôles."""
    with transaction.atomic():
        if role.memberships.exists():
            raise BusinessError(ROLE_IN_USE)
        audit.record(
            Action.ROLES_DELETED, role, actor=actor, before=_role_data(role), label=role.name
        )
        role.delete()


# Comptes du personnel


def make_temporary_password() -> str:
    """Mot de passe provisoire facile à dicter : 3 groupes de 4 caractères (≈ 59 bits)."""
    groups = ("".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(4)) for _ in range(3))
    return "-".join(groups)


def ensure_number_fits_space(phone: str, school: School) -> None:
    """Pas de mélange entre fictif et réel (`03` § 4 bis) : un numéro de la plage réservée n'a de
    rôle ou de famille que dans un espace de démonstration, et un tel espace n'accepte que ces
    numéros. Le compte d'une vraie personne n'est donc jamais relié à des données fictives."""
    if school.is_demo and not is_demo_phone(phone):
        raise BusinessError(DEMO_SPACE_NUMBERS)
    if is_demo_phone(phone) and not school.is_demo:
        raise BusinessError(DEMO_NUMBER)


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
    ensure_number_fits_space(phone, school)
    roles = list(roles)
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
        _audit_staff(
            Action.STAFF_ADDED,
            membership,
            actor=actor,
            after={"roles": _role_summaries(roles), "new_account": temporary_password is not None},
        )
    return membership, temporary_password


def _audit_staff(action: str, membership: Membership, *, actor: User | None, **data) -> None:
    """Action de l'école sur une personne : dans le journal de l'école courante."""
    audit.record(action, membership, actor=actor, label=str(membership.user), **data)


def _audit_account(user: User, action: str, *, actor: User | None, **data) -> None:
    """Changement d'un compte (mot de passe, double authentification, noms…) : dans le journal
    de chaque école où la personne est active, sur son appartenance à cette école. Le compte est
    unique et donne accès à chacune ; aucune entrée ne dit où l'action a été faite."""
    memberships = Membership.objects.filter(user=user, is_active=True).select_related("school")
    for membership in memberships:
        with use_school(membership.school):
            _audit_staff(action, membership, actor=actor, **data)


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
            user = _account_of(membership)
            before = {field: getattr(user, field) for field in account}
            _update_account(user, **account)
            old, new = audit.changes(before, {field: getattr(user, field) for field in account})
            if new:
                _audit_staff(
                    Action.STAFF_ACCOUNT_CHANGED, membership, actor=actor, before=old, after=new
                )
        if roles is not None:
            roles = list(roles)
            before = _role_summaries(membership.roles.all())
            membership.roles.set(roles)
            if _role_summaries(roles) != before:
                _audit_staff(
                    Action.STAFF_ROLES_CHANGED,
                    membership,
                    actor=actor,
                    before={"roles": before},
                    after={"roles": _role_summaries(roles)},
                )
        if is_active is not None and is_active != membership.is_active:
            membership.is_active = is_active
            membership.save(update_fields=["is_active", "updated_at"])
            action = Action.STAFF_REACTIVATED if is_active else Action.STAFF_DEACTIVATED
            _audit_staff(action, membership, actor=actor)
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
        if is_demo_phone(fields["phone"]) != is_demo_phone(user.phone):
            # Un compte ne sort pas de la plage réservée et n'y entre pas (`03` § 4 bis).
            raise BusinessError(DEMO_SPACE_NUMBERS if is_demo_phone(user.phone) else DEMO_NUMBER)
    for field, value in fields.items():
        setattr(user, field, value.strip())
    user.save(update_fields=[*fields, "updated_at"])


def ensure_not_shared(user: User) -> None:
    """Compte d'un espace de démonstration créé depuis la console (4.17.2) : partagé entre les
    visiteurs par la fiche d'accès, qui doit rester juste. Ni son mot de passe ni sa double
    authentification ne changent ; « Remettre à zéro » en donne un nouveau. Une requête, pour
    les seuls numéros réservés."""
    block = demo_block(user.phone)
    if block is not None and Demonstration.objects.filter(block=block).exists():
        raise BusinessError(SHARED_ACCOUNT)


def set_temporary_password(membership: Membership, *, actor: User) -> str:
    """« Nouveau mot de passe » (M3) : mot de passe provisoire renvoyé une seule fois, à changer
    à la prochaine connexion. Les sessions ouvertes de la personne sont fermées (Django lie la
    session au mot de passe)."""
    user = _account_of(membership)
    ensure_not_shared(user)
    password = make_temporary_password()
    with transaction.atomic():
        user.set_password(password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        _audit_staff(Action.STAFF_PASSWORD_RESET, membership, actor=actor)
    return password


def reset_staff_totp(membership: Membership, *, actor: User) -> None:
    """« Réinitialiser la double auth. » (M3), ex. téléphone perdu : la personne la réactive à sa
    prochaine connexion si l'un de ses rôles l'exige."""
    user = _account_of(membership)
    with transaction.atomic():
        reset_totp(user)
        _audit_staff(Action.STAFF_TOTP_RESET, membership, actor=actor)


# Mot de passe


def change_password(user: User, new_password: str, *, current_password: str | None = None) -> None:
    """Nouveau mot de passe choisi par la personne (déjà validé par le serializer), après le mot
    de passe actuel s'il est donné (compte connecté). Les autres sessions du compte sont
    fermées ; la vue garde la session en cours."""
    if current_password is not None and not user.check_password(current_password):
        raise BusinessError(WRONG_PASSWORD)
    ensure_not_shared(user)
    with transaction.atomic():
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        _audit_account(user, Action.ACCOUNT_PASSWORD_CHANGED, actor=user)


# Double authentification (B4)


def totp_required(user: User) -> bool:
    """Exigée pour un super-admin, et si, dans une école où il est actif, le compte a un rôle
    portant un droit sensible (`roles.TOTP_PERMISSIONS`). Le compte étant unique, elle le protège
    alors partout. Un espace de démonstration ne compte pas : ses comptes sont partagés entre
    visiteurs et ses données fictives (`03` § 4 bis)."""
    if user.is_platform_admin:
        return True
    return (
        Membership.objects.filter(
            user=user, is_active=True, roles__permissions__overlap=sorted(TOTP_PERMISSIONS)
        )
        .exclude(school__environment=School.Environment.DEMO)
        .exists()
    )


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


def verify_second_factor(user: User, code: str) -> str:
    """Code TOTP du moment ou code de secours pas encore utilisé ; chacun ne sert qu'une fois
    (`INVALID_CODE` sinon). Renvoie `"totp"` ou `"recovery_code"` (journal de la connexion).
    Les essais ratés sont comptés par l'appelant (`attempts.py`)."""
    with transaction.atomic():
        # Deux requêtes avec le même code en même temps : une seule passe.
        locked = User.objects.select_for_update().get(pk=user.pk)
        key = _totp_key(locked) if locked.totp_enabled else None
        step = totp.matching_step(key, code, after=locked.totp_last_step) if key else None
        if step is not None:
            locked.totp_last_step = user.totp_last_step = step
            locked.save(update_fields=["totp_last_step", "updated_at"])
            return "totp"
        digests = _recovery_digests(code)
        if digests and locked.totp_enabled:
            used = RecoveryCode.objects.filter(
                user=locked, digest__in=digests, used_at__isnull=True
            ).update(used_at=timezone.now())
            if used:
                return "recovery_code"
    raise BusinessError(INVALID_CODE)


def enable_totp(user: User, secret: str, code: str) -> list[str]:
    """Activer la double authentification avec la clé montrée à la personne (M1), une fois le
    premier code vérifié ; aussi pour « changer de téléphone ». Renvoie les 8 codes de secours,
    affichés une seule fois."""
    step = totp.matching_step(secret, code)
    if step is None:
        raise BusinessError(INVALID_CODE)
    ensure_not_shared(user)
    action = Action.ACCOUNT_TOTP_CHANGED if user.totp_enabled else Action.ACCOUNT_TOTP_ENABLED
    with transaction.atomic():
        user.totp_secret = encrypt(secret)
        user.totp_enabled_at = timezone.now()
        user.totp_last_step = step
        user.save(update_fields=["totp_secret", "totp_enabled_at", "totp_last_step", "updated_at"])
        _audit_account(user, action, actor=user)
        return _new_recovery_codes(user)


def regenerate_recovery_codes(user: User, code: str) -> list[str]:
    """8 nouveaux codes de secours ; les anciens ne servent plus."""
    verify_second_factor(user, code)
    with transaction.atomic():
        _audit_account(user, Action.ACCOUNT_RECOVERY_CODES_RENEWED, actor=user)
        return _new_recovery_codes(user)


def disable_totp(user: User, code: str) -> None:
    """Refusé si l'un des rôles du compte l'exige (M4)."""
    if totp_required(user):
        raise BusinessError(TOTP_STILL_REQUIRED)
    verify_second_factor(user, code)
    with transaction.atomic():
        reset_totp(user)
        _audit_account(user, Action.ACCOUNT_TOTP_DISABLED, actor=user)


def support_reset_totp(user: User, *, actor: User) -> None:
    """Par le support (console ou administration Django), ex. téléphone perdu : noté dans le
    journal de la plateforme et dans celui de chaque école où la personne est active. Rien à
    réinitialiser : rien n'est noté."""
    if not (user.totp_enabled or user.totp_secret):
        return
    with transaction.atomic():
        reset_totp(user)
        _audit_support(user, Action.ACCOUNT_TOTP_RESET, PlatformAction.ACCOUNT_TOTP_RESET, actor)


# Support de la plateforme (console, 5.4.1 ; administration Django pour le dépannage)

_SUPPORT_ACCOUNT_FIELDS = ("phone", "last_name", "middle_name", "first_name")


def _audit_support(
    user: User, action: str, platform_action: str, actor: User, **data: dict | None
) -> None:
    """Action du support sur un compte : journal de la plateforme, et journal de chaque école où
    la personne est active (elle y voit le support, pas le reste de la console)."""
    _audit_account(user, action, actor=actor, **data)
    audit.record_platform(platform_action, user, actor=actor, label=str(user), **data)


def audit_support_changes(old: User, user: User, *, actor: User) -> None:
    """Après un changement du compte par le support (`old` : le compte avant) : noms et
    téléphone, désactivation ou réactivation du compte."""
    before, after = audit.changes(
        {field: getattr(old, field) for field in _SUPPORT_ACCOUNT_FIELDS},
        {field: getattr(user, field) for field in _SUPPORT_ACCOUNT_FIELDS},
    )
    if after:
        _audit_support(
            user,
            Action.ACCOUNT_CHANGED,
            PlatformAction.ACCOUNT_CHANGED,
            actor,
            before=before,
            after=after,
        )
    if old.is_active != user.is_active:
        if user.is_active:
            actions = (Action.ACCOUNT_REACTIVATED, PlatformAction.ACCOUNT_REACTIVATED)
        else:
            actions = (Action.ACCOUNT_DEACTIVATED, PlatformAction.ACCOUNT_DEACTIVATED)
        _audit_support(user, *actions, actor)


def ensure_console_can_change(user: User) -> None:
    """La console ne change pas un compte de la plateforme : un super-admin se dépanne dans
    l'administration Django (double authentification exigée)."""
    if user.is_platform_admin:
        raise BusinessError(PLATFORM_ACCOUNT)


def support_update_account(user: User, *, actor: User, **fields) -> User:
    """Noms, téléphone (l'identifiant de connexion) et accès d'un compte, par le support
    (console). Désactivé : plus de connexion nulle part, ni à une école ni au portail ; ses
    sessions ouvertes ne valent plus."""
    ensure_console_can_change(user)
    old = User.objects.get(pk=user.pk)
    with transaction.atomic():
        is_active = fields.pop("is_active", user.is_active)
        if fields:
            _update_account(user, **fields)
        if is_active != user.is_active:
            user.is_active = is_active
            user.save(update_fields=["is_active", "updated_at"])
        audit_support_changes(old, user, actor=actor)
    return user


def support_set_temporary_password(user: User, *, actor: User) -> str:
    """Mot de passe provisoire donné par le support (comme « Nouveau mot de passe » de M3),
    renvoyé une seule fois, à changer à la prochaine connexion ; les sessions ouvertes de la
    personne sont fermées. Le support ne choisit jamais le mot de passe de quelqu'un.

    Pas pour un compte qui ne sert qu'au portail des parents : le portail refuse un mot de
    passe provisoire ; le parent demande un nouveau code famille à son école (4.4)."""
    if not (
        user.is_platform_admin or Membership.objects.filter(user=user, is_active=True).exists()
    ):
        raise BusinessError(PORTAL_ONLY_ACCOUNT)
    password = make_temporary_password()
    with transaction.atomic():
        user.set_password(password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        _audit_support(
            user, Action.ACCOUNT_PASSWORD_RESET, PlatformAction.ACCOUNT_PASSWORD_RESET, actor
        )
    return password


def reset_totp(user: User) -> None:
    """Sans code et sans entrée dans le journal : l'appelant écrit la sienne (école, support ;
    `make demo`, qui n'est l'action de personne)."""
    with transaction.atomic():
        user.totp_secret = ""
        user.totp_enabled_at = None
        user.totp_last_step = 0
        user.save(update_fields=["totp_secret", "totp_enabled_at", "totp_last_step", "updated_at"])
        RecoveryCode.objects.filter(user=user).delete()

"""Comptes, rôles et appartenances : règles métier (`docs/04-modele-de-donnees.md` § 1 et § 8).

Les services qui changent les rôles et les comptes d'une école travaillent dans l'école courante
(requête sur son sous-domaine, ou `use_school`). L'audit de ces changements arrive avec
`AuditLog` (tâche 1.4).
"""

import secrets
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Membership, Role, User
from apps.accounts.phone import normalize_phone
from apps.accounts.roles import ROLES_MANAGE, SYSTEM_ROLES, sorted_permissions
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import CrossSchoolError, require_current_school, use_school
from apps.schools.models import School

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


def update_staff_member(
    membership: Membership,
    *,
    actor: User,
    roles: Iterable[Role] | None = None,
    is_active: bool | None = None,
) -> Membership:
    """Changer les rôles d'une personne dans l'école, la désactiver (plus aucun accès à cette
    école, son compte reste valable ailleurs) ou la réactiver. On ne supprime pas un compte."""
    school = require_current_school()
    if membership.school_id != school.pk:
        raise CrossSchoolError("Appartenance d'une autre école que l'école courante.")
    with transaction.atomic(), _keeping_a_role_manager(school):
        if roles is not None:
            membership.roles.set(roles)
        if is_active is not None and is_active != membership.is_active:
            membership.is_active = is_active
            membership.save(update_fields=["is_active", "updated_at"])
    return membership

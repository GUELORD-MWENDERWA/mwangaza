"""Équipe de la plateforme (EQ.1) : inviter, changer les rôles, retirer.

Un membre est un compte de la plateforme (`User.is_platform_admin`) avec un ou plusieurs rôles
fixes (`platform_roles.py`) : double authentification toujours exigée (`services.totp_required`),
adresses autorisées et session courte (`privileged.py`), aucun droit dans une école. Chaque
changement va au journal de la plateforme sous le nom de son auteur. La plateforme garde toujours
un propriétaire : le dernier ne peut ni partir ni perdre ce rôle.

Un membre retiré n'est jamais supprimé (le journal le cite) : son compte est désactivé et son mot
de passe rendu inutilisable, ce qui ferme tout de suite ses sessions ouvertes (Django lie la
session au mot de passe). Réinvité plus tard, il repart avec un mot de passe provisoire et une
nouvelle double authentification."""

from collections.abc import Iterable

from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from apps.accounts import services
from apps.accounts.models import User
from apps.accounts.phone import is_demo_phone, normalize_phone
from apps.accounts.platform_roles import OWNER
from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.core.errors import ApiError, BusinessError

PHONE_IN_USE = ApiError(
    "phone_in_use",
    _(
        "This phone number belongs to a school or parent account: a team member needs a number "
        "of their own."
    ),
    409,
)
ALREADY_IN_TEAM = ApiError("already_in_team", _("This person is already in the team."), 409)
LAST_OWNER = ApiError(
    "last_owner", _("The platform must keep at least one lead administrator."), 409
)


def members() -> QuerySet[User]:
    """Membres actuels de l'équipe, par nom."""
    return User.objects.filter(is_platform_admin=True, is_active=True)


def _roles(roles: Iterable[str]) -> list[str]:
    return sorted(set(roles))


def _keeping_an_owner(member: User) -> None:
    """Refus si `member` est le dernier propriétaire. Tous les propriétaires sont verrouillés
    (même ordre pour tous) : deux propriétaires qui se retirent l'un l'autre en même temps n'en
    laissent pas zéro."""
    owners = list(
        members()
        .filter(platform_roles__contains=[OWNER])
        .select_for_update()
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if owners == [member.pk]:
        raise BusinessError(LAST_OWNER)


def invite(
    *,
    actor: User,
    phone: str,
    roles: Iterable[str],
    last_name: str,
    middle_name: str = "",
    first_name: str = "",
) -> tuple[User, str]:
    """Nouveau membre avec ses rôles et un mot de passe provisoire, renvoyé une seule fois (à
    changer à la première connexion, puis double authentification à activer). Un ancien membre
    retenu par son numéro repart de la même façon ; le numéro d'un compte d'école ou de parent est
    refusé : un compte de la plateforme n'a aucun droit dans une école."""
    phone = normalize_phone(phone)
    if is_demo_phone(phone):
        raise BusinessError(services.DEMO_NUMBER)
    roles = _roles(roles)
    names = {
        "last_name": last_name.strip(),
        "middle_name": middle_name.strip(),
        "first_name": first_name.strip(),
    }
    password = services.make_temporary_password()
    with transaction.atomic():
        user = User.objects.select_for_update().filter(phone=phone).first()
        if user is None:
            user = User.objects.create_user(
                phone,
                password,
                **names,
                is_platform_admin=True,
                platform_roles=roles,
                must_change_password=True,
                created_by=actor,
            )
        elif not user.is_platform_admin:
            raise BusinessError(PHONE_IN_USE)
        elif user.is_active:
            raise BusinessError(ALREADY_IN_TEAM)
        else:
            services.reset_totp(user)
            for field, value in names.items():
                setattr(user, field, value)
            user.set_password(password)
            user.is_active, user.platform_roles, user.must_change_password = True, roles, True
            user.save()
        audit.record_platform(
            PlatformAction.TEAM_MEMBER_INVITED, user, actor=actor, after={"roles": roles}
        )
    return user, password


def set_roles(member: User, *, actor: User, roles: Iterable[str]) -> User:
    """Nouveaux rôles, effectifs dès la requête suivante du membre (relus avec son compte)."""
    roles = _roles(roles)
    with transaction.atomic():
        before = sorted(member.platform_roles)
        if before == roles:
            return member
        if OWNER in before and OWNER not in roles:
            _keeping_an_owner(member)
        member.platform_roles = roles
        member.save(update_fields=["platform_roles", "updated_at"])
        audit.record_platform(
            PlatformAction.TEAM_ROLES_CHANGED,
            member,
            actor=actor,
            before={"roles": before},
            after={"roles": roles},
        )
    return member


def remove(member: User, *, actor: User) -> None:
    """Retrait de l'équipe : plus aucun droit, sessions fermées tout de suite."""
    with transaction.atomic():
        before = sorted(member.platform_roles)
        if OWNER in before:
            _keeping_an_owner(member)
        member.platform_roles = []
        member.is_active = False
        member.set_unusable_password()
        member.save(update_fields=["platform_roles", "is_active", "password", "updated_at"])
        audit.record_platform(
            PlatformAction.TEAM_MEMBER_REMOVED, member, actor=actor, before={"roles": before}
        )

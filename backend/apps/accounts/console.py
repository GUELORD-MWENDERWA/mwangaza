"""Comptes dans la console de la plateforme (5.4.1) : toutes les écoles à la fois, pour le
super-admin seulement (`IsPlatformAdmin`). Un compte est unique sur la plateforme : il sert au
personnel de plusieurs écoles (`Membership`) et aux parents de familles de plusieurs écoles
(`Family.primary_user`), lues ici hors de toute école (`all_schools`), toujours pour les
comptes demandés."""

import re
from collections import defaultdict
from collections.abc import Iterable
from uuid import UUID

from django.db.models import Prefetch, Q, QuerySet

from apps.accounts.models import Membership, Role, User
from apps.students.models import Family

# En dessous, des chiffres tapés ne désignent pas encore un numéro.
PHONE_DIGITS = 3


def _matching(search: str) -> Q:
    """Chaque mot dans le nom, le post-nom ou le prénom ; ou les chiffres du numéro, tapé à la
    façon locale (0971…) ou internationale (+243 971…)."""
    names = Q()
    for word in search.split():
        names &= (
            Q(last_name__icontains=word)
            | Q(middle_name__icontains=word)
            | Q(first_name__icontains=word)
        )
    digits = re.sub(r"\D", "", search)
    if len(digits) < PHONE_DIGITS:
        return names
    return names | Q(phone__contains=digits.lstrip("0") or digits)


def accounts(search: str = "") -> QuerySet[User]:
    """Comptes avec leurs écoles et leurs rôles (deux requêtes de plus pour une page, pas une
    par compte)."""
    memberships = Membership.objects.select_related("school").prefetch_related(
        Prefetch("roles", queryset=Role.all_schools.order_by("id"))
    )
    users = User.objects.prefetch_related(
        Prefetch("memberships", queryset=memberships.order_by("school__name"))
    )
    if search := search.strip():
        users = users.filter(_matching(search))
    return users


def families_of(users: Iterable[User]) -> dict[UUID, list[Family]]:
    """Familles du portail reliées à ces comptes, dans toutes les écoles, en une requête."""
    families = defaultdict(list)
    rows = (
        Family.all_schools.filter(primary_user__in=[user.pk for user in users])
        .select_related("school")
        .order_by("school__name", "code")
    )
    for family in rows:
        families[family.primary_user_id].append(family)
    return families

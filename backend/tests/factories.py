"""Fabriques factory_boy partagées par les tests de toutes les apps."""

import factory
from django.utils import timezone

from apps.accounts import totp
from apps.accounts.models import Membership, Role, User
from apps.accounts.modules import ALL_MODULES
from apps.accounts.roles import starter_role_name
from apps.core.crypto import encrypt
from apps.core.tenancy import use_school
from apps.schools.models import School

TEST_PASSWORD = "mot-de-passe-de-test"


class SchoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = School
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"ecole{n}")
    name = factory.Sequence(lambda n: f"École fictive n° {n}")
    status = School.Status.ACTIVE
    modules = ALL_MODULES


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    # +243 1… : jamais le numéro d'une vraie personne, et hors de la plage réservée aux espaces
    # de démonstration (+243 0…, `accounts/phone.py`).
    phone = factory.Sequence(lambda n: f"+24310009{n:04d}")
    last_name = factory.Sequence(lambda n: f"Nom{n}")
    first_name = "Prénom"
    password = factory.django.Password(TEST_PASSWORD)


def starter_role(school, key: str) -> Role:
    """Le rôle du modèle de départ `key` (`"head"`, `"cashier"`…) dans `school`, retrouvé par le
    nom qu'il reçoit à la création de l'école : un rôle n'a pas de code."""
    with use_school(school):
        return Role.objects.get(name=starter_role_name(key))


class MembershipFactory(factory.django.DjangoModelFactory):
    """`roles` : clés du modèle de départ (`"head"`) ou objets `Role` de la même école."""

    class Meta:
        model = Membership
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    school = factory.SubFactory(SchoolFactory)

    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        with use_school(self.school):
            self.roles.set(
                starter_role(self.school, role) if isinstance(role, str) else role
                for role in extracted
            )


def enable_totp(user: User, secret: str | None = None) -> str:
    """Double authentification activée pour `user`, sans utiliser de code ; renvoie la clé."""
    secret = secret or totp.new_secret()
    user.totp_secret = encrypt(secret)
    user.totp_enabled_at = timezone.now()
    user.totp_last_step = 0
    user.save()
    return secret


def totp_code(secret: str, *, shift: int = 0) -> str:
    """Code du moment (`shift=1` : de la période suivante, encore accepté)."""
    return totp.code_at(secret, totp.current_step() + shift)

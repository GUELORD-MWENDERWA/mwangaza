"""Fabriques factory_boy partagées par les tests de toutes les apps."""

import factory

from apps.accounts.models import Membership, Role, User
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


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    # +243 0… : jamais le numéro d'une vraie personne.
    phone = factory.Sequence(lambda n: f"+24300009{n:04d}")
    last_name = factory.Sequence(lambda n: f"Nom{n}")
    first_name = "Prénom"
    password = factory.django.Password(TEST_PASSWORD)


class MembershipFactory(factory.django.DjangoModelFactory):
    """`roles` : codes de rôles système (`"head"`) ou objets `Role` de la même école."""

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
                Role.objects.get(code=role) if isinstance(role, str) else role for role in extracted
            )

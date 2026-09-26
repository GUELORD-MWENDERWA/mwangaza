"""Fabriques factory_boy partagées par les tests de toutes les apps."""

import factory

from apps.schools.models import School


class SchoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = School
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"ecole{n}")
    name = factory.Sequence(lambda n: f"École fictive n° {n}")
    status = School.Status.ACTIVE

"""make demo : données fictives pour le développement et les démonstrations."""

import pytest
from django.core.management import CommandError, call_command

from apps.schools.models import School

pytestmark = pytest.mark.django_db


def test_demo_creates_the_two_demo_schools(settings):
    settings.DEBUG = True

    call_command("demo")

    schools = {school.code: school for school in School.objects.all()}
    assert set(schools) == {"itig", "volcans"}
    assert schools["itig"].name == "ITIG Don Bosco Goma (démo)"
    assert all(school.status == School.Status.ACTIVE for school in schools.values())


def test_demo_can_run_twice_without_duplicates(settings):
    settings.DEBUG = True

    call_command("demo")
    call_command("demo")

    assert School.objects.count() == 2


def test_demo_is_refused_outside_development(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        call_command("demo")

    assert not School.objects.exists()

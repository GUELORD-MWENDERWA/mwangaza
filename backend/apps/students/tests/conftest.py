"""Organisation de deux écoles fictives (année 2026-2027, classe « 3e Électricité A ») et un
élève à inscrire."""

import pytest

from apps.core.tenancy import use_school
from apps.schools.tests.test_organisation_api import structure
from apps.students import services

GUARDIAN = {"full_name": "Kahindo Neema", "relationship": "mother", "phone": "+243971234567"}


@pytest.fixture
def alpha(school, head):
    return structure(school, head)


@pytest.fixture
def beta(other_school, other_head):
    return structure(other_school, other_head)


def new_student(school, actor, **fields):
    """Élève avec une nouvelle famille (une mère) dans `school`."""
    fields = {"last_name": "Kasereka", "first_name": "Jean", "sex": "M", **fields}
    with use_school(school):
        student, _created = services.create_student(actor=actor, guardians=[GUARDIAN], **fields)
    return student


def enrolled(school, actor, group, **fields):
    student = new_student(school, actor, **fields)
    with use_school(school):
        services.enroll(student, actor=actor, class_group=group)
        student.refresh_from_db()
    return student

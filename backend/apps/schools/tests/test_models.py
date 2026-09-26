"""École : le code est le sous-domaine ({code}.mwangaza.school)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.schools.models import School
from tests.factories import SchoolFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("code", ["itig", "volcans", "cs-les-volcans", "lycee2", "ab"])
def test_valid_codes(code):
    School(code=code, name="École").full_clean()


@pytest.mark.parametrize(
    "code",
    ["a", "ITIG", "-itig", "itig-", "les volcans", "école", "itig.goma", "x" * 31, ""],
)
def test_invalid_codes_are_refused(code):
    with pytest.raises(ValidationError) as error:
        School(code=code, name="École").full_clean()

    assert "code" in error.value.message_dict


@pytest.mark.parametrize("code", ["www", "parents", "admin", "api"])
def test_reserved_codes_are_refused(code):
    with pytest.raises(ValidationError) as error:
        School(code=code, name="École").full_clean()

    assert "code" in error.value.message_dict


def test_database_refuses_an_invalid_code_even_without_validation():
    with pytest.raises(IntegrityError), transaction.atomic():
        School.objects.create(code="ITIG", name="École")


def test_code_is_unique():
    SchoolFactory(code="itig")

    with pytest.raises(IntegrityError), transaction.atomic():
        School.objects.create(code="itig", name="Doublon")


def test_new_school_is_on_trial_with_uuid7_id():
    school = School.objects.create(code="nouvelle", name="Nouvelle école")

    assert school.status == School.Status.TRIAL
    assert school.pk.version == 7
    assert str(school) == "Nouvelle école"

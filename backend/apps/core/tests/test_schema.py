"""Schéma OpenAPI (`make api`) : types exacts pour le client du front (`packages/api`)."""

import pytest
from drf_spectacular.generators import SchemaGenerator

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module")
def schemas():
    return SchemaGenerator().get_schema(request=None, public=True)["components"]["schemas"]


def test_a_response_always_has_every_field(schemas):
    # Champ avec une valeur par défaut dans le modèle : toujours renvoyé, donc obligatoire.
    assert set(schemas["CurrentSchool"]["required"]) == set(schemas["CurrentSchool"]["properties"])
    assert "status" in schemas["MySchool"]["required"]
    assert "name" in schemas["RoleSummary"]["required"]
    assert set(schemas["Me"]["required"]) == set(schemas["Me"]["properties"])


def test_what_is_sent_keeps_its_optional_fields(schemas):
    assert "name" not in schemas["RoleRequest"].get("required", [])
    assert "required" not in schemas["PatchedMeUpdateRequest"]


def test_field_errors_come_only_with_invalid_input(schemas):
    assert schemas["Error"]["required"] == ["code", "detail"]

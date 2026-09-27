"""Erreurs de l'API au format `{code, detail}` ; erreurs de saisie avec un code par champ."""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.core.errors import ApiError, BusinessError, api_exception_handler

pytestmark = pytest.mark.django_db


def test_business_error_keeps_its_code_and_status():
    error = ApiError("role_in_use", "Still given.", 409)

    response = api_exception_handler(BusinessError(error), {})

    assert response.status_code == 409
    assert response.data == {"code": "role_in_use", "detail": "Still given."}


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (PermissionDenied(), 403, "permission_denied"),
        (NotFound(), 404, "not_found"),
        (NotFound("Nothing here.", code="school_not_found"), 404, "school_not_found"),
    ],
)
def test_drf_errors_get_a_code(exc, status, code):
    response = api_exception_handler(exc, {})

    assert response.status_code == status
    assert response.data["code"] == code
    assert set(response.data) == {"code", "detail"}


def test_field_errors_have_a_code_for_each_message():
    error = serializers.ValidationError(
        {"phone": [serializers.ErrorDetail("Invalid.", code="invalid_phone")]}
    )

    response = api_exception_handler(error, {})

    assert response.status_code == 400
    assert response.data == {
        "code": "invalid",
        "detail": "Some fields are invalid.",
        "fields": {"phone": [{"code": "invalid_phone", "detail": "Invalid."}]},
    }


def test_a_field_named_code_does_not_hide_the_error_code():
    response = api_exception_handler(serializers.ValidationError({"code": ["Required."]}), {})

    assert response.data["code"] == "invalid"
    assert response.data["fields"] == {"code": [{"code": "invalid", "detail": "Required."}]}


def test_nested_and_list_errors_are_flattened():
    error = serializers.ValidationError(
        {"contact": {"phone": ["Invalid."]}, "roles": [{}, {"name": ["Required."]}]}
    )

    fields = api_exception_handler(error, {}).data["fields"]

    assert fields == {
        "contact.phone": [{"code": "invalid", "detail": "Invalid."}],
        "roles.1.name": [{"code": "invalid", "detail": "Required."}],
    }


def test_an_error_without_a_field_goes_to_non_field_errors():
    response = api_exception_handler(serializers.ValidationError("Not both."), {})

    assert response.data["fields"] == {
        "non_field_errors": [{"code": "invalid", "detail": "Not both."}]
    }


def test_django_validation_error_of_a_service_gets_the_same_format():
    error = DjangoValidationError(
        {"terms.0.ends_on": DjangoValidationError("Outside the year.", code="outside_year")}
    )

    response = api_exception_handler(error, {})

    assert response.status_code == 400
    assert response.data == {
        "code": "invalid",
        "detail": "Some fields are invalid.",
        "fields": {"terms.0.ends_on": [{"code": "outside_year", "detail": "Outside the year."}]},
    }


def test_other_exceptions_are_not_hidden():
    assert api_exception_handler(RuntimeError("bug"), {}) is None


def test_method_not_allowed_through_the_api(client, school):
    response = client.post("/api/school/", {}, HTTP_HOST="alpha.localhost")

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"

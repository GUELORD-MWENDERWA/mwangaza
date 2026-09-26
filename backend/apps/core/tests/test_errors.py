"""Erreurs de l'API au format `{code, detail}` ; erreurs de saisie au format de DRF."""

import pytest
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


def test_field_errors_keep_the_drf_format():
    response = api_exception_handler(serializers.ValidationError({"phone": ["Invalid."]}), {})

    assert response.status_code == 400
    assert response.data == {"phone": ["Invalid."]}


def test_other_exceptions_are_not_hidden():
    assert api_exception_handler(RuntimeError("bug"), {}) is None


def test_method_not_allowed_through_the_api(client, school):
    response = client.post("/api/school/", {}, HTTP_HOST="alpha.localhost")

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"

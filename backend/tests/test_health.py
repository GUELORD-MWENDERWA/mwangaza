from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.db.utils import OperationalError


@pytest.mark.django_db
def test_health_is_public_and_checks_database(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_health_reports_database_failure(client):
    with mock.patch("config.views.connection.cursor", side_effect=OperationalError("base arrêtée")):
        response = client.get("/api/health/")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error"}


def test_openapi_schema_is_valid():
    output = StringIO()

    call_command("spectacular", "--validate", "--fail-on-warn", stdout=output)

    assert "openapi: 3" in output.getvalue()

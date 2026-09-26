"""L'école de chaque requête vient du sous-domaine : {code}.mwangaza.school."""

import json

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.utils import timezone

from apps.core.middleware import TenantMiddleware, school_code_from_host
from apps.core.tenancy import get_current_school, use_school
from apps.schools.models import School
from tests.sample.models import Note


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("itig.localhost", "itig"),
        ("itig.localhost:5173", "itig"),
        ("ITIG.localhost", "itig"),
        ("volcans.localhost:8000", "volcans"),
        ("localhost", None),
        ("localhost:5174", None),
        ("testserver", None),
        ("127.0.0.1:8000", None),
        ("parents.localhost", None),
        ("admin.localhost", None),
        ("www.localhost", None),
        ("a.b.localhost", "a.b"),
    ],
)
def test_school_code_from_host(host, expected):
    assert school_code_from_host(host) == expected


@override_settings(SCHOOL_BASE_DOMAINS=["mwangaza.school"])
@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("itig.mwangaza.school", "itig"),
        ("mwangaza.school", None),
        ("parents.mwangaza.school", None),
        ("itig.localhost", None),
        ("itig.mwangaza.school.evil.example", None),
    ],
)
def test_school_code_from_host_in_production(host, expected):
    assert school_code_from_host(host) == expected


@pytest.fixture
def seen():
    return {}


@pytest.fixture
def middleware(seen):
    def view(request):
        seen["school"] = get_current_school()
        seen["request_school"] = request.school
        seen["timezone"] = timezone.get_current_timezone_name()
        seen["notes"] = (
            list(Note.objects.values_list("text", flat=True)) if seen["school"] else None
        )
        return HttpResponse("ok")

    return TenantMiddleware(view)


@pytest.fixture
def notes(school, other_school):
    with use_school(school):
        Note.objects.create(text="note alpha")
    with use_school(other_school):
        Note.objects.create(text="note beta")


@pytest.mark.django_db
def test_request_on_school_subdomain_sees_only_that_school(middleware, seen, school, notes):
    response = middleware(RequestFactory().get("/api/health/", HTTP_HOST="alpha.localhost:5173"))

    assert response.status_code == 200
    assert seen["school"] == school
    assert seen["request_school"] == school
    assert seen["notes"] == ["note alpha"]
    assert get_current_school() is None


@pytest.mark.django_db
def test_other_school_never_sees_first_school_data(middleware, seen, other_school, notes):
    middleware(RequestFactory().get("/api/health/", HTTP_HOST="beta.localhost"))

    assert seen["school"] == other_school
    assert seen["notes"] == ["note beta"]


@pytest.mark.django_db
@pytest.mark.parametrize("host", ["localhost:8000", "testserver", "parents.localhost"])
def test_platform_hosts_have_no_school(middleware, seen, host):
    response = middleware(RequestFactory().get("/api/health/", HTTP_HOST=host))

    assert response.status_code == 200
    assert seen["school"] is None
    assert seen["request_school"] is None


@pytest.mark.django_db
def test_unknown_school_is_refused(middleware, seen):
    response = middleware(RequestFactory().get("/api/health/", HTTP_HOST="inconnue.localhost"))

    assert response.status_code == 404
    assert json.loads(response.content)["code"] == "school_not_found"
    assert "school" not in seen


@pytest.mark.django_db
def test_suspended_school_is_refused(middleware, seen, school):
    school.status = School.Status.SUSPENDED
    school.save()

    response = middleware(RequestFactory().get("/api/health/", HTTP_HOST="alpha.localhost"))

    assert response.status_code == 403
    assert json.loads(response.content)["code"] == "school_suspended"
    assert "school" not in seen


@pytest.mark.django_db
def test_trial_school_is_served(middleware, seen, school):
    school.status = School.Status.TRIAL
    school.save()

    response = middleware(RequestFactory().get("/api/health/", HTTP_HOST="alpha.localhost"))

    assert response.status_code == 200
    assert seen["school"] == school


@pytest.mark.django_db
def test_current_school_is_cleared_even_if_the_view_fails(school):
    def failing_view(request):
        raise RuntimeError("erreur dans la vue")

    with pytest.raises(RuntimeError):
        TenantMiddleware(failing_view)(RequestFactory().get("/", HTTP_HOST="alpha.localhost"))

    assert get_current_school() is None


@pytest.mark.django_db
def test_middleware_is_installed(client, school):
    response = client.get("/api/health/", HTTP_HOST="inconnue.localhost")

    assert response.status_code == 404
    assert response.json()["code"] == "school_not_found"


@pytest.mark.django_db
def test_each_school_has_its_time_zone(middleware, seen, school, other_school):
    other_school.timezone = "Africa/Kinshasa"
    other_school.save()

    middleware(RequestFactory().get("/api/health/", HTTP_HOST="alpha.localhost"))
    assert seen["timezone"] == "Africa/Lubumbashi"

    middleware(RequestFactory().get("/api/health/", HTTP_HOST="beta.localhost"))
    assert seen["timezone"] == "Africa/Kinshasa"
    # Après la requête : le fuseau du serveur.
    assert timezone.get_current_timezone_name() == "Africa/Lubumbashi"


@pytest.mark.django_db
def test_platform_hosts_keep_the_server_time_zone(middleware, seen):
    middleware(RequestFactory().get("/api/health/", HTTP_HOST="localhost"))

    assert seen["timezone"] == "Africa/Lubumbashi"

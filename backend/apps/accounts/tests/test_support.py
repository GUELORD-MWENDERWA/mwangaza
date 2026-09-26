"""Session support « en tant qu'école » (A3) : `/api/support/` à l'adresse de l'école."""

import time
from datetime import datetime
from unittest import mock

import pytest

from apps.accounts.models import Role
from apps.accounts.roles import PERMISSIONS
from apps.accounts.support import SUPPORT_DURATION, SUPPORT_EXCLUDED_PERMISSIONS
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import School
from conftest import Api
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SUPPORT = "/api/support/"
REASON = "Le directeur ne trouve plus le rôle de la caissière"


@pytest.fixture
def in_support(api, school, platform_admin):
    """Super-admin connecté à l'adresse de l'école alpha, session support ouverte."""
    client = api(platform_admin)
    response = client.post(SUPPORT, {"reason": REASON})
    assert response.status_code == 201, response.content
    return client


def journal(school) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.order_by("created_at", "id"))


def later(seconds: float):
    return mock.patch("apps.accounts.support.time.time", return_value=time.time() + seconds)


# Ouverture


def test_super_admin_opens_a_support_session(in_support, school, platform_admin):
    response = in_support.get(SUPPORT)

    assert response.status_code == 200
    body = response.json()
    assert body["school"] == {"code": "alpha", "name": school.name, "status": "active"}
    assert body["reason"] == REASON
    [entry] = journal(school)
    assert entry.action == Action.SUPPORT_STARTED
    assert entry.actor == platform_admin
    assert entry.impersonated_by == platform_admin
    assert entry.entity_id == school.pk
    assert entry.after["reason"] == REASON
    noted = datetime.fromisoformat(entry.after["expires_at"].replace("Z", "+00:00"))
    assert abs((noted - datetime.fromisoformat(body["expires_at"])).total_seconds()) < 0.001


def test_the_session_lasts_one_hour_at_most(in_support):
    body = in_support.get(SUPPORT).json()
    started = datetime.fromisoformat(body["started_at"])
    expires = datetime.fromisoformat(body["expires_at"])

    assert (expires - started).total_seconds() == SUPPORT_DURATION == 3600


def test_the_school_sees_support_mwangaza_in_its_journal(api, in_support, head):
    [item] = api(head).get("/api/audit/").json()["results"]

    assert item["action"] == "support.started"
    assert item["by_support"] is True
    assert item["actor"] is None


def test_reason_is_required(api, school, platform_admin):
    response = api(platform_admin).post(SUPPORT, {})

    assert response.status_code == 400
    assert "reason" in response.json()["fields"]
    assert journal(school) == []


# Pendant la session


def test_school_rights_except_the_cash(in_support):
    me = in_support.get("/api/me/").json()

    permissions = set(me["school"]["permissions"])
    assert permissions == set(PERMISSIONS) - SUPPORT_EXCLUDED_PERMISSIONS
    assert "finance.collect_payment" not in permissions
    assert "roles.manage" in permissions and "audit.view" in permissions
    assert me["school"]["roles"] == []
    assert me["support"]["reason"] == REASON
    assert in_support.get("/api/staff/").status_code == 200
    assert in_support.get("/api/roles/").status_code == 200


def test_each_action_of_the_session_is_marked(in_support, school, platform_admin):
    with use_school(school):
        role = Role.objects.get(code="teacher")

    response = in_support.patch(f"/api/roles/{role.id}/", {"name": "Professeur"})

    assert response.status_code == 200
    entry = journal(school)[-1]
    assert entry.action == Action.ROLES_UPDATED
    assert entry.actor == platform_admin
    assert entry.impersonated_by == platform_admin


def test_outside_a_session_the_super_admin_has_no_right(api, school, platform_admin):
    client = api(platform_admin)

    assert client.get("/api/staff/").status_code == 403
    assert client.get("/api/me/").json()["support"] is None
    assert client.get(SUPPORT).json()["code"] == "no_support_session"


# Fin de la session


def test_after_one_hour_the_session_is_over(in_support):
    with later(SUPPORT_DURATION + 1):
        assert in_support.get("/api/staff/").status_code == 403
        assert in_support.get("/api/me/").json()["support"] is None
    # Oubliée : elle ne revient pas.
    assert in_support.get("/api/staff/").status_code == 403


def test_just_before_one_hour_it_still_works(in_support):
    with later(SUPPORT_DURATION - 5):
        assert in_support.get("/api/staff/").status_code == 200


def test_closing_the_session(in_support, school, platform_admin):
    response = in_support.delete(SUPPORT)

    assert response.status_code == 204
    entry = journal(school)[-1]
    assert entry.action == Action.SUPPORT_ENDED
    assert entry.impersonated_by == platform_admin
    assert in_support.get("/api/staff/").status_code == 403
    assert in_support.delete(SUPPORT).status_code == 404


def test_logging_out_closes_the_session(in_support, school):
    assert in_support.post("/api/auth/logout/").status_code == 204

    assert journal(school)[-1].action == Action.SUPPORT_ENDED


def test_reopening_closes_the_previous_session(in_support, school):
    assert in_support.post(SUPPORT, {"reason": "Autre demande"}).status_code == 201

    actions = [entry.action for entry in journal(school)]
    assert actions == [Action.SUPPORT_STARTED, Action.SUPPORT_ENDED, Action.SUPPORT_STARTED]


def test_an_account_no_longer_super_admin_loses_the_session(in_support, platform_admin):
    platform_admin.is_platform_admin = False
    platform_admin.save()

    assert in_support.get("/api/staff/").status_code == 403


# Refus


def test_only_the_super_admin_opens_a_session(api, school, head):
    response = api(head).post(SUPPORT, {"reason": REASON})

    assert response.status_code == 403
    assert response.json()["code"] == "not_platform_admin"
    assert journal(school) == []


def test_two_factor_authentication_is_required(api, school, platform_admin):
    response = api(platform_admin, mfa=False).post(SUPPORT, {"reason": REASON})

    assert response.status_code == 403
    assert response.json()["code"] == "totp_required"
    assert journal(school) == []


def test_anonymous_is_refused(api, school):
    assert api().post(SUPPORT, {"reason": REASON}).json()["code"] == "not_authenticated"


def test_not_at_the_platform_address(api, platform_admin):
    response = api(platform_admin, host="localhost").post(SUPPORT, {"reason": REASON})

    assert response.status_code == 404
    assert response.json()["code"] == "school_not_found"


def test_not_in_a_suspended_school(api, school, platform_admin):
    school.status = School.Status.SUSPENDED
    school.save()

    response = api(platform_admin).post(SUPPORT, {"reason": REASON})

    assert response.status_code == 403
    assert response.json()["code"] == "school_suspended"


# Isolation des écoles


def test_a_session_in_one_school_gives_nothing_in_another(in_support, school, other_school):
    MembershipFactory(school=other_school, roles=["head"])
    elsewhere = Api(in_support.client, "beta.localhost")

    assert elsewhere.get("/api/staff/").status_code == 403
    assert elsewhere.get("/api/me/").json()["support"] is None
    assert elsewhere.get(SUPPORT).status_code == 404
    assert journal(other_school) == []
    # Toujours valable à l'adresse de l'école alpha.
    assert in_support.get("/api/staff/").status_code == 200

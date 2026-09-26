"""GET /api/me/ : le compte, ses écoles, ses droits dans l'école de l'adresse."""

import pytest

from apps.accounts.models import Role
from apps.accounts.roles import SYSTEM_ROLES
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/me/"


def test_anonymous_is_refused(api, school):
    response = api().get(URL)

    assert response.status_code == 403
    assert response.json()["code"] == "not_authenticated"


def test_head_sees_their_roles_and_permissions(api, school):
    user = UserFactory(last_name="Kambale", middle_name="Muhindo", first_name="Patrice")
    MembershipFactory(user=user, school=school, roles=["head"])
    with use_school(school):
        head_role = Role.objects.get(code="head")

    data = api(user).get(URL).json()

    assert data["id"] == str(user.id)
    assert data["phone"] == user.phone
    assert (data["last_name"], data["middle_name"], data["first_name"]) == (
        "Kambale",
        "Muhindo",
        "Patrice",
    )
    assert data["language"] == "fr"
    assert data["must_change_password"] is False
    assert data["schools"] == [
        {"code": "alpha", "name": "École Alpha (fictive)", "status": "active"}
    ]
    school_data = data["school"]
    assert (school_data["code"], school_data["name"]) == ("alpha", "École Alpha (fictive)")
    assert school_data["roles"] == [{"id": str(head_role.id), "code": "head", "name": ""}]
    assert school_data["permissions"] == list(SYSTEM_ROLES["head"].permissions)


def test_one_account_in_two_schools(api, school, other_school):
    user = UserFactory()
    MembershipFactory(user=user, school=school, roles=["head"])
    MembershipFactory(user=user, school=other_school, roles=["teacher"])

    at_alpha = api(user).get(URL).json()
    at_beta = api(user, host="beta.localhost").get(URL).json()
    at_platform = api(user, host="localhost").get(URL).json()

    assert [s["code"] for s in at_alpha["schools"]] == ["alpha", "beta"]
    assert [r["code"] for r in at_alpha["school"]["roles"]] == ["head"]
    # Dans chaque école, seulement les rôles et permissions de cette école.
    assert [r["code"] for r in at_beta["school"]["roles"]] == ["teacher"]
    assert at_beta["school"]["permissions"] == []
    # Adresse générale : choix de l'école (M2), aucun droit.
    assert at_platform["school"] is None
    assert len(at_platform["schools"]) == 2


def test_no_access_to_a_school_where_the_account_has_no_role(api, head, other_school):
    data = api(head, host="beta.localhost").get(URL).json()

    assert data["school"] is None
    assert [s["code"] for s in data["schools"]] == ["alpha"]


def test_deactivated_membership_is_not_listed(api, school, other_school):
    user = UserFactory()
    MembershipFactory(user=user, school=school, roles=["head"], is_active=False)
    MembershipFactory(user=user, school=other_school, roles=["cashier"])

    data = api(user).get(URL).json()

    assert data["school"] is None
    assert [s["code"] for s in data["schools"]] == ["beta"]


def test_temporary_password_must_be_changed(api, school):
    user = MembershipFactory(school=school, user__must_change_password=True).user

    assert api(user).get(URL).json()["must_change_password"] is True

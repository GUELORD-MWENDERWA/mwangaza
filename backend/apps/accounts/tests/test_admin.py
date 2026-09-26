"""Administration Django : super-admin seulement ; rôles et appartenances de toutes les écoles en
lecture seule."""

import pytest
from django.test import Client

from apps.accounts.models import Role, User
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(db):
    admin = User.objects.create_superuser("0000000000", "secret-123", last_name="Admin")
    client = Client(HTTP_HOST="localhost")
    client.force_login(admin)
    return client


def test_pages_open_for_the_platform_admin(admin_client, school, other_school):
    membership = MembershipFactory(school=school, roles=["head", "teacher"])
    role = Role.all_schools.filter(school=other_school).first()

    for path in [
        "/admin/",
        "/admin/accounts/user/",
        "/admin/accounts/user/add/",
        f"/admin/accounts/user/{membership.user.id}/change/",
        "/admin/accounts/role/",
        f"/admin/accounts/role/{role.id}/change/",
        "/admin/accounts/membership/",
        f"/admin/accounts/membership/{membership.id}/change/",
        "/admin/schools/school/",
    ]:
        assert admin_client.get(path).status_code == 200, path


def test_roles_of_all_schools_are_listed(admin_client, school, other_school):
    content = admin_client.get("/admin/accounts/role/?all=").content.decode()

    assert "École Alpha (fictive)" in content
    assert "École Beta (fictive)" in content


def test_membership_page_shows_its_roles(admin_client, school):
    membership = MembershipFactory(school=school, roles=["cashier"])

    content = admin_client.get(f"/admin/accounts/membership/{membership.id}/change/").content

    assert b"Cashier" in content or b"Caissier" in content


def test_roles_and_memberships_are_read_only(admin_client, school):
    membership = MembershipFactory(school=school, roles=["cashier"])

    assert admin_client.get("/admin/accounts/role/add/").status_code == 403
    assert admin_client.get("/admin/accounts/membership/add/").status_code == 403
    response = admin_client.post(
        f"/admin/accounts/membership/{membership.id}/change/", {"is_active": ""}
    )
    assert response.status_code == 403
    membership.refresh_from_db()
    assert membership.is_active


def test_create_an_account_with_a_local_number(admin_client):
    response = admin_client.post(
        "/admin/accounts/user/add/",
        {
            "phone": "097 123 45 67",
            "last_name": "Kasereka",
            "middle_name": "",
            "first_name": "Jean",
            "usable_password": "true",
            "password1": "un-mot-de-passe-long-42",
            "password2": "un-mot-de-passe-long-42",
        },
    )

    assert response.status_code == 302, response.content.decode()[:2000]
    user = User.objects.get(phone="+243971234567")
    assert user.check_password("un-mot-de-passe-long-42")
    assert not user.is_platform_admin


def test_staff_of_a_school_cannot_enter(school):
    head = MembershipFactory(school=school, roles=["head"]).user
    client = Client(HTTP_HOST="localhost")
    client.force_login(head)

    response = client.get("/admin/accounts/user/")

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_django_groups_are_hidden(admin_client):
    assert admin_client.get("/admin/auth/group/").status_code == 404

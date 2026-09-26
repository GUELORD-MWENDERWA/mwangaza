"""Permission serveur des points d'API d'une école (`HasSchoolPermission`).

Exemple : la liste des rôles, qui demande `roles.manage` (seul le directeur l'a parmi les rôles
système).
"""

import pytest

from apps.accounts.models import Role, User
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/roles/"


def test_anonymous_is_refused(api, school):
    response = api().get(URL)

    assert response.status_code == 403
    assert response.json()["code"] == "not_authenticated"


def test_member_with_the_permission_is_allowed(api, head):
    assert api(head).get(URL).status_code == 200


def test_member_without_the_permission_is_refused(api, cashier):
    response = api(cashier).get(URL)

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_account_without_membership_is_refused(api, school):
    assert api(UserFactory()).get(URL).status_code == 403


def test_platform_admin_has_no_right_in_a_school(api, school):
    # Connexion « en tant qu'école » tracée : tâche 1.5.
    admin = User.objects.create_superuser("0000000000", "secret-123", last_name="Admin")

    assert api(admin).get(URL).status_code == 403


def test_deactivated_membership_is_refused(api, school):
    membership = MembershipFactory(school=school, roles=["head"], is_active=False)

    assert api(membership.user).get(URL).status_code == 403


def test_deactivated_account_is_logged_out(api, head):
    client = api(head)
    head.is_active = False
    head.save()

    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()["code"] == "not_authenticated"


def test_head_of_one_school_has_no_right_in_another(api, head, other_school):
    response = api(head, host="beta.localhost").get(URL)

    assert response.status_code == 403


def test_address_without_school_is_not_found(api, head):
    response = api(head, host="localhost").get(URL)

    assert response.status_code == 404
    assert response.json()["code"] == "school_not_found"


def test_permission_comes_from_the_roles_of_the_school(api, school):
    # Rôle créé par l'école avec `roles.manage` : accès ; directeur privé du code : refus.
    with use_school(school):
        manager = Role.objects.create(name="Gestionnaire", permissions=["roles.manage"])
        head_role = Role.objects.get(code="head")
    custom = MembershipFactory(school=school, roles=[manager]).user
    head = MembershipFactory(school=school, roles=["head"]).user
    with use_school(school):
        head_role.permissions = ["students.view"]
        head_role.save()

    assert api(custom).get(URL).status_code == 200
    assert api(head).get(URL).status_code == 403


def test_permissions_add_up_across_roles(api, school):
    user = MembershipFactory(school=school, roles=["teacher", "head"]).user

    assert api(user).get(URL).status_code == 200


def test_debug_login_page_does_not_exist_outside_development(api, school):
    # « Log in » de l'API navigable : seulement en DEBUG (réglages de test : DEBUG=False).
    assert api(host="localhost").get("/api/auth/login/").status_code == 404

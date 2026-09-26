"""Permission serveur des points d'API d'une école (`HasSchoolPermission`).

Exemple : la liste des rôles, qui demande `roles.manage` (seul le directeur l'a parmi les rôles
système).
"""

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.login import MFA_SESSION_KEY
from apps.accounts.models import Role, User
from apps.accounts.permissions import HasSchoolPermission
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


# Double authentification (B4) : vérifiée à chaque requête, pas seulement à la connexion.


def test_sensitive_roles_need_a_session_with_two_factor_authentication(api, head):
    response = api(head, mfa=False).get(URL)

    assert response.status_code == 403
    assert response.json()["code"] == "totp_required"


def _has_permission(user, school, permission: str, *, mfa: bool) -> bool:
    view = SimpleNamespace(required_permission=permission)
    request = SimpleNamespace(user=user, school=school, session={MFA_SESSION_KEY: mfa})
    return HasSchoolPermission().has_permission(request, view)


def test_role_without_sensitive_right_does_not_need_it(school):
    secretary = MembershipFactory(school=school, roles=["secretary"]).user

    assert _has_permission(secretary, school, "students.view", mfa=False) is True


def test_any_right_on_money_needs_it_even_for_another_permission(school):
    # Caissier, ou rôle créé par l'école avec un droit sur l'argent : rien n'est lié au nom.
    with use_school(school):
        reports = Role.objects.create(
            name="Lecteur des rapports", permissions=["finance.view_reports", "students.view"]
        )
    cashier = MembershipFactory(school=school, roles=["cashier"]).user
    reader = MembershipFactory(school=school, roles=[reports]).user

    for user in (cashier, reader):
        with pytest.raises(PermissionDenied) as refused:
            _has_permission(user, school, "students.view", mfa=False)
        assert refused.value.get_codes() == "totp_required"
        assert _has_permission(user, school, "students.view", mfa=True) is True


def test_role_given_during_the_session_asks_for_it(api, school):
    # Enseignant connecté sans double authentification, puis nommé directeur : refusé jusqu'à
    # une nouvelle connexion.
    membership = MembershipFactory(school=school, roles=["teacher"])
    client = api(membership.user, mfa=False)
    with use_school(school):
        membership.roles.set([Role.objects.get(code="head")])

    assert client.get(URL).json()["code"] == "totp_required"

"""/api/roles/ : rôles de l'école (B1 à B2), permission `roles.manage`."""

import pytest

from apps.accounts.models import Role
from apps.accounts.roles import STARTER_ROLES
from apps.core.tenancy import use_all_schools, use_school
from tests.factories import MembershipFactory, starter_role

pytestmark = pytest.mark.django_db

URL = "/api/roles/"


def role(school, **lookup) -> Role:
    with use_school(school):
        return Role.objects.get(**lookup)


def custom_role(school, name="Chef d'atelier", permissions=("students.view",)) -> Role:
    with use_school(school):
        return Role.objects.create(name=name, permissions=list(permissions))


# Lecture


def test_list_roles_in_creation_order_with_member_counts(api, head, school):
    custom_role(school)
    MembershipFactory(school=school, roles=["cashier"])
    MembershipFactory(school=school, roles=["cashier"])
    MembershipFactory(school=school, roles=["cashier"], is_active=False)

    results = api(head).get(URL).json()["results"]

    assert len(results) == len(STARTER_ROLES) + 1
    by_name = {r["name"]: r for r in results}
    assert by_name["Caissier"]["member_count"] == 2
    assert by_name["Directeur"]["member_count"] == 1
    assert by_name["Caissier"]["permissions"] == list(STARTER_ROLES["cashier"].permissions)
    # Rien ne distingue un rôle du modèle de départ d'un rôle créé par l'école.
    assert results[-1] | {"id": None} == {
        "id": None,
        "name": "Chef d'atelier",
        "permissions": ["students.view"],
        "member_count": 0,
    }


# Création (B2)


def test_create_school_role(api, head, school):
    response = api(head).post(
        URL,
        {
            "name": " Surveillant de caisse ",
            "permissions": ["finance.view_reports", "students.view"],
        },
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["name"] == "Surveillant de caisse"
    assert data["permissions"] == ["students.view", "finance.view_reports"]
    assert data["member_count"] == 0
    created = role(school, pk=data["id"])
    assert created.created_by == head


def test_create_needs_a_name(api, head):
    response = api(head).post(URL, {"permissions": ["students.view"]})

    assert response.status_code == 400
    assert response.json()["code"] == "role_name_required"


def test_create_refuses_a_name_taken_in_the_school(api, head, school):
    custom_role(school)

    response = api(head).post(URL, {"name": "chef D'ATELIER"})

    assert response.status_code == 409
    assert response.json()["code"] == "role_name_taken"


def test_create_refuses_an_unknown_permission(api, head):
    response = api(head).post(URL, {"name": "Pirate", "permissions": ["students.delete"]})

    assert response.status_code == 400
    assert "permissions.0" in response.json()["fields"]


# Modification


def test_rename_a_starter_role(api, head, school):
    head_role = starter_role(school, "head")

    renamed = api(head).patch(f"{URL}{head_role.id}/", {"name": "Préfet des études"})
    taken = api(head).patch(f"{URL}{head_role.id}/", {"name": "caissier"})

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Préfet des études"
    assert (taken.status_code, taken.json()["code"]) == (409, "role_name_taken")
    assert role(school, pk=head_role.pk).name == "Préfet des études"


@pytest.mark.parametrize("key", ["cashier", None])
def test_every_role_keeps_a_name(api, head, school, key):
    # Un rôle du modèle de départ comme un rôle créé par l'école.
    target = starter_role(school, key) if key else custom_role(school)

    response = api(head).patch(f"{URL}{target.id}/", {"name": " "})

    assert response.status_code == 400
    assert response.json()["code"] == "role_name_required"
    assert role(school, pk=target.pk).name == target.name


def test_change_permissions_of_a_role(api, head, school):
    cashier = starter_role(school, "cashier")

    response = api(head).patch(
        f"{URL}{cashier.id}/", {"permissions": ["finance.close_register", "students.view"]}
    )

    assert response.status_code == 200
    assert role(school, pk=cashier.pk).permissions == ["students.view", "finance.close_register"]


def test_put_is_not_allowed(api, head, school):
    response = api(head).client.put(
        f"{URL}{starter_role(school, 'cashier').id}/",
        {"name": "x"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"


# Dernier gestionnaire des rôles


def test_cannot_remove_roles_manage_from_the_only_managers(api, head, school):
    head_role = starter_role(school, "head")

    response = api(head).patch(f"{URL}{head_role.id}/", {"permissions": ["students.view"]})

    assert response.status_code == 409
    assert response.json()["code"] == "last_role_manager"
    assert "roles.manage" in role(school, pk=head_role.pk).permissions


def test_can_remove_roles_manage_when_another_role_keeps_it(api, head, school):
    manager = custom_role(school, name="Gestionnaire", permissions=["roles.manage"])
    MembershipFactory(school=school, roles=[manager])
    head_role = starter_role(school, "head")

    response = api(head).patch(f"{URL}{head_role.id}/", {"permissions": ["students.view"]})

    assert response.status_code == 200


# Suppression


@pytest.mark.parametrize("key", ["teacher", None])
def test_delete_an_unused_role(api, head, school, key):
    # Plus de rôle protégé : celui du modèle de départ se supprime comme un autre.
    target = starter_role(school, key) if key else custom_role(school)

    response = api(head).delete(f"{URL}{target.id}/")

    assert response.status_code == 204
    with use_school(school):
        assert not Role.objects.filter(pk=target.pk).exists()


def test_cannot_delete_a_role_still_given(api, head, school):
    custom = custom_role(school)
    MembershipFactory(school=school, roles=[custom], is_active=False)

    response = api(head).delete(f"{URL}{custom.id}/")

    assert response.status_code == 409
    assert response.json()["code"] == "role_in_use"


def test_the_role_of_the_last_role_manager_cannot_be_deleted(api, head, school):
    # Garde-fou : ce rôle est donné à quelqu'un, et le dernier gestionnaire ne peut pas se le
    # retirer (`test_staff_api`) ; l'école garde donc toujours un compte qui gère les rôles.
    head_role = starter_role(school, "head")

    response = api(head).delete(f"{URL}{head_role.id}/")

    assert (response.status_code, response.json()["code"]) == (409, "role_in_use")
    assert role(school, pk=head_role.pk).permissions == list(STARTER_ROLES["head"].permissions)


# Permission et isolation


@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
def test_without_roles_manage_everything_is_refused(api, cashier, school, method):
    target = starter_role(school, "teacher")
    path = URL if method == "post" else f"{URL}{target.id}/"

    response = getattr(api(cashier), method)(path)

    assert response.status_code == 403


def test_other_school_roles_are_invisible(api, head, other_head, school, other_school):
    alpha_custom = custom_role(school, name="Rôle secret d'Alpha")

    results = api(other_head, host="beta.localhost").get(URL).json()["results"]

    ids = {r["id"] for r in results}
    assert str(alpha_custom.id) not in ids
    with use_all_schools():
        assert ids == {str(r.id) for r in Role.all_schools.filter(school=other_school)}
    assert "Alpha" not in str(results)


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_other_school_role_is_not_found(api, other_head, school, other_school, method):
    alpha_custom = custom_role(school)
    beta = api(other_head, host="beta.localhost")

    response = getattr(beta, method)(f"{URL}{alpha_custom.id}/")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    unchanged = role(school, pk=alpha_custom.pk)
    assert (unchanged.name, unchanged.permissions) == ("Chef d'atelier", ["students.view"])


def test_role_created_from_one_school_stays_in_it(api, head, school, other_school):
    api(head).post(URL, {"name": "Chef d'atelier"})

    with use_school(other_school):
        assert not Role.objects.filter(name="Chef d'atelier").exists()
    with use_school(school):
        assert Role.objects.filter(name="Chef d'atelier").exists()

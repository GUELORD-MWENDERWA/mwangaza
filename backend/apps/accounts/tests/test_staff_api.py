"""/api/staff/ : comptes du personnel de l'école (M3, B1 à B3), permission `roles.manage`."""

import re

import pytest

from apps.accounts import services
from apps.accounts.models import Membership, RecoveryCode, Role, User
from apps.core.tenancy import use_school
from tests.factories import (
    TEST_PASSWORD,
    MembershipFactory,
    UserFactory,
    enable_totp,
    totp_code,
)

pytestmark = pytest.mark.django_db

URL = "/api/staff/"


def role_id(school, code) -> str:
    with use_school(school):
        return str(Role.objects.get(code=code).id)


def role_codes(membership) -> set[str]:
    with use_school(membership.school):
        return {role.code for role in membership.roles.all()}


# Liste


def test_list_the_school_staff(api, head, school, other_school):
    cashier = MembershipFactory(
        school=school, roles=["cashier"], user__last_name="Kahindo", user__first_name="Grâce"
    )
    MembershipFactory(school=other_school, roles=["cashier"], user__last_name="Byamungu")

    results = api(head).get(URL).json()["results"]

    assert len(results) == 2
    entry = next(r for r in results if r["id"] == str(cashier.id))
    assert entry["user"] == {
        "id": str(cashier.user.id),
        "phone": cashier.user.phone,
        "last_name": "Kahindo",
        "middle_name": "",
        "first_name": "Grâce",
    }
    assert entry["roles"] == [role_id(school, "cashier")]
    assert entry["is_active"] is True
    assert "Byamungu" not in str(results)


def test_list_shows_nothing_of_the_other_schools_of_a_person(api, head, school, other_school):
    user = UserFactory()
    MembershipFactory(user=user, school=school, roles=["teacher"])
    MembershipFactory(user=user, school=other_school, roles=["head"])

    content = api(head).get(URL).content.decode()

    assert "beta" not in content
    assert "Beta" not in content
    assert role_id(other_school, "head") not in content


def test_filter_by_name_phone_role_and_state(api, head, school):
    kahindo = MembershipFactory(
        school=school,
        roles=["cashier"],
        user__last_name="Kahindo",
        user__middle_name="Masika",
        user__first_name="Grâce",
        user__phone="+243000071234",
    )
    former = MembershipFactory(
        school=school, roles=["cashier"], is_active=False, user__last_name="Byamungu"
    )
    MembershipFactory(school=school, roles=["secretary"], user__last_name="Furaha")
    client = api(head)

    def found(**params) -> list[str]:
        response = client.get(URL, **params)
        assert response.status_code == 200, response.content
        return [item["id"] for item in response.json()["results"]]

    assert found(search="grâce kahi") == [str(kahindo.id)]
    assert found(search="masika") == [str(kahindo.id)]
    assert found(search="000071234") == [str(kahindo.id)]  # forme nationale : 0 + 9 chiffres
    assert found(role=role_id(school, "cashier")) == [str(former.id), str(kahindo.id)]
    assert found(role=role_id(school, "cashier"), is_active="false") == [str(former.id)]
    assert len(found(is_active="true")) == 3


def test_filter_by_a_role_of_another_school_is_refused(api, head, other_school):
    response = api(head).get(URL, role=role_id(other_school, "cashier"))

    assert response.status_code == 400
    assert response.json()["fields"]["role"][0]["code"] == "does_not_exist"


# Ajout


def test_add_a_new_person(api, head, school):
    response = api(head).post(
        URL,
        {
            "phone": "097 118 30 62",
            "last_name": "Kavira",
            "middle_name": "Mbambu",
            "first_name": "Jeanne",
            "roles": [role_id(school, "cashier")],
        },
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["existing_account"] is False
    assert re.fullmatch(r"[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}", data["temporary_password"])
    assert data["user"]["phone"] == "+243971183062"
    user = User.objects.get(phone="+243971183062")
    assert user.get_full_name() == "Kavira Mbambu Jeanne"
    assert user.check_password(data["temporary_password"])
    assert user.must_change_password
    assert user.created_by == head
    membership = Membership.objects.get(pk=data["id"])
    assert (membership.school, membership.created_by) == (school, head)
    assert role_codes(membership) == {"cashier"}


def test_temporary_password_is_shown_only_once(api, head, school):
    created = (
        api(head)
        .post(
            URL,
            {"phone": "0971183062", "last_name": "Kavira", "roles": [role_id(school, "cashier")]},
        )
        .json()
    )

    listed = api(head).get(URL).json()["results"]
    detail = api(head).get(f"{URL}{created['id']}/").json()

    assert "temporary_password" not in str(listed)
    assert "temporary_password" not in detail


def test_add_a_person_who_already_has_an_account_elsewhere(api, head, school, other_school):
    user = UserFactory(
        phone="+243819024417", last_name="Ombeni", middle_name="", first_name="Baraka"
    )
    MembershipFactory(user=user, school=other_school, roles=["head"])

    response = api(head).post(
        URL,
        {
            "phone": "0819024417",
            "last_name": "Autre nom",
            "first_name": "Ignoré",
            "roles": [role_id(school, "teacher")],
        },
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["existing_account"] is True
    assert data["temporary_password"] is None
    # Un seul compte, ses noms et son mot de passe inchangés, rien dit de l'autre école.
    assert User.objects.filter(phone="+243819024417").count() == 1
    user.refresh_from_db()
    assert (user.last_name, user.first_name) == ("Ombeni", "Baraka")
    assert user.check_password(TEST_PASSWORD)
    assert "beta" not in response.content.decode().lower()
    assert role_codes(Membership.objects.get(user=user, school=other_school)) == {"head"}


def test_cannot_add_someone_twice(api, head, school):
    existing = MembershipFactory(school=school, roles=["teacher"], is_active=False)

    response = api(head).post(
        URL, {"phone": existing.user.phone, "roles": [role_id(school, "cashier")]}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "already_member"


def test_new_number_needs_a_last_name(api, head, school):
    response = api(head).post(URL, {"phone": "0971183062", "roles": [role_id(school, "cashier")]})

    assert response.status_code == 400
    assert response.json()["code"] == "names_required"
    assert not User.objects.filter(phone="+243971183062").exists()


def test_invalid_phone(api, head, school):
    response = api(head).post(
        URL, {"phone": "12345", "last_name": "X", "roles": [role_id(school, "cashier")]}
    )

    assert response.status_code == 400
    [error] = response.json()["fields"]["phone"]
    assert error["detail"].startswith("Saisissez un numéro de téléphone valide")


def test_at_least_one_role(api, head):
    response = api(head).post(URL, {"phone": "0971183062", "last_name": "X", "roles": []})

    assert response.status_code == 400
    assert "roles" in response.json()["fields"]


def test_role_of_another_school_is_refused(api, head, school, other_school):
    response = api(head).post(
        URL, {"phone": "0971183062", "last_name": "X", "roles": [role_id(other_school, "head")]}
    )

    assert response.status_code == 400
    assert "roles" in response.json()["fields"]
    assert not User.objects.filter(phone="+243971183062").exists()


# Modification


def test_change_roles(api, head, school):
    member = MembershipFactory(school=school, roles=["cashier"])

    response = api(head).patch(
        f"{URL}{member.id}/", {"roles": [role_id(school, "accountant"), role_id(school, "teacher")]}
    )

    assert response.status_code == 200
    assert set(response.json()["roles"]) == {
        role_id(school, "accountant"),
        role_id(school, "teacher"),
    }
    assert role_codes(member) == {"accountant", "teacher"}


def test_deactivate_then_reactivate(api, head, school):
    member = MembershipFactory(school=school, roles=["cashier"])

    off = api(head).patch(f"{URL}{member.id}/", {"is_active": False})
    assert off.json()["is_active"] is False
    # Plus aucun accès à l'école, tout de suite.
    assert api(member.user).get("/api/me/").json()["school"] is None

    on = api(head).patch(f"{URL}{member.id}/", {"is_active": True})
    assert on.json()["is_active"] is True
    assert api(member.user).get("/api/me/").json()["school"]["code"] == "alpha"


def test_deactivation_keeps_the_account_valid_in_other_schools(api, head, school, other_school):
    user = UserFactory()
    member = MembershipFactory(user=user, school=school, roles=["cashier"])
    MembershipFactory(user=user, school=other_school, roles=["cashier"])

    api(head).patch(f"{URL}{member.id}/", {"is_active": False})

    user.refresh_from_db()
    assert user.is_active
    assert api(user, host="beta.localhost").get("/api/me/").json()["school"]["code"] == "beta"


def test_role_of_another_school_is_refused_on_update(api, head, school, other_school):
    member = MembershipFactory(school=school, roles=["cashier"])

    response = api(head).patch(f"{URL}{member.id}/", {"roles": [role_id(other_school, "head")]})

    assert response.status_code == 400
    assert role_codes(member) == {"cashier"}


def test_cannot_delete_an_account(api, head, school):
    member = MembershipFactory(school=school, roles=["cashier"])

    response = api(head).delete(f"{URL}{member.id}/")

    assert response.status_code == 405
    assert Membership.objects.filter(pk=member.pk).exists()


# Dernier gestionnaire des rôles (M3 : « impossible de se retirer soi-même le dernier rôle de
# directeur »)


def test_last_head_cannot_remove_their_own_head_role(api, head, school):
    membership = head.memberships.get()

    response = api(head).patch(f"{URL}{membership.id}/", {"roles": [role_id(school, "teacher")]})

    assert response.status_code == 409
    assert response.json()["code"] == "last_role_manager"
    assert role_codes(membership) == {"head"}


def test_last_head_cannot_deactivate_themself(api, head, school):
    membership = head.memberships.get()

    response = api(head).patch(f"{URL}{membership.id}/", {"is_active": False})

    assert response.status_code == 409
    membership.refresh_from_db()
    assert membership.is_active


def test_a_head_can_step_down_when_another_remains(api, head, school):
    MembershipFactory(school=school, roles=["head"])
    membership = head.memberships.get()

    response = api(head).patch(f"{URL}{membership.id}/", {"roles": [role_id(school, "teacher")]})

    assert response.status_code == 200


def test_a_deactivated_account_does_not_count_as_manager(api, head, school):
    other = MembershipFactory(school=school, roles=["head"])
    other.user.is_active = False
    other.user.save()
    membership = head.memberships.get()

    response = api(head).patch(f"{URL}{membership.id}/", {"is_active": False})

    assert response.status_code == 409


# Permission et isolation


@pytest.mark.parametrize("method", ["get", "post", "patch"])
def test_without_roles_manage_everything_is_refused(api, cashier, school, method):
    target = cashier.memberships.get()
    path = URL if method == "post" else f"{URL}{target.id}/"

    response = getattr(api(cashier), method)(path)

    assert response.status_code == 403


@pytest.mark.parametrize("method", ["get", "patch"])
def test_other_school_member_is_not_found(api, other_head, school, other_school, method):
    alpha_member = MembershipFactory(school=school, roles=["cashier"])

    response = getattr(api(other_head, host="beta.localhost"), method)(
        f"{URL}{alpha_member.id}/", **({"data": {"is_active": False}} if method == "patch" else {})
    )

    assert response.status_code == 404
    alpha_member.refresh_from_db()
    assert alpha_member.is_active
    assert role_codes(alpha_member) == {"cashier"}


def test_other_school_head_cannot_give_roles_here(api, other_head, school):
    # Directeur de beta sur l'adresse d'alpha : aucun droit.
    response = api(other_head).post(
        URL, {"phone": other_head.phone, "roles": [role_id(school, "head")]}
    )

    assert response.status_code == 403
    assert not Membership.objects.filter(user=other_head, school=school).exists()


def test_person_added_from_one_school_is_only_in_it(api, head, school, other_school):
    api(head).post(
        URL, {"phone": "0971183062", "last_name": "Kavira", "roles": [role_id(school, "cashier")]}
    )

    user = User.objects.get(phone="+243971183062")
    assert [m.school for m in user.memberships.all()] == [school]


# Double authentification, dernière connexion, compte géré par l'école (M3)


def by_id(api_client) -> dict:
    return {entry["id"]: entry for entry in api_client.get(URL).json()["results"]}


def test_list_shows_two_factor_status_for_this_school(api, head, school, other_school):
    enabled = MembershipFactory(school=school, roles=["teacher"])
    enable_totp(enabled.user)
    to_enable = MembershipFactory(school=school, roles=["cashier"])
    not_required = MembershipFactory(school=school, roles=["teacher"])
    # Exigée par un rôle dans une autre école : l'école alpha ne le voit pas.
    MembershipFactory(user=not_required.user, school=other_school, roles=["cashier"])

    staff = by_id(api(head))

    assert staff[str(enabled.id)]["totp"] == "enabled"
    assert staff[str(to_enable.id)]["totp"] == "to_enable"
    assert staff[str(not_required.id)]["totp"] == "not_required"


def test_last_login_is_the_one_at_this_school(api, head, school, other_school):
    member = MembershipFactory(school=school, roles=["teacher"])
    MembershipFactory(user=member.user, school=other_school, roles=["teacher"])

    response = api(host="beta.localhost").post(
        "/api/auth/login/", {"phone": member.user.phone, "password": TEST_PASSWORD}
    )

    assert response.json()["step"] == "done"
    assert by_id(api(head))[str(member.id)]["last_login_at"] is None
    assert Membership.objects.get(user=member.user, school=other_school).last_login_at


def test_account_managed_here_only_if_used_nowhere_else(api, head, school, other_school):
    only_here = MembershipFactory(school=school, roles=["teacher"])
    elsewhere = MembershipFactory(school=school, roles=["teacher"])
    MembershipFactory(user=elsewhere.user, school=other_school, is_active=False)
    admin = User.objects.create_superuser("0000090999", "secret-123", last_name="Admin")
    admin_member = MembershipFactory(user=admin, school=school, roles=["teacher"])

    staff = by_id(api(head))

    assert staff[str(only_here.id)]["account_managed_here"] is True
    assert staff[str(elsewhere.id)]["account_managed_here"] is False
    assert staff[str(admin_member.id)]["account_managed_here"] is False
    detail = api(head).get(f"{URL}{elsewhere.id}/").json()
    assert detail["account_managed_here"] is False


def test_new_password_for_an_account_used_only_here(api, head, school):
    member = MembershipFactory(school=school, roles=["cashier"])
    session_of_the_person = api(member.user)

    response = api(head).post(f"{URL}{member.id}/new-password/")

    assert response.status_code == 200
    password = response.json()["temporary_password"]
    assert re.fullmatch(r"[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}", password)
    member.user.refresh_from_db()
    assert member.user.must_change_password is True
    assert member.user.check_password(password)
    # Ses sessions ouvertes sont fermées ; à la connexion, nouveau mot de passe d'abord.
    assert session_of_the_person.get("/api/me/").status_code == 403
    login = api().post("/api/auth/login/", {"phone": member.user.phone, "password": password})
    assert login.json()["step"] == "new_password"


def test_no_new_password_for_an_account_used_elsewhere(api, head, school, other_school):
    member = MembershipFactory(school=school, roles=["teacher"])
    MembershipFactory(user=member.user, school=other_school, roles=["head"])

    response = api(head).post(f"{URL}{member.id}/new-password/")

    assert response.status_code == 409
    assert response.json()["code"] == "account_used_elsewhere"
    assert "beta" not in response.content.decode().lower()
    member.user.refresh_from_db()
    assert member.user.check_password(TEST_PASSWORD)
    assert member.user.must_change_password is False


def test_platform_admin_account_is_not_managed_by_a_school(api, head, school):
    admin = User.objects.create_superuser("0000090999", "secret-123", last_name="Admin")
    member = MembershipFactory(user=admin, school=school, roles=["teacher"])

    response = api(head).post(f"{URL}{member.id}/new-password/")

    assert response.json()["code"] == "account_used_elsewhere"


def test_reset_two_factor_authentication(api, head, school):
    member = MembershipFactory(school=school, roles=["cashier"])
    secret = enable_totp(member.user)
    services.enable_totp(member.user, secret, totp_code(secret))

    response = api(head).post(f"{URL}{member.id}/reset-totp/")

    assert response.status_code == 200
    assert response.json()["totp"] == "to_enable"
    member.user.refresh_from_db()
    assert (member.user.totp_enabled, member.user.totp_secret) == (False, "")
    assert not RecoveryCode.objects.filter(user=member.user).exists()
    login = api().post("/api/auth/login/", {"phone": member.user.phone, "password": TEST_PASSWORD})
    assert login.json()["step"] == "totp_setup"


def test_no_reset_for_an_account_used_elsewhere(api, head, school, other_school):
    member = MembershipFactory(school=school, roles=["teacher"])
    MembershipFactory(user=member.user, school=other_school, roles=["cashier"])
    enable_totp(member.user)

    response = api(head).post(f"{URL}{member.id}/reset-totp/")

    assert response.json()["code"] == "account_used_elsewhere"
    member.user.refresh_from_db()
    assert member.user.totp_enabled


def test_change_names_and_phone(api, head, school):
    member = MembershipFactory(school=school, roles=["cashier"])

    response = api(head).patch(
        f"{URL}{member.id}/",
        {"last_name": " Kavira ", "middle_name": "", "first_name": "Jeanne", "phone": "0100090555"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["phone"] == "+243100090555"
    member.user.refresh_from_db()
    assert (member.user.last_name, member.user.first_name) == ("Kavira", "Jeanne")


def test_phone_already_used_by_another_account(api, head, school):
    member = MembershipFactory(school=school, roles=["cashier"])
    other = UserFactory()

    response = api(head).patch(f"{URL}{member.id}/", {"phone": other.phone})

    assert response.status_code == 409
    assert response.json()["code"] == "phone_taken"


def test_last_name_cannot_be_emptied(api, head, school):
    member = MembershipFactory(school=school, roles=["cashier"])

    response = api(head).patch(f"{URL}{member.id}/", {"last_name": ""})

    assert response.status_code == 400


def test_names_of_an_account_used_elsewhere_are_refused(api, head, school, other_school):
    member = MembershipFactory(school=school, roles=["teacher"], user__last_name="Kambale")
    MembershipFactory(user=member.user, school=other_school)

    response = api(head).patch(
        f"{URL}{member.id}/", {"last_name": "Autre", "roles": [role_id(school, "cashier")]}
    )

    assert response.json()["code"] == "account_used_elsewhere"
    member.user.refresh_from_db()
    assert member.user.last_name == "Kambale"
    # Tout est refusé : les rôles non plus ne changent pas.
    assert role_codes(member) == {"teacher"}


@pytest.mark.parametrize("action", ["new-password", "reset-totp"])
def test_account_actions_need_roles_manage(api, cashier, school, action):
    member = MembershipFactory(school=school, roles=["teacher"])

    response = api(cashier).post(f"{URL}{member.id}/{action}/")

    assert response.status_code == 403


@pytest.mark.parametrize("action", ["new-password", "reset-totp"])
def test_account_actions_on_another_school_are_not_found(
    api, other_head, school, other_school, action
):
    alpha_member = MembershipFactory(school=school, roles=["cashier"])
    enable_totp(alpha_member.user)

    response = api(other_head, host="beta.localhost").post(f"{URL}{alpha_member.id}/{action}/")

    assert response.status_code == 404
    alpha_member.user.refresh_from_db()
    assert alpha_member.user.check_password(TEST_PASSWORD)
    assert alpha_member.user.totp_enabled


def test_head_without_two_factor_session_is_refused(api, head, school):
    member = MembershipFactory(school=school, roles=["teacher"])

    response = api(head, mfa=False).post(f"{URL}{member.id}/new-password/")

    assert response.json()["code"] == "totp_required"

"""Administration Django : super-admin seulement ; rôles et appartenances de toutes les écoles en
lecture seule."""

import pytest
from django.test import Client

from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.core.tenancy import use_all_schools
from tests.factories import MembershipFactory, enable_totp

pytestmark = pytest.mark.django_db


def test_pages_open_for_the_platform_admin(admin_client, school, other_school):
    membership = MembershipFactory(school=school, roles=["head", "teacher"])
    with use_all_schools():
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


def test_support_resets_two_factor_authentication(admin_client, school, other_school):
    # Compte dans deux écoles : aucune ne peut le faire, le support oui.
    member = MembershipFactory(school=school, roles=["cashier"])
    MembershipFactory(user=member.user, school=other_school, roles=["teacher"])
    enable_totp(member.user)

    response = admin_client.post(
        "/admin/accounts/user/",
        {"action": "reset_totp", "_selected_action": [str(member.user.pk)]},
    )

    assert response.status_code == 302
    member.user.refresh_from_db()
    assert not member.user.totp_enabled
    # Noté dans le journal de chaque école de la personne, au nom du support.
    for each in (school, other_school):
        with use_all_schools():
            log = AuditLog.all_schools.get(school=each)
        assert log.action == "account.totp_reset"
        assert log.actor.is_platform_admin
        assert log.entity_label == str(member.user)


# Changements d'un compte par le support : journal de chaque école où la personne est active


@pytest.fixture
def member(school, other_school):
    """Compte actif dans alpha et beta, désactivé dans une troisième école."""
    membership = MembershipFactory(school=school, roles=["cashier"])
    MembershipFactory(user=membership.user, school=other_school, roles=["teacher"])
    MembershipFactory(user=membership.user, is_active=False)
    return membership.user


def change(admin_client, user, **fields):
    data = {
        "phone": user.phone,
        "last_name": user.last_name,
        "middle_name": user.middle_name,
        "first_name": user.first_name,
        "language": user.language,
        "is_active": "on" if user.is_active else "",
        "must_change_password": "",
        **fields,
    }
    return admin_client.post(f"/admin/accounts/user/{user.pk}/change/", data)


def entries(action) -> list[AuditLog]:
    with use_all_schools():
        return list(AuditLog.all_schools.filter(action=action).select_related("school"))


def test_support_changes_names_and_phone(admin_client, member, school, other_school):
    old_phone = member.phone

    response = change(admin_client, member, last_name="Kavira", phone="0000004001")

    assert response.status_code == 302, response.context["adminform"].form.errors
    logs = entries("account.changed")
    assert {log.school for log in logs} == {school, other_school}
    for log in logs:
        assert log.before == {"phone": old_phone, "last_name": member.last_name}
        assert log.after == {"phone": "+243000004001", "last_name": "Kavira"}
        assert log.actor.is_platform_admin


def test_nothing_changed_nothing_noted(admin_client, member):
    assert change(admin_client, member).status_code == 302

    with use_all_schools():
        assert not AuditLog.all_schools.exists()


def test_support_deactivates_then_reactivates_an_account(
    admin_client, member, school, other_school
):
    change(admin_client, member, is_active="")
    member.refresh_from_db()
    assert not member.is_active

    change(admin_client, member, is_active="on")

    assert {log.school for log in entries("account.deactivated")} == {school, other_school}
    assert {log.school for log in entries("account.reactivated")} == {school, other_school}


def test_support_gives_a_temporary_password(admin_client, member, school, other_school):
    page = f"/admin/accounts/user/{member.pk}/password/"
    # Afficher la page ne change rien.
    assert admin_client.get(page).status_code == 200
    with use_all_schools():
        assert not AuditLog.all_schools.exists()

    response = admin_client.post(page)

    password = response.context["temporary_password"]
    assert password in response.content.decode()
    member.refresh_from_db()
    assert member.check_password(password)
    assert not member.check_password("mot-de-passe-de-test")
    assert member.must_change_password
    assert {log.school for log in entries("account.password_reset")} == {school, other_school}
    with use_all_schools():
        assert not any("password" in (log.after or {}) for log in AuditLog.all_schools.all())

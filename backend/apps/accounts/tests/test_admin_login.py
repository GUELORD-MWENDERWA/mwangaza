"""Connexion à l'administration Django : super-admin seulement, toujours avec la double
authentification (même connexion en étapes que l'API)."""

import pytest
from django.test import Client

from apps.accounts.login import TOTP_SETUP_SESSION_KEY
from apps.accounts.models import LoginFailure, User
from apps.audit.models import AuditLog
from apps.core.crypto import decrypt
from tests.factories import MembershipFactory, enable_totp, totp_code

pytestmark = pytest.mark.django_db

LOGIN = "/admin/login/?next=/admin/accounts/user/"
PASSWORD = "secret-123"


@pytest.fixture
def client():
    return Client(HTTP_HOST="localhost")


@pytest.fixture
def secret(platform_admin):
    return enable_totp(platform_admin)


def log_in(client, phone="0000000000", password=PASSWORD):
    return client.post(LOGIN, {"phone": phone, "password": password})


def enter(client, code):
    return client.post(LOGIN, {"code": code})


def test_password_then_code(client, secret):
    response = log_in(client)
    assert response.status_code == 302
    # Pas encore d'accès : le code manque.
    assert client.get("/admin/").status_code == 302
    assert 'name="code"' in client.get(LOGIN).content.decode()

    response = enter(client, totp_code(secret))

    assert response.status_code == 302
    assert response["Location"] == "/admin/accounts/user/"
    assert client.get("/admin/").status_code == 200


def test_recovery_code_is_accepted(client, platform_admin):
    from apps.accounts import services

    enable_totp(platform_admin)
    [code, *_] = services._new_recovery_codes(platform_admin)
    log_in(client)

    assert enter(client, code).status_code == 302
    assert client.get("/admin/").status_code == 200


def test_wrong_code_is_refused_and_counted(client, secret):
    log_in(client)

    response = enter(client, "000000")

    assert response.status_code == 200
    assert "errornote" in response.content.decode()
    assert LoginFailure.objects.count() == 1
    assert client.get("/admin/").status_code == 302


def test_first_login_turns_two_factor_authentication_on(client, platform_admin):
    log_in(client)
    page = client.get(LOGIN).content.decode()
    assert 'name="code"' in page
    secret = decrypt(client.session[TOTP_SETUP_SESSION_KEY])
    assert " ".join(secret[i : i + 4] for i in range(0, len(secret), 4)) in page

    response = enter(client, totp_code(secret))

    # Codes de secours montrés une fois, sur cette page.
    assert response.status_code == 200
    assert response.context["recovery_codes"] and len(response.context["recovery_codes"]) == 8
    platform_admin.refresh_from_db()
    assert platform_admin.totp_enabled
    assert client.get("/admin/").status_code == 200


def test_temporary_password_is_replaced(client, platform_admin, secret):
    platform_admin.must_change_password = True
    platform_admin.save()
    log_in(client)
    enter(client, totp_code(secret))

    response = client.post(
        LOGIN,
        {"new_password1": "nouveau-mot-de-passe-7", "new_password2": "nouveau-mot-de-passe-7"},
    )

    assert response.status_code == 302
    platform_admin.refresh_from_db()
    assert not platform_admin.must_change_password
    assert platform_admin.check_password("nouveau-mot-de-passe-7")
    assert client.get("/admin/").status_code == 200


def test_wrong_password(client, secret):
    response = log_in(client, password="pas-le-bon")

    assert response.status_code == 200
    assert "pas un compte d&#x27;administration Mwangaza" in response.content.decode()
    assert LoginFailure.objects.count() == 1


def test_staff_of_a_school_is_refused_like_a_wrong_password(client, school):
    head = MembershipFactory(school=school, roles=["head"]).user

    response = log_in(client, phone=head.phone, password="mot-de-passe-de-test")

    assert response.status_code == 200
    assert "pas un compte d&#x27;administration Mwangaza" in response.content.decode()
    assert "_auth_user_id" not in client.session
    assert client.get(LOGIN).context["form"].fields.keys() == {"phone", "password"}
    assert not AuditLog.all_schools.exists()


def test_locked_after_five_failures(client, secret):
    for _ in range(5):
        log_in(client, password="pas-le-bon")

    response = log_in(client)

    assert response.status_code == 200
    assert "errornote" in response.content.decode()
    assert client.get("/admin/").status_code == 302


def test_a_session_without_two_factor_authentication_is_not_enough(client, platform_admin):
    client.force_login(platform_admin)

    response = client.get("/admin/accounts/user/")

    assert response.status_code == 302
    assert response["Location"].startswith("/admin/login/")
    # La page de connexion recommence au mot de passe.
    assert client.get(LOGIN).context["form"].fields.keys() == {"phone", "password"}


def test_staff_of_a_school_never_enters(client, school):
    head = MembershipFactory(school=school, roles=["head"]).user
    client.force_login(head)
    session = client.session
    session["accounts.mfa"] = True
    session.save()

    response = client.get("/admin/accounts/user/")

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_logged_in_admin_goes_straight_in(admin_client):
    response = admin_client.get(LOGIN)

    assert response.status_code == 302
    assert response["Location"] == "/admin/accounts/user/"


def test_next_must_stay_on_the_site(client, secret):
    client.post(
        "/admin/login/?next=https://pirate.example/", {"phone": "0000000000", "password": PASSWORD}
    )

    response = client.post(
        "/admin/login/?next=https://pirate.example/", {"code": totp_code(secret)}
    )

    assert response["Location"] == "/admin/"


def test_trusted_device_does_not_skip_the_code(client, secret, platform_admin):
    from apps.accounts import login

    class Response(dict):
        def set_cookie(self, name, value, **kwargs):
            self[name] = value

    cookie = Response()
    login.trust_device(cookie, platform_admin)
    client.cookies[login.TRUSTED_DEVICE_COOKIE] = cookie[login.TRUSTED_DEVICE_COOKIE]

    log_in(client)

    assert client.get("/admin/").status_code == 302
    assert 'name="code"' in client.get(LOGIN).content.decode()


def test_platform_admin_must_use_two_factor_authentication(platform_admin):
    from apps.accounts import services

    assert services.totp_required(platform_admin)
    assert User.objects.get(pk=platform_admin.pk).is_platform_admin

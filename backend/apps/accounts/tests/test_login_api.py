"""Connexion en plusieurs étapes (B4) : `/api/auth/login/`, `…/login/totp/`, `…/password/`,
`…/totp/setup/`, `…/totp/activate/`, `…/logout/`."""

import time

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client, override_settings

from apps.accounts import attempts, services
from apps.accounts.login import PENDING_SESSION_KEY, TRUSTED_DEVICE_COOKIE
from apps.accounts.models import Membership, RecoveryCode, Role
from apps.core.crypto import decrypt
from apps.core.tenancy import use_school
from tests.factories import TEST_PASSWORD, MembershipFactory, enable_totp, totp_code

pytestmark = pytest.mark.django_db

LOGIN = "/api/auth/login/"
CODE = "/api/auth/login/totp/"
PASSWORD = "/api/auth/password/"
SETUP = "/api/auth/totp/setup/"
ACTIVATE = "/api/auth/totp/activate/"
LOGOUT = "/api/auth/logout/"
ME = "/api/me/"
ROLES = "/api/roles/"
NEW_PASSWORD = "nouveau-mot-de-passe-2026"


def log_in(api, user, password=TEST_PASSWORD, phone=None):
    return api.post(LOGIN, {"phone": phone or user.phone, "password": password})


def step(response) -> str:
    assert response.status_code == 200, response.content
    return response.json()["step"]


def logged_in(api) -> bool:
    return api.get(ME).status_code == 200


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


# Étape 1 : numéro et mot de passe


def test_login_without_second_factor(api, teacher):
    client = api()

    assert step(log_in(client, teacher)) == "done"

    assert logged_in(client)
    teacher.refresh_from_db()
    assert teacher.last_login is not None
    membership = Membership.objects.get(user=teacher)
    assert membership.last_login_at is not None


def test_national_form_of_the_number(api, teacher):
    local = "0" + teacher.phone.removeprefix("+243")

    assert step(log_in(api(), teacher, phone=local)) == "done"


def test_refused_login_always_gets_the_same_answer(api, teacher, other_school):
    # Mauvais mot de passe, numéro inconnu, compte désactivé : on ne devine pas qui a un compte.
    inactive = MembershipFactory(school=other_school, user__is_active=False).user
    tries = [
        (teacher.phone, "pas-le-bon"),
        ("0000099999", TEST_PASSWORD),
        (inactive.phone, TEST_PASSWORD),
    ]
    answers = []
    for phone, password in tries:
        client = api()
        response = client.post(LOGIN, {"phone": phone, "password": password})
        assert response.status_code == 400
        assert not logged_in(client)
        answers.append(response.json())

    assert answers[0]["code"] == "invalid_credentials"
    assert answers[0] == answers[1] == answers[2]


def test_five_failures_lock_the_number(api, teacher):
    client = api()
    for _ in range(5):
        assert log_in(client, teacher, password="pas-le-bon").status_code == 400

    response = log_in(client, teacher)

    assert response.status_code == 429
    assert response.json()["code"] == "too_many_attempts"
    assert 14 * 60 < int(response["Retry-After"]) <= 15 * 60 + 1
    assert not logged_in(client)


@override_settings(CLIENT_IP_HEADER="HTTP_X_REAL_IP")
def test_behind_the_proxy_an_address_lock_stops_only_that_visitor(teacher):
    # En production, tout arrive de Caddy (même REMOTE_ADDR) ; le visiteur est dans X-Real-IP.
    for number in range(30):
        attempts.record_failure(f"+2430000{number:05d}", "41.243.12.7")

    def log_in_from(ip):
        client = Client(HTTP_HOST="alpha.localhost", HTTP_X_REAL_IP=ip)
        data = {"phone": teacher.phone, "password": TEST_PASSWORD}
        return client.post(LOGIN, data, content_type="application/json")

    assert log_in_from("41.243.12.7").status_code == 429
    assert log_in_from("197.157.1.20").status_code == 200


def test_unknown_number_is_locked_the_same_way(api, school):
    client = api()
    for _ in range(5):
        client.post(LOGIN, {"phone": "0000099999", "password": "essai"})

    response = client.post(LOGIN, {"phone": "+243000099999", "password": "essai"})

    assert response.status_code == 429


def test_login_forgets_the_failures(api, teacher):
    client = api()
    for _ in range(4):
        log_in(client, teacher, password="pas-le-bon")
    step(log_in(client, teacher))
    for _ in range(4):
        log_in(api(), teacher, password="pas-le-bon")

    assert step(log_in(api(), teacher)) == "done"


def test_login_needs_the_csrf_token(school, teacher):
    client = Client(enforce_csrf_checks=True, HTTP_HOST="alpha.localhost")
    data = {"phone": teacher.phone, "password": TEST_PASSWORD}

    refused = client.post(LOGIN, data, content_type="application/json")
    assert refused.status_code == 403
    assert refused.json()["code"] == "permission_denied"

    assert client.get("/api/auth/csrf/").status_code == 204
    token = client.cookies["csrftoken"].value
    accepted = client.post(LOGIN, data, content_type="application/json", HTTP_X_CSRFTOKEN=token)
    assert accepted.json()["step"] == "done"


def test_account_without_access_to_this_school_can_log_in(api, school, other_school):
    # Choix de l'école (M2) : le compte est valable, l'école de l'adresse ne lui donne rien.
    user = MembershipFactory(school=other_school, roles=["teacher"]).user
    client = api()

    assert step(log_in(client, user)) == "done"

    data = client.get(ME).json()
    assert data["school"] is None
    assert [s["code"] for s in data["schools"]] == ["beta"]
    assert Membership.objects.get(user=user).last_login_at is None


def test_current_step_after_a_reload(api, head):
    enable_totp(head)
    client = api()
    assert step(client.get(LOGIN)) == "password"

    log_in(client, head)
    assert step(client.get(LOGIN)) == "totp"


def test_logout(api, teacher):
    client = api()
    step(log_in(client, teacher))

    assert client.post(LOGOUT).status_code == 204
    assert not logged_in(client)


def test_new_login_replaces_the_previous_account(api, teacher, cashier):
    client = api()
    step(log_in(client, teacher))
    enable_totp(cashier)

    assert step(log_in(client, cashier)) == "totp"
    assert not logged_in(client)


# Étape `totp`


def test_code_is_asked_when_two_factor_is_on(api, head):
    secret = enable_totp(head)
    client = api()

    assert step(log_in(client, head)) == "totp"
    # Mot de passe seul : rien n'est ouvert.
    assert not logged_in(client)
    assert client.get(ROLES).status_code == 403

    wrong = client.post(CODE, {"code": "000000" if totp_code(secret) != "000000" else "111111"})
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "invalid_code"

    assert step(client.post(CODE, {"code": totp_code(secret)})) == "done"
    assert client.get(ROLES).status_code == 200


def test_a_code_cannot_be_used_twice(api, head):
    secret = enable_totp(head)
    code = totp_code(secret)
    first = api()
    log_in(first, head)
    step(first.post(CODE, {"code": code}))

    second = api()
    log_in(second, head)
    response = second.post(CODE, {"code": code})

    assert response.json()["code"] == "invalid_code"


def test_recovery_code_works_once(api, head):
    codes = services.enable_totp(head, secret := enable_totp(head), totp_code(secret))
    client = api()
    log_in(client, head)

    assert step(client.post(CODE, {"code": codes[0].lower()})) == "done"
    assert client.get(ME).json()["recovery_codes_left"] == 7

    again = api()
    log_in(again, head)
    assert again.post(CODE, {"code": codes[0]}).json()["code"] == "invalid_code"


def test_wrong_codes_count_as_failed_attempts(api, head):
    secret = enable_totp(head)
    client = api()
    log_in(client, head)
    bad = "123456" if totp_code(secret) != "123456" else "654321"
    for _ in range(5):
        client.post(CODE, {"code": bad})

    response = client.post(CODE, {"code": totp_code(secret)})

    assert response.status_code == 429
    assert log_in(api(), head).status_code == 429


def test_code_step_needs_a_login_in_progress(api, school):
    response = api().post(CODE, {"code": "123456"})

    assert response.status_code == 403
    assert response.json()["code"] == "not_authenticated"


def test_login_in_progress_expires_after_10_minutes(api, head):
    secret = enable_totp(head)
    client = api()
    log_in(client, head)
    session = client.client.session
    session[PENDING_SESSION_KEY] = {**session[PENDING_SESSION_KEY], "started": time.time() - 601}
    session.save()

    response = client.post(CODE, {"code": totp_code(secret)})

    assert response.status_code == 409
    assert response.json()["code"] == "login_expired"
    assert step(client.get(LOGIN)) == "password"


def test_trusted_device_skips_the_code_for_7_days(api, head):
    secret = enable_totp(head)
    client = api()
    log_in(client, head)
    response = client.post(CODE, {"code": totp_code(secret), "trust_device": True})
    cookie = response.cookies[TRUSTED_DEVICE_COOKIE]
    assert cookie["httponly"]
    assert cookie["max-age"] == 7 * 24 * 3600
    client.post(LOGOUT)

    assert step(log_in(client, head)) == "done"
    # La session vaut double authentification : accès aux droits sensibles.
    assert client.get(ROLES).status_code == 200


def test_trust_is_for_one_account_and_ends_with_a_new_password(api, head, cashier):
    secret = enable_totp(head)
    enable_totp(cashier)
    client = api()
    log_in(client, head)
    client.post(CODE, {"code": totp_code(secret), "trust_device": True})

    assert step(log_in(client, cashier)) == "totp"

    head.set_password(NEW_PASSWORD)
    head.save()
    assert step(log_in(client, head, password=NEW_PASSWORD)) == "totp"


def test_no_trust_without_asking(api, head):
    secret = enable_totp(head)
    client = api()
    log_in(client, head)
    response = client.post(CODE, {"code": totp_code(secret)})

    assert TRUSTED_DEVICE_COOKIE not in response.cookies


# Étape `new_password`


def test_temporary_password_must_be_replaced(api, school):
    user = MembershipFactory(school=school, roles=["teacher"], user__must_change_password=True).user
    client = api()

    assert step(log_in(client, user)) == "new_password"
    assert not logged_in(client)

    too_short = client.post(PASSWORD, {"new_password": "court"})
    assert too_short.status_code == 400
    [error] = too_short.json()["fields"]["new_password"]
    assert error["code"] == "password_too_short"
    same = client.post(PASSWORD, {"new_password": TEST_PASSWORD})
    assert same.status_code == 400

    assert step(client.post(PASSWORD, {"new_password": NEW_PASSWORD})) == "done"
    assert logged_in(client)
    user.refresh_from_db()
    assert user.must_change_password is False
    assert user.check_password(NEW_PASSWORD)


def test_password_close_to_the_account_is_refused(api, school):
    user = MembershipFactory(
        school=school,
        roles=["teacher"],
        user__must_change_password=True,
        user__last_name="Kambalemuhindo",
    ).user
    client = api()
    log_in(client, user)

    response = client.post(PASSWORD, {"new_password": "kambalemuhindo"})

    assert response.status_code == 400


def test_code_comes_before_the_new_password(api, head):
    # Un mot de passe provisoire ne suffit pas à prendre un compte protégé.
    secret = enable_totp(head)
    head.must_change_password = True
    head.save()
    client = api()

    assert step(log_in(client, head)) == "totp"
    early = client.post(PASSWORD, {"new_password": NEW_PASSWORD})
    assert early.status_code == 409
    assert early.json()["code"] == "wrong_step"

    assert step(client.post(CODE, {"code": totp_code(secret)})) == "new_password"
    assert step(client.post(PASSWORD, {"new_password": NEW_PASSWORD})) == "done"
    assert client.get(ROLES).status_code == 200


# Étape `totp_setup` (M1)


@pytest.mark.parametrize("role", ["head", "accountant", "cashier", "promoter"])
def test_roles_that_require_two_factor_must_turn_it_on(api, school, role):
    user = MembershipFactory(school=school, roles=[role]).user
    client = api()

    assert step(log_in(client, user)) == "totp_setup"
    assert not logged_in(client)

    key = client.post(SETUP).json()
    assert key["otpauth_uri"].startswith("otpauth://totp/Mwangaza:")
    user.refresh_from_db()
    assert user.totp_secret == ""

    response = client.post(ACTIVATE, {"code": totp_code(key["secret"])})
    assert step(response) == "done"
    assert len(response.json()["recovery_codes"]) == 8
    user.refresh_from_db()
    assert user.totp_enabled
    assert decrypt(user.totp_secret) == key["secret"]
    assert RecoveryCode.objects.filter(user=user).count() == 8
    me = client.get(ME).json()
    assert (me["totp_enabled"], me["recovery_codes_left"]) == (True, 8)


def test_head_reaches_their_rights_after_turning_it_on(api, head):
    client = api()
    log_in(client, head)
    secret = client.post(SETUP).json()["secret"]
    step(client.post(ACTIVATE, {"code": totp_code(secret)}))

    assert client.get(ROLES).status_code == 200


def test_activation_needs_a_valid_code_and_a_key(api, cashier):
    client = api()
    log_in(client, cashier)

    missing = client.post(ACTIVATE, {"code": "123456"})
    assert missing.json()["code"] == "totp_setup_not_started"

    secret = client.post(SETUP).json()["secret"]
    wrong = client.post(ACTIVATE, {"code": "000000" if totp_code(secret) != "000000" else "1"})
    assert wrong.json()["code"] == "invalid_code"
    cashier.refresh_from_db()
    assert not cashier.totp_enabled


def test_new_cashier_changes_password_then_turns_it_on(api, school):
    user = MembershipFactory(school=school, roles=["cashier"], user__must_change_password=True).user
    client = api()

    assert step(log_in(client, user)) == "new_password"
    assert step(client.post(PASSWORD, {"new_password": NEW_PASSWORD})) == "totp_setup"
    secret = client.post(SETUP).json()["secret"]
    assert step(client.post(ACTIVATE, {"code": totp_code(secret)})) == "done"


def test_teacher_is_not_asked(api, teacher):
    assert step(log_in(api(), teacher)) == "done"


# Hachage des mots de passe


@override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.Argon2PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]
)
def test_old_password_is_converted_to_argon2_at_login(api, teacher):
    teacher.password = make_password(TEST_PASSWORD, hasher="pbkdf2_sha256")
    teacher.save()

    step(log_in(api(), teacher))

    teacher.refresh_from_db()
    assert teacher.password.startswith("argon2")


def test_session_without_second_factor_is_stopped_after_a_promotion(api, school, teacher):
    # Connecté sans double authentification (enseignant), puis nommé directeur : refusé jusqu'à
    # une nouvelle connexion, qui lui fera activer la double authentification.
    client = api()
    step(log_in(client, teacher))
    with use_school(school):
        Membership.objects.get(user=teacher).roles.add(Role.objects.get(code="head"))

    assert client.get(ROLES).json()["code"] == "totp_required"
    assert step(log_in(client, teacher)) == "totp_setup"

"""Mon compte (M4) : la personne change son mot de passe et gère sa double authentification."""

import pytest

from apps.accounts import services
from apps.accounts.models import RecoveryCode
from apps.core.crypto import decrypt
from tests.factories import TEST_PASSWORD, MembershipFactory, enable_totp, totp_code

pytestmark = pytest.mark.django_db

PASSWORD = "/api/auth/password/"
SETUP = "/api/auth/totp/setup/"
ACTIVATE = "/api/auth/totp/activate/"
RECOVERY = "/api/auth/totp/recovery-codes/"
DISABLE = "/api/auth/totp/disable/"
ME = "/api/me/"
NEW_PASSWORD = "nouveau-mot-de-passe-2026"


def wrong_code(secret: str) -> str:
    return "000000" if totp_code(secret) != "000000" else "111111"


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


# Mot de passe


def test_change_password(api, teacher):
    client = api(teacher)

    response = client.post(
        PASSWORD, {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}
    )

    assert response.json() == {"step": "done"}
    teacher.refresh_from_db()
    assert teacher.check_password(NEW_PASSWORD)
    # Cette session reste ouverte.
    assert client.get(ME).status_code == 200


def test_other_sessions_are_logged_out(api, teacher):
    phone, computer = api(teacher), api(teacher)

    computer.post(PASSWORD, {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD})

    assert phone.get(ME).json()["code"] == "not_authenticated"


def test_current_password_is_required(api, teacher):
    client = api(teacher)

    missing = client.post(PASSWORD, {"new_password": NEW_PASSWORD})
    wrong = client.post(PASSWORD, {"current_password": "pas-le-bon", "new_password": NEW_PASSWORD})

    assert missing.status_code == 400
    assert "current_password" in missing.json()
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "wrong_password"
    teacher.refresh_from_db()
    assert teacher.check_password(TEST_PASSWORD)


def test_wrong_current_passwords_count_as_failed_attempts(api, teacher):
    client = api(teacher)
    for _ in range(5):
        client.post(PASSWORD, {"current_password": "pas-le-bon", "new_password": NEW_PASSWORD})

    response = client.post(
        PASSWORD, {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 429


def test_anonymous_cannot_change_a_password(api, school):
    response = api().post(PASSWORD, {"new_password": NEW_PASSWORD})

    assert response.json()["code"] == "not_authenticated"


# Double authentification


def test_teacher_can_turn_it_on(api, teacher):
    client = api(teacher, mfa=False)

    secret = client.post(SETUP).json()["secret"]
    response = client.post(ACTIVATE, {"code": totp_code(secret)})

    assert response.json()["step"] == "done"
    assert len(response.json()["recovery_codes"]) == 8
    teacher.refresh_from_db()
    assert teacher.totp_enabled


def test_new_phone_needs_the_current_code(api, head):
    # « Changer de téléphone » (M4).
    old_secret = enable_totp(head)
    client = api(head)

    missing = client.post(SETUP)
    assert missing.status_code == 400
    assert "code" in missing.json()
    assert client.post(SETUP, {"code": wrong_code(old_secret)}).json()["code"] == "invalid_code"

    new_secret = client.post(SETUP, {"code": totp_code(old_secret)}).json()["secret"]
    step = client.post(ACTIVATE, {"code": totp_code(new_secret)}).json()["step"]

    assert step == "done"
    head.refresh_from_db()
    assert decrypt(head.totp_secret) == new_secret
    with pytest.raises(services.BusinessError):
        services.verify_second_factor(head, totp_code(old_secret, shift=1))


def test_new_recovery_codes(api, head):
    secret = enable_totp(head)
    old_codes = services.enable_totp(head, secret, totp_code(secret))
    client = api(head)

    refused = client.post(RECOVERY, {"code": wrong_code(secret)})
    response = client.post(RECOVERY, {"code": old_codes[0]})

    assert refused.json()["code"] == "invalid_code"
    new_codes = response.json()["recovery_codes"]
    assert len(new_codes) == 8
    assert not set(new_codes) & set(old_codes)
    assert RecoveryCode.objects.filter(user=head).count() == 8
    with pytest.raises(services.BusinessError):
        services.verify_second_factor(head, old_codes[1])
    services.verify_second_factor(head, new_codes[0])


def test_cannot_turn_it_off_when_a_role_requires_it(api, head):
    secret = enable_totp(head)

    response = api(head).post(DISABLE, {"code": totp_code(secret)})

    assert response.status_code == 409
    assert response.json()["code"] == "totp_still_required"
    head.refresh_from_db()
    assert head.totp_enabled


def test_teacher_can_turn_it_off(api, teacher):
    secret = enable_totp(teacher)
    client = api(teacher)

    assert client.post(DISABLE, {"code": wrong_code(secret)}).json()["code"] == "invalid_code"
    assert client.post(DISABLE, {"code": totp_code(secret)}).status_code == 204

    teacher.refresh_from_db()
    assert (teacher.totp_enabled, teacher.totp_secret) == (False, "")
    assert client.get(ME).json()["totp_enabled"] is False


@pytest.mark.parametrize("path", [RECOVERY, DISABLE])
def test_anonymous_is_refused(api, school, path):
    response = api().post(path, {"code": "123456"})

    assert response.json()["code"] == "not_authenticated"


def test_setup_needs_an_account(api, school):
    assert api().post(SETUP).json()["code"] == "not_authenticated"

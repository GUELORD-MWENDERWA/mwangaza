"""Compte super-admin (S.3.1) : chaque connexion et chaque refus au journal de la plateforme,
session fermée après 2 heures sans activité, adresses autorisées (`DJANGO_CONSOLE_ALLOWED_IPS`)."""

import pytest
from django.conf import settings
from django.test import override_settings

from apps.accounts import privileged
from apps.audit.models import PlatformAuditLog
from tests.factories import TEST_PASSWORD, MembershipFactory, enable_totp, totp_code

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
LOGIN = "/api/auth/login/"
CODE = "/api/auth/login/totp/"
ME = "/api/me/"
SEEN = privileged.SEEN_SESSION_KEY


def log_in(api, user, password=TEST_PASSWORD):
    return api.post(LOGIN, {"phone": user.phone, "password": password})


def journal() -> list[tuple]:
    logs = PlatformAuditLog.objects.order_by("created_at", "id")
    return list(logs.values_list("action", "entity_label", "after"))


def test_logins_and_refused_codes_of_the_platform_admin_are_in_the_platform_journal(
    api, platform_admin, school
):
    secret = enable_totp(platform_admin)
    console = api(host=CONSOLE)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user

    assert log_in(console, platform_admin, "secret-123").json()["step"] == "totp"
    wrong = "000000" if totp_code(secret) != "000000" else "111111"
    assert console.post(CODE, {"code": wrong}).json()["code"] == "invalid_code"
    assert console.post(CODE, {"code": totp_code(secret)}).json()["step"] == "done"
    # Le personnel d'une école n'y écrit rien : sa connexion est dans le journal de son école.
    assert log_in(api(), teacher).json()["step"] == "done"

    label = f"{platform_admin} · 127.0.0.1 · {CONSOLE}"
    assert journal() == [
        ("access.code_refused", label, None),
        ("access.login", label, {"second_factor": "totp"}),
    ]
    assert console.client.session.get_expiry_age() == privileged.IDLE_SECONDS


def test_the_platform_admin_session_is_short_and_rewritten_at_most_every_five_minutes(
    api, platform_admin, cashier
):
    console = api(platform_admin, host=CONSOLE)
    session = console.client.session
    first = session[SEEN]

    console.get(ME)
    assert console.client.session[SEEN] == first
    # Six minutes plus tard : les 2 heures repartent.
    session[SEEN] = first - 6 * 60
    session.save()
    console.get(ME)
    assert console.client.session[SEEN] >= first
    # Session ouverte avant ce réglage (deux semaines) : raccourcie à la première requête.
    del session[SEEN]
    session.set_expiry(None)
    session.save()
    console.get(ME)
    assert console.client.session.get_expiry_age() == privileged.IDLE_SECONDS

    # Le personnel d'une école garde sa session ordinaire.
    staff = api(cashier)
    assert staff.get(ME).status_code == 200
    assert SEEN not in staff.client.session
    assert staff.client.session.get_expiry_age() == settings.SESSION_COOKIE_AGE


def test_the_platform_admin_is_refused_outside_the_allowed_addresses(api, platform_admin, head):
    enable_totp(platform_admin)
    console = api(platform_admin, host=CONSOLE)

    with override_settings(CONSOLE_ALLOWED_IPS=["203.0.113.7", "10.8.0.0/24"]):
        # Session déjà ouverte, utilisée d'ailleurs (127.0.0.1 dans les tests) : notée une fois.
        for _ in range(2):
            response = console.get(ME)
            assert (response.status_code, response.json()["code"]) == (403, "address_not_allowed")
        # Bon mot de passe, mauvaise adresse : la réponse d'un mauvais mot de passe.
        refused = log_in(api(host=CONSOLE), platform_admin, "secret-123")
        assert (refused.status_code, refused.json()["code"]) == (400, "invalid_credentials")
        # Le personnel d'une école n'est pas concerné.
        assert api(head).get(ME).status_code == 200
    # Une entrée mal écrite n'autorise personne.
    with override_settings(CONSOLE_ALLOWED_IPS=["127.0.0.1x"]):
        assert console.get(ME).status_code == 403
    with override_settings(CONSOLE_ALLOWED_IPS=["127.0.0.0/8"]):
        assert log_in(api(host=CONSOLE), platform_admin, "secret-123").json()["step"] == "totp"

    assert [action for action, _label, _after in journal()] == ["access.address_refused"] * 2

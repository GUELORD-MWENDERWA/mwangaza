"""Console de la plateforme (5.2.1) : réservée au super-admin, à son adresse (`admin.<domaine>`),
après la double authentification ; connexion refusée à tout autre compte ; tableau de bord de
toutes les écoles (paiements annulés exclus, devises jamais additionnées) et santé du serveur."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.login import TRUSTED_DEVICE_COOKIE
from apps.core import health
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.schools.models import School
from tests.factories import TEST_PASSWORD, MembershipFactory, enable_totp, totp_code

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
DASHBOARD = "/api/console/dashboard/"


def test_console_is_only_for_the_platform_admin_after_two_factor_at_its_address(
    api, platform_admin, head
):
    assert api(None, host=CONSOLE).get(DASHBOARD).status_code == 403
    assert api(head, host=CONSOLE).get(DASHBOARD).status_code == 403
    assert api(platform_admin, host=CONSOLE, mfa=False).get(DASHBOARD).status_code == 403
    # Ailleurs qu'à l'adresse de la console, ce point d'API n'existe pas.
    for host in ("alpha.localhost", "parents.localhost", "localhost"):
        assert api(platform_admin, host=host).get(DASHBOARD).status_code == 404
    assert api(platform_admin, host=CONSOLE).get(DASHBOARD).status_code == 200


def test_dashboard_counts_every_school_and_today_payments_by_currency(
    api, platform_admin, school, other_school, head, cashier, other_head, monkeypatch
):
    # Redis et le disque de la machine de test ne comptent pas (CI : disque presque plein).
    monkeypatch.setattr(health, "_redis_latency", lambda: 1)
    monkeypatch.setattr(health, "_disk_free_percent", lambda: 50)
    alpha = school_with_fees(school, head)
    beta = school_with_fees(other_school, other_head)
    beta_cashier = MembershipFactory(school=other_school, roles=["cashier"]).user
    pay(school, cashier, alpha["enrollment"], 12000, "USD")
    pay(school, cashier, alpha["enrollment"], 10000, "CDF")
    cancelled = pay(school, cashier, alpha["enrollment"], 9000, "USD")
    with use_school(school):
        request, _created = services.request_cancellation(
            cancelled, actor=cashier, reason="Montant saisi deux fois"
        )
        services.approve_cancellation(request, actor=head)
    pay(other_school, beta_cashier, beta["enrollment"], 5000, "USD")
    other_school.status = School.Status.TRIAL
    other_school.trial_ends_on = timezone.localdate() + timedelta(days=10)
    other_school.save()

    data = api(platform_admin, host=CONSOLE).get(DASHBOARD).json()

    assert data["schools"] == {"active": 1, "trial": 1, "suspended": 0, "trial_ending": 1}
    assert data["students"] == 2
    assert [(r["currency"], r["amount_minor"], r["count"]) for r in data["today"]] == [
        ("USD", 17000, 2),
        ("CDF", 10000, 1),
    ]
    assert [(s["code"], s["payments"]) for s in data["active_schools"]] == [
        (school.code, 2),
        (other_school.code, 1),
    ]
    assert data["active_schools"][0]["today"] == [
        {"currency": "USD", "amount_minor": 12000},
        {"currency": "CDF", "amount_minor": 10000},
    ]
    assert data["health"]["status"] == "ok"


def test_console_login_refuses_other_accounts_and_always_asks_the_code(api, platform_admin):
    secret = enable_totp(platform_admin)
    accountant = MembershipFactory(roles=["accountant"]).user
    enable_totp(accountant)
    console = api(None, host=CONSOLE)
    console.get("/api/auth/csrf/")

    refused = console.post(
        "/api/auth/login/", {"phone": accountant.phone, "password": TEST_PASSWORD}
    )
    assert refused.json()["code"] == "invalid_credentials"

    login = {"phone": platform_admin.phone, "password": "secret-123"}
    assert console.post("/api/auth/login/", login).json()["step"] == "totp"
    done = console.post("/api/auth/login/totp/", {"code": totp_code(secret), "trust_device": True})
    assert done.json()["step"] == "done"
    # Jamais d'appareil de confiance pour le super-admin : le code est demandé à chaque fois.
    assert TRUSTED_DEVICE_COOKIE not in done.cookies
    assert console.get(DASHBOARD).status_code == 200


def test_health_reports_a_broken_redis(monkeypatch):
    def refused():
        raise ConnectionError

    monkeypatch.setattr(health, "_redis_latency", refused)
    report = health.report()

    assert report["status"] == "error"
    assert {c["name"]: c["status"] for c in report["checks"]}["redis"] == "error"

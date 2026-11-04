"""Détection (S.8) : rafale de connexions ratées, export inhabituel, annulations hors norme,
appareil déconnecté qui insiste. Une alerte par sujet et par jour, au journal de la plateforme
(fictive ou réelle selon le sujet) et sur l'écran de l'équipe ; carte « Sécurité » du tableau de
bord selon le mode et le droit journal."""

from datetime import timedelta
from unittest import mock

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts import attempts
from apps.audit import security
from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.sync.models import Device
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
DASHBOARD = "/api/console/dashboard/"


@pytest.fixture(autouse=True)
def _fresh_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def pushed():
    with mock.patch("apps.notifications.console.alert") as alert:
        yield alert


def alerts(action: str):
    return PlatformAuditLog.objects.filter(action=action)


def test_failed_login_bursts_alert_once_per_address_number_and_platform(monkeypatch, pushed):
    monkeypatch.setattr(security, "LOGIN_PLATFORM_FAILURES", 50)
    burst = alerts(PlatformAction.SECURITY_LOGIN_BURST)
    # Une adresse essaie 31 numéros : bloquée au 30e, une seule alerte.
    for i in range(31):
        attempts.record_failure(f"+24397000{i:04d}", "198.51.100.7")
    assert list(burst.values_list("entity_label", "after__scope", "is_demo")) == [
        ("198.51.100.7", "ip", False)
    ]
    # Un numéro fictif visé depuis 20 adresses : alerte fictive ; la 50e erreur de la plateforme
    # donne l'alerte d'ensemble.
    for i in range(20):
        attempts.record_failure("+243000000777", f"203.0.113.{i}")
    assert sorted(burst.values_list("after__scope", "is_demo")) == [
        ("ip", False),
        ("phone", True),
        ("platform", False),
    ]
    assert burst.get(after__scope="phone").after["failures"] == 20
    assert pushed.call_count == 3


def test_unusual_exports_count_per_school_and_account(
    monkeypatch, api, school, head, other_head, cashier, pushed
):
    monkeypatch.setattr(security, "EXPORTS_PER_HOUR", 3)
    export = "/api/audit/export/?since=2026-10-01&until=2026-10-31"
    for _ in range(2):
        assert api(head).get(export).status_code == 200
        assert api(other_head, host="beta.localhost").get(export).status_code == 200
    unusual = alerts(PlatformAction.SECURITY_UNUSUAL_EXPORT)
    # Deux exports chacun, dans deux écoles : rien n'est additionné entre elles.
    assert not unusual.exists()
    api(head).get(export)
    api(head).get(export)
    alert = unusual.get()
    assert (alert.entity_id, alert.after["exports"]) == (str(school.pk), 3)
    assert head.get_full_name() in alert.entity_label
    # Un seul gros fichier suffit aussi.
    with use_school(school):
        security.exported(cashier, security.EXPORT_ROWS_PER_HOUR)
    assert unusual.count() == 2 and pushed.call_count == 2


def test_cancellations_alert_above_the_school_norm(monkeypatch, school, head, cashier):
    monkeypatch.setattr(security, "CANCELLATIONS_MIN", 2)
    # 1 annulation sur les 30 derniers jours, seuil * 60 : 3 aujourd'hui dépassent la norme
    # (3 * 30 > 60 * 1), 2 non.
    monkeypatch.setattr(security, "CANCELLATIONS_FACTOR", 60)
    fees = school_with_fees(school, head)

    def cancel():
        payment = pay(school, cashier, fees["enrollment"], 1000, "USD")
        with use_school(school):
            asked, _ = finance.request_cancellation(payment, actor=cashier, reason="Erreur d'élève")
            finance.approve_cancellation(asked, actor=head)

    with mock.patch("django.utils.timezone.now", return_value=timezone.now() - timedelta(days=7)):
        cancel()
    cancel()
    cancel()
    unusual = alerts(PlatformAction.SECURITY_CANCELLATIONS)
    assert not unusual.exists()
    cancel()
    cancel()
    alert = unusual.get()
    assert (alert.entity_id, alert.after) == (str(school.pk), {"today": 3, "previous_30_days": 1})


def test_a_disconnected_device_that_keeps_trying(api, school, head, pushed):
    with use_school(school):
        device = Device.objects.create(user=head, label="PC", prefix="P1", public_key="x")
        device.revoked_at = timezone.now()
        device.save(update_fields=["revoked_at"])
    client = api(head)
    for _ in range(security.REVOKED_CONTACTS + 2):
        assert client.post(f"/api/me/devices/{device.pk}/resume/").status_code == 409
    alert = alerts(PlatformAction.SECURITY_REVOKED_DEVICE).get()
    assert (alert.entity_id, alert.is_demo) == (str(device.pk), False)
    assert alert.after["attempts"] == security.REVOKED_CONTACTS


def test_the_security_card_follows_the_mode_and_the_journal_right(api, platform_admin):
    audit.record_platform(
        PlatformAction.SECURITY_LOGIN_BURST, actor=None, label="198.51.100.7", demo=False
    )
    audit.record_platform(
        PlatformAction.SECURITY_LOGIN_BURST, actor=None, label="+243000000777", demo=True
    )
    with mock.patch("django.utils.timezone.now", return_value=timezone.now() - timedelta(days=8)):
        audit.record_platform(PlatformAction.SECURITY_LOGIN_BURST, actor=None, label="ancienne")

    def card(mode="live", user=platform_admin):
        client = api(user, host=CONSOLE).client
        response = client.get(DASHBOARD, HTTP_HOST=CONSOLE, HTTP_X_CONSOLE_MODE=mode)
        return response.json()["security"]

    live = card()
    assert (live["count"], [a["entity_label"] for a in live["alerts"]]) == (1, ["198.51.100.7"])
    assert [a["entity_label"] for a in card("demo")["alerts"]] == ["+243000000777"]
    # Sans le droit journal (support) : la carte n'est pas envoyée.
    support = UserFactory(is_platform_admin=True, platform_roles=["support"])
    assert card(user=support) is None

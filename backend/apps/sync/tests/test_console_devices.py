"""Appareils de toutes les écoles dans la console de la plateforme (5.4.2) : super-admin
seulement, à l'adresse de la console ; « Déconnecter » ferme la session de l'appareil et va dans
le journal de son école et dans celui de la plateforme."""

from urllib.parse import urlencode

import pytest

from apps.audit.actions import Action, PlatformAction
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.core.tenancy import use_all_schools, use_school
from apps.sync.models import Device
from apps.sync.tests.test_devices import WEBCRYPTO_KEY
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
DEVICES = "/api/console/devices/"


def remember(client, label="Windows · Edge") -> str:
    response = client.post("/api/me/devices/", {"label": label, "public_key": WEBCRYPTO_KEY})
    assert response.status_code == 201, response.content
    return response.json()["id"]


def test_only_the_platform_admin_sees_and_disconnects_devices(
    api, platform_admin, head, other_head
):
    device_id = remember(api(other_head, host="beta.localhost"))
    revoke = f"{DEVICES}{device_id}/revoke/"

    for client in (api(head, host=CONSOLE), api(platform_admin, host=CONSOLE, mfa=False)):
        assert client.get(DEVICES).status_code == 403
        assert client.post(revoke).status_code == 403
    # À l'adresse d'une école, ces points d'API n'existent pas.
    for client in (api(platform_admin), api(head)):
        assert client.get(DEVICES).status_code == 404
        assert client.post(revoke).status_code == 404
    with use_all_schools():
        assert Device.all_schools.get(pk=device_id).revoked_at is None
    assert not PlatformAuditLog.objects.exists()


def test_devices_of_every_school_with_search_and_state(
    api, platform_admin, school, other_school, head, other_head, django_assert_max_num_queries
):
    alpha = remember(api(head), label="Android · Chrome")
    beta = remember(api(other_head, host="beta.localhost"))
    for _ in range(3):
        remember(api(MembershipFactory(school=school, roles=["cashier"]).user))
    console = api(platform_admin, host=CONSOLE)

    with django_assert_max_num_queries(6):
        listed = console.get(DEVICES).json()
    assert listed["count"] == 5
    found = {row["id"]: row for row in listed["results"]}
    assert found[beta]["school"]["code"] == other_school.code
    assert found[alpha]["user"] == {"id": str(head.pk), "name": str(head)}

    # Recherche dans l'appareil, le compte ou l'école.
    assert [
        row["id"]
        for row in console.get(f"{DEVICES}?{urlencode({'search': 'android'})}").json()["results"]
    ] == [alpha]
    by_school = console.get(f"{DEVICES}?{urlencode({'search': other_school.name})}").json()[
        "results"
    ]
    assert [row["id"] for row in by_school] == [beta]

    assert console.post(f"{DEVICES}{beta}/revoke/").status_code == 200
    revoked = console.get(f"{DEVICES}?{urlencode({'state': 'revoked'})}").json()["results"]
    assert [row["id"] for row in revoked] == [beta]
    assert console.get(f"{DEVICES}?{urlencode({'state': 'active'})}").json()["count"] == 4


def test_disconnecting_closes_the_session_and_goes_to_both_journals(
    api, platform_admin, school, other_school, other_head
):
    phone = api(other_head, host="beta.localhost")
    device_id = remember(phone, label="Android · Chrome")
    console = api(platform_admin, host=CONSOLE)

    response = console.post(f"{DEVICES}{device_id}/revoke/")

    assert response.status_code == 200
    assert response.json()["revoked_at"] is not None
    assert phone.get("/api/me/devices/").status_code == 403  # sa session est fermée
    with use_school(other_school):
        entry = AuditLog.objects.get(action=Action.DEVICES_REVOKED)
    assert (str(entry.entity_id), entry.actor) == (device_id, platform_admin)
    with use_school(school):
        assert not AuditLog.objects.filter(action=Action.DEVICES_REVOKED).exists()
    platform = PlatformAuditLog.objects.get()
    assert (platform.action, platform.entity_id) == (PlatformAction.DEVICE_REVOKED, device_id)
    assert other_school.name in platform.entity_label

    # Une deuxième fois : rien de plus.
    assert console.post(f"{DEVICES}{device_id}/revoke/").status_code == 200
    assert PlatformAuditLog.objects.count() == 1
    with use_school(other_school):
        assert AuditLog.objects.filter(action=Action.DEVICES_REVOKED).count() == 1

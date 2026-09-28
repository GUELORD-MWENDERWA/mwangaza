import base64
from datetime import UTC, datetime

import pytest

from apps.audit import services as audit
from apps.audit.actions import Action
from apps.audit.context import RequestInfo, use_request_info
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.finance.models import CashRegister
from apps.sync import services
from apps.sync.models import Device
from tests.factories import MembershipFactory

URL = "/api/me/devices/"
# Paire créée par WebCrypto (Node, comme le navigateur) : clé publique SPKI et signature r ‖ s.
WEBCRYPTO_KEY = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEAxaJQv2q2g2p9MlGNFQNfMyPhKe80PF3p2GyQveTDlnuqmB66sU1V7T"
    "k4jLmi5SRDaKU/wfjRG8baQnpDqp5Ew=="
)
WEBCRYPTO_MESSAGE = b"ITIG-P1-26-000184|2026-09-28T10:42:00Z|15000|USD|K.M."
WEBCRYPTO_SIGNATURE = base64.b64decode(
    "O8hc6zI495x/ijjCipLYny31og1OseX6Us0UWMhsxLrG0VIOH5AWP6ueVmPEqKHx7OuYYexgCCw/zETtcgUiAw=="
)


def remember(client, label="Windows · Edge"):
    return client.post(URL, {"label": label, "public_key": WEBCRYPTO_KEY})


def test_each_device_gets_its_own_prefix_never_a_register_code(api, school, head, cashier):
    with use_school(school):
        CashRegister.objects.create(name="Caisse P", code="P2")

    first = remember(api(head))
    second = remember(api(cashier), label="Android · Chrome")

    assert (first.status_code, first.json()["prefix"]) == (201, "P1")
    assert second.json()["prefix"] == "P3"
    with use_school(school):
        entry = AuditLog.objects.get(action=Action.DEVICES_REGISTERED, actor=cashier)
    assert (entry.entity_label, entry.after) == (
        "P3 · Android · Chrome",
        {"prefix": "P3", "label": "Android · Chrome"},
    )


def test_a_key_that_is_not_a_p256_public_key_is_refused(api, head):
    response = api(head).post(URL, {"label": "PC", "public_key": "pas-une-cle"})

    assert response.status_code == 400
    assert response.json()["fields"]["public_key"][0]["code"] == "invalid_key"


def test_only_members_of_the_school_manage_their_devices(api, head, other_head):
    assert remember(api()).status_code == 403
    assert remember(api(other_head)).status_code == 403  # compte de l'école beta sur alpha
    assert api(head).get(URL).status_code == 200


def test_a_school_or_another_account_never_sees_nor_touches_a_device(
    api, school, other_school, head, cashier
):
    MembershipFactory(school=other_school, user=head, roles=["head"])
    device_id = remember(api(head)).json()["id"]

    from_beta = api(head, host="beta.localhost")
    assert from_beta.get(URL).json()["results"] == []
    assert from_beta.post(f"{URL}{device_id}/resume/").status_code == 404
    assert from_beta.post(f"{URL}{device_id}/revoke/").status_code == 404

    colleague = api(cashier)
    assert colleague.get(URL).json()["results"] == []
    assert colleague.post(f"{URL}{device_id}/resume/").status_code == 404
    assert colleague.post(f"{URL}{device_id}/revoke/").status_code == 404
    with use_school(school):
        assert Device.objects.get(pk=device_id).revoked_at is None


def test_disconnecting_a_device_closes_its_session_and_is_audited(api, school, head):
    phone, laptop = api(head), api(head)
    phone_id = remember(phone, label="Android · Chrome").json()["id"]
    laptop_id = remember(laptop).json()["id"]

    listed = laptop.get(URL).json()["results"]
    assert {(d["id"], d["is_current"]) for d in listed} == {(phone_id, False), (laptop_id, True)}

    assert laptop.post(f"{URL}{phone_id}/revoke/").status_code == 204

    assert phone.get(URL).status_code == 403  # plus de session sur le téléphone
    assert [d["id"] for d in laptop.get(URL).json()["results"]] == [laptop_id]
    with use_school(school):
        entry = AuditLog.objects.get(action=Action.DEVICES_REVOKED)
    # L'action porte l'appareil depuis lequel elle a été faite.
    assert (str(entry.entity_id), str(entry.device_id)) == (phone_id, laptop_id)


def test_a_new_login_resumes_the_device_unless_it_was_disconnected(api, school, head):
    device_id = remember(api(head)).json()["id"]

    later = api(head)
    resumed = later.post(f"{URL}{device_id}/resume/")
    assert (resumed.status_code, resumed.json()["is_current"]) == (200, True)

    later.post(f"{URL}{device_id}/revoke/")
    again = api(head).post(f"{URL}{device_id}/resume/")
    assert (again.status_code, again.json()["code"]) == (409, "device_revoked")


def test_the_device_only_goes_to_the_journal_of_its_school(school, other_school, head):
    with use_school(school):
        device = Device.objects.create(user=head, label="PC", prefix="P1", public_key="x")
    info = RequestInfo(device_id=str(device.pk), device_school_id=school.pk)
    offline_at = datetime(2026, 9, 28, 10, 42, tzinfo=UTC)

    with use_request_info(info):
        with use_school(school):
            here = audit.record(Action.AUTH_LOGIN, actor=head, device_time=offline_at)
        with use_school(other_school):
            elsewhere = audit.record(Action.AUTH_LOGIN, actor=head)

    assert (str(here.device_id), here.device_time) == (str(device.pk), offline_at)
    assert elsewhere.device_id is None


@pytest.mark.parametrize(
    ("message", "signature", "valid"),
    [
        (WEBCRYPTO_MESSAGE, WEBCRYPTO_SIGNATURE, True),
        (WEBCRYPTO_MESSAGE.replace(b"15000", b"95000"), WEBCRYPTO_SIGNATURE, False),
        (WEBCRYPTO_MESSAGE, WEBCRYPTO_SIGNATURE[:-1], False),
    ],
)
def test_a_receipt_signed_in_the_browser_is_verified_by_the_server(message, signature, valid):
    device = Device(public_key=WEBCRYPTO_KEY)

    assert services.verify_signature(device, message, signature) is valid

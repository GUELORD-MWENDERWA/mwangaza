"""Synchronisation (3.3.2) : appareil enregistré exigé, isolation entre écoles, droits,
instantané et changements (écritures en masse et transaction en cours comprises), opérations
appliquées une seule fois, encaissement hors ligne jamais refusé pour un surplus."""

import threading
from datetime import UTC, datetime

import pytest
from django.db import connection, transaction

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.models import Payment, PaymentAllocation
from apps.finance.tests.test_charges import once, rule
from apps.finance.tests.test_payments import school_with_fees
from apps.students.tests.conftest import enrolled
from apps.sync import changes
from apps.sync.models import ChangeLog, Device, SyncOperation
from apps.sync.tests.test_devices import remember
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SNAPSHOT, PULL, PUSH = "/api/sync/snapshot/", "/api/sync/pull/", "/api/sync/push/"
PAID_AT = "2026-10-02T08:15:00Z"


def till(api, school, cashier, data, host="alpha.localhost"):
    """Le caissier sur son appareil enregistré, sa caisse ouverte."""
    client = api(cashier, host)
    device = remember(client).json()
    with use_school(school):
        session = finance.open_cash_session(actor=cashier, cash_register=data["register"])
    return client, device, session


def payment_op(data, device, session, amount, *, seq=1, code="ALPHA", **payload) -> dict:
    return {
        "op_id": str(uuid7()),
        "type": "payment.create",
        "payload": {
            "id": str(uuid7()),
            "enrollment": str(data["enrollment"].pk),
            "cash_session": str(session.pk),
            "received_amount_minor": amount,
            "received_currency": "USD",
            "receipt_number": f"{code}-{device['prefix']}-26-{seq:06d}",
            "paid_at": PAID_AT,
            **payload,
        },
    }


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


def test_only_a_remembered_device_of_an_allowed_account_syncs(api, school, head, cashier, alpha):
    client = api(cashier)
    assert client.get(PULL, since=0).json()["code"] == "device_required"
    device = remember(client).json()
    assert client.get(PULL, since=0).status_code == 200
    with use_school(school):
        Device.objects.filter(pk=device["id"]).update(revoked_at=datetime.now(UTC))
    response = client.post(PUSH, {"operations": []})
    assert (response.status_code, response.json()["code"]) == (409, "device_revoked")

    teacher = api(MembershipFactory(school=school, roles=["teacher"]).user)
    remember(teacher)
    assert teacher.get(SNAPSHOT).status_code == 403


def test_the_snapshot_gives_each_account_what_its_rights_allow(api, school, head, cashier, alpha):
    other = MembershipFactory(school=school, roles=["cashier"]).user
    client, device, _session = till(api, school, cashier, alpha)
    with use_school(school):
        finance.open_cash_session(
            actor=other,
            cash_register=finance.create_cash_register(actor=head, name="Caisse 2", code="C2"),
        )
        mine, _ = finance.record_payment(
            alpha["enrollment"], actor=cashier, received_amount_minor=5000, received_currency="USD"
        )
        finance.record_payment(
            alpha["enrollment"], actor=other, received_amount_minor=1000, received_currency="USD"
        )
    for name in ("Amani", "Baraka"):
        enrolled(school, head, alpha["group"], first_name=name)

    first = client.get(SNAPSHOT, limit=2).json()
    assert first["device"]["prefix"] == device["prefix"] and first["cursor"] > 0
    assert [fee["name"] for fee in first["config"]["fee_types"]] == ["Fonctionnement", "Minerval"]
    assert first["config"]["exchange_rate"]["rate"] == "2850.000000"
    rest = client.get(SNAPSHOT, after=first["next"], limit=2).json()
    assert rest["next"] is None and rest["cursor"] is None and rest["config"] is None
    items = {e["id"]: e for e in first["enrollments"] + rest["enrollments"]}
    assert len(items) == 3
    bundle = items[str(alpha["enrollment"].pk)]
    # Le caissier : seulement ses paiements, mais tout ce qui est payé compte dans le reste dû.
    assert [p["receipt_number"] for p in bundle["payments"]] == [mine.receipt_number]
    minerval = [c for c in bundle["charges"] if c["fee_type_name"] == "Minerval"]
    assert [c["remaining_minor"] for c in minerval] == [6000, 12000, 12000]

    secretary = api(MembershipFactory(school=school, roles=["secretary"]).user)
    remember(secretary)
    data = secretary.get(SNAPSHOT).json()
    assert data["config"]["fee_types"] is None and data["config"]["exchange_rate"] is None
    assert {e["charges"] for e in data["enrollments"]} == {None}


def test_pull_returns_what_changed_since_the_cursor_bulk_writes_included(
    api, school, head, cashier, alpha
):
    client, _device, _session = till(api, school, cashier, alpha)
    cursor = client.get(SNAPSHOT).json()["cursor"]
    assert client.get(PULL, since=cursor).json() == {
        "changes": [],
        "cursor": cursor,
        "has_more": False,
    }
    with use_school(school):
        # Nouveau barème : frais dus créés en masse pour les élèves inscrits.
        rule(head, alpha, "Atelier", "USD", once("Atelier", 1500))
    data = client.get(PULL, since=cursor).json()
    kinds = {(c["entity_type"], c["operation"]) for c in data["changes"]}
    assert kinds == {("config", "upsert"), ("enrollment", "upsert")}
    enrollment = next(c for c in data["changes"] if c["entity_type"] == "enrollment")
    assert "Atelier" in {c["fee_type_name"] for c in enrollment["enrollment"]["charges"]}
    assert client.get(PULL, since=data["cursor"]).json()["changes"] == []
    assert client.get(PULL, since=data["cursor"] + 1).json()["code"] == "snapshot_required"


@pytest.mark.django_db(transaction=True)
def test_a_change_committed_after_a_pull_is_never_missed(school):
    """Un import encore en cours tient ses lignes : la lecture ne l'attend pas, et ses
    changements, validés ensuite, arrivent au pull suivant."""
    first, second = uuid7(), uuid7()
    with use_school(school):
        changes.touch_enrollments([first])
    holding, release = threading.Event(), threading.Event()

    def long_transaction():
        with use_school(school), transaction.atomic():
            changes.touch_enrollments([first])
            holding.set()
            release.wait(timeout=10)
        connection.close()

    worker = threading.Thread(target=long_transaction)
    worker.start()
    holding.wait(timeout=10)
    with use_school(school):
        changes.touch_enrollments([second])
        cursor = changes.sequence()
        release.set()
        worker.join()
        changes.sequence()
        seqs = dict(ChangeLog.objects.values_list("entity_id", "seq"))
    assert seqs[second] == cursor and seqs[first] > cursor


def test_the_same_batch_sent_twice_is_applied_once(api, school, head, cashier, alpha):
    client, device, session = till(api, school, cashier, alpha)
    batch = {"receipt_seq": 1, "operations": [payment_op(alpha, device, session, 12000)]}

    first = client.post(PUSH, batch).json()["results"]
    again = client.post(PUSH, batch).json()["results"]
    assert [r["status"] for r in first + again] == ["applied", "duplicate"]
    assert first[0]["result"] == again[0]["result"]
    with use_school(school):
        payment = Payment.objects.get()
        entry = AuditLog.objects.get(action=Action.FINANCE_PAYMENT_RECORDED)
        registered = Device.objects.get(pk=device["id"])
    assert payment.receipt_number == f"ALPHA-{device['prefix']}-26-000001"
    assert payment.paid_at == datetime(2026, 10, 2, 8, 15, tzinfo=UTC)
    assert payment.device_id == registered.pk and payment.synced_at is not None
    assert entry.device_time == payment.paid_at and entry.device_id == registered.pk
    assert registered.last_receipt_seq == 1


def test_two_offline_tills_paying_the_same_fee_both_keep_the_money(
    api, school, head, cashier, alpha
):
    """Deux caisses hors ligne encaissent pour le même élève : aucune n'est refusée. La
    seconde ne trouve plus rien à payer (sa répartition ne tient plus) : son argent n'est
    affecté à rien (crédit de l'élève en 3.6)."""
    other = MembershipFactory(school=school, roles=["cashier"]).user
    with use_school(school):
        register = finance.create_cash_register(actor=head, name="Caisse 2", code="C2")
        first = next(
            c for c in finance.charges_of(alpha["enrollment"].pk) if c.fee_type.name == "Minerval"
        )
    one, device_one, session_one = till(api, school, cashier, alpha)
    two, device_two, session_two = till(api, school, other, {**alpha, "register": register})
    everything = payment_op(alpha, device_one, session_one, 36000)
    parts = [{"student_charge": str(first.pk), "received_minor": 12000}]
    late = payment_op(alpha, device_two, session_two, 12000, allocations=parts)
    for client, op in [(one, everything), (two, late)]:
        assert client.post(PUSH, {"operations": [op]}).json()["results"][0]["status"] == "applied"

    with use_school(school):
        payments = Payment.objects.order_by("synced_at")
        allocated = [
            sum(
                PaymentAllocation.objects.filter(payment=p).values_list("received_minor", flat=True)
            )
            for p in payments
        ]
        remaining = finance.balance(finance.charges_of(alpha["enrollment"].pk)).currencies
    assert [p.received_amount_minor for p in payments] == [36000, 12000]
    assert allocated == [36000, 0]
    assert {(c.currency, c.remaining_minor) for c in remaining} == {("USD", 0), ("CDF", 25000)}


def test_a_rejected_operation_stays_rejected_and_the_next_ones_go_on(
    api, school, head, cashier, alpha
):
    client, device, session = till(api, school, cashier, alpha)
    stolen = payment_op(alpha, {"prefix": "P9"}, session, 5000)
    good = payment_op(alpha, device, session, 5000, seq=2)
    results = client.post(PUSH, {"operations": [stolen, good]}).json()["results"]
    assert [r["status"] for r in results] == ["rejected", "applied"]
    assert results[0]["error"]["fields"]["receipt_number"][0]["code"] == "receipt_number_invalid"
    again = client.post(PUSH, {"operations": [stolen]}).json()["results"][0]
    assert again == results[0]

    secretary = api(MembershipFactory(school=school, roles=["secretary"]).user)
    remember(secretary)
    refused = secretary.post(PUSH, {"operations": [payment_op(alpha, device, session, 100)]})
    assert refused.json()["results"][0]["error"]["code"] == "permission_denied"
    with use_school(school):
        assert Payment.objects.count() == 1
        assert SyncOperation.objects.filter(status="rejected").count() == 2


def test_a_school_never_reads_nor_writes_another_school_through_sync(
    api, school, other_school, head, other_head, cashier, alpha
):
    beta = school_with_fees(other_school, other_head)
    beta_cashier = MembershipFactory(school=other_school, roles=["cashier"]).user
    client, device, session = till(api, school, cashier, alpha)
    applied = payment_op(alpha, device, session, 1000)
    client.post(PUSH, {"operations": [applied]})

    other, other_device, other_session = till(
        api, other_school, beta_cashier, beta, host="beta.localhost"
    )
    snapshot = other.get(SNAPSHOT).json()
    assert [e["id"] for e in snapshot["enrollments"]] == [str(beta["enrollment"].pk)]
    pulled = other.get(PULL, since=0).json()["changes"]
    assert str(alpha["enrollment"].pk) not in {c["entity_id"] for c in pulled}
    assert {c["entity_id"] for c in pulled if c["entity_type"] == "config"} == {
        str(other_school.pk)
    }
    # Une inscription de l'autre école est introuvable ; un `op_id` déjà vu ailleurs est neuf.
    intruder = payment_op(alpha, other_device, other_session, 1000, code="BETA")
    intruder["op_id"] = applied["op_id"]
    result = other.post(PUSH, {"operations": [intruder]}).json()["results"][0]
    assert result["status"] == "rejected"
    assert result["error"]["fields"]["enrollment"][0]["code"] == "does_not_exist"
    with use_school(other_school):
        assert not Payment.objects.exists()

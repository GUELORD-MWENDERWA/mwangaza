"""Annulation d'un paiement (3.8.1, F7) : isolation entre écoles, droits (demander ses paiements,
valider jamais sa propre demande), le paiement compte jusqu'à la validation, reçu d'annulation
numéroté dans sa série avec le reste dû, refus, crédits de réduction annulés à hauteur du
trop-payé disparu ; audit. Demande hors ligne et surplus hors ligne :
`apps/sync/tests/test_sync.py`."""

import pytest

from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import CancellationRequest, StudentCredit
from apps.finance.tests.test_api import entries
from apps.finance.tests.test_credits import minerval, scholarship, usd
from apps.finance.tests.test_payments import pay, school_with_fees
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

CANCELLATIONS = "/api/cancellations/"


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


@pytest.fixture
def accountant(school):
    return MembershipFactory(school=school, roles=["accountant"]).user


def ask(client, payment, reason="Mauvais élève sélectionné (homonyme)"):
    return client.post(CANCELLATIONS, {"payment": str(payment.pk), "reason": reason})


def test_a_school_neither_reads_nor_decides_the_cancellations_of_another(
    api, school, other_school, cashier, other_head, alpha
):
    payment = pay(school, cashier, alpha["enrollment"], 12000, "USD")
    request_id = ask(api(cashier), payment).json()["id"]
    other = api(other_head, "beta.localhost")

    assert other.get(CANCELLATIONS).json()["results"] == []
    for action in ["", "receipt/"]:
        assert other.get(f"{CANCELLATIONS}{request_id}/{action}").status_code == 404
    for action in ["approve/", "reject/", "reprint/"]:
        assert other.post(f"{CANCELLATIONS}{request_id}/{action}").status_code == 404
    # Le paiement d'une autre école est introuvable.
    beta_accountant = MembershipFactory(school=other_school, roles=["accountant"]).user
    refused = ask(api(beta_accountant, "beta.localhost"), payment)
    assert refused.json()["fields"]["payment"][0]["code"] == "does_not_exist"
    with use_school(school):
        assert CancellationRequest.objects.get().status == "pending"


def test_asking_and_deciding_need_their_rights_and_never_ones_own_request(
    api, school, head, cashier, accountant, alpha
):
    """Le caissier demande pour ses paiements et ne voit que ses demandes ; il ne valide pas. Le
    comptable demande pour tout paiement mais ne valide pas sa propre demande. La secrétaire
    ne voit rien ; le directeur valide sans demander."""
    other_cashier = MembershipFactory(school=school, roles=["cashier"]).user
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    payment = pay(school, cashier, alpha["enrollment"], 12000, "USD")
    with use_school(school):
        services.create_cash_register(actor=head, name="Caisse 2", code="C2")
    other_payment = pay(school, accountant, alpha["enrollment"], 6000, "USD", code="C2")

    assert ask(api(other_cashier), payment).status_code == 403
    assert ask(api(head), payment).status_code == 403
    assert api(secretary).get(CANCELLATIONS).status_code == 403
    mine = ask(api(cashier), payment).json()["id"]
    theirs = ask(api(accountant), other_payment).json()["id"]
    assert [r["id"] for r in api(cashier).get(CANCELLATIONS).json()["results"]] == [mine]
    assert len(api(head).get(CANCELLATIONS).json()["results"]) == 2
    assert api(cashier).post(f"{CANCELLATIONS}{mine}/approve/").status_code == 403

    own = api(accountant).post(f"{CANCELLATIONS}{theirs}/approve/")

    assert (own.status_code, own.json()["code"]) == (403, "own_cancellation")
    assert api(accountant).post(f"{CANCELLATIONS}{mine}/approve/").status_code == 200


def test_a_payment_counts_until_its_cancellation_is_approved_with_a_numbered_receipt(
    api, school, head, cashier, alpha
):
    enrollment = alpha["enrollment"]
    payment = pay(school, cashier, enrollment, 12000, "USD")
    as_cashier = api(cashier)
    request_id = ask(as_cashier, payment).json()["id"]

    shown = as_cashier.get(f"/api/payments/{payment.pk}/").json()
    assert (shown["cancelled"], shown["cancellation_pending"]) == (False, True)
    assert usd(school, alpha) == (12000, 24000)
    assert as_cashier.get("/api/cash-sessions/current/").json()["totals"] != []
    assert ask(as_cashier, payment).json()["code"] == "cancellation_pending"
    assert as_cashier.get(f"{CANCELLATIONS}{request_id}/receipt/").status_code == 404

    approved = api(head).post(f"{CANCELLATIONS}{request_id}/approve/", {"note": "Vu le parent"})

    assert approved.status_code == 200, approved.content
    receipt = approved.json()
    assert receipt["status"] == "approved"
    assert receipt["cancellation"]["receipt_number"] == "ALPHA-AN-26-000001"
    [remaining] = [c for c in receipt["balance"]["currencies"] if c["currency"] == "USD"]
    assert remaining["remaining_minor"] == 36000
    assert usd(school, alpha) == (0, 36000)
    assert as_cashier.get(f"/api/payments/{payment.pk}/").json()["cancelled"] is True
    assert as_cashier.get("/api/cash-sessions/current/").json()["totals"] == []
    again = api(head).post(f"{CANCELLATIONS}{request_id}/approve/")
    assert again.json()["code"] == "cancellation_decided"
    assert ask(as_cashier, payment).json()["code"] == "payment_cancelled"

    second = pay(school, cashier, enrollment, 6000, "USD")
    later = ask(as_cashier, second).json()["id"]
    numbered = api(head).post(f"{CANCELLATIONS}{later}/approve/").json()
    assert numbered["cancellation"]["receipt_number"] == "ALPHA-AN-26-000002"
    assert as_cashier.post(f"{CANCELLATIONS}{request_id}/reprint/").status_code == 200

    [requested, _later] = entries(school, Action.FINANCE_CANCELLATION_REQUESTED)
    assert requested.actor == cashier and requested.after["reason"].startswith("Mauvais élève")
    [cancelled, _second] = entries(school, Action.FINANCE_PAYMENT_CANCELLED)
    assert (cancelled.actor, cancelled.entity_id) == (head, payment.pk)
    assert cancelled.after["cancellation_receipt_number"] == "ALPHA-AN-26-000001"
    [reprinted] = entries(school, Action.FINANCE_CANCELLATION_REPRINTED)
    assert reprinted.actor == cashier


def test_a_refused_cancellation_leaves_the_payment_valid_and_can_be_asked_again(
    api, school, head, cashier, alpha
):
    payment = pay(school, cashier, alpha["enrollment"], 12000, "USD")
    request_id = ask(api(cashier), payment).json()["id"]

    refused = api(head).post(f"{CANCELLATIONS}{request_id}/reject/", {"note": "Parent absent"})

    assert (refused.json()["status"], refused.json()["decision_note"]) == (
        "rejected",
        "Parent absent",
    )
    assert usd(school, alpha) == (12000, 24000)
    assert api(head).post(f"{CANCELLATIONS}{request_id}/approve/").status_code == 409
    assert ask(api(cashier), payment).status_code == 201
    [entry] = entries(school, Action.FINANCE_CANCELLATION_REJECTED)
    assert (entry.actor, entry.after["note"]) == (head, "Parent absent")


def test_cancelling_a_payment_voids_the_discount_credit_it_had_made_and_keeps_the_rest(
    school, head, cashier, alpha
):
    """Deux tranches payées (2 x 120,00 $), puis une bourse de 25 % : 2 x 30,00 $ de trop, un
    crédit de 60,00 $. Le 1er paiement annulé, seuls 30,00 $ restent de trop : le crédit de
    60,00 $ est annulé et un crédit de 30,00 $ de la même bourse le remplace."""
    first = pay(school, cashier, alpha["enrollment"], 12000, "USD")
    pay(school, cashier, alpha["enrollment"], 12000, "USD")
    discount = scholarship(school, head, alpha, 25)
    with use_school(school):
        request, _created = services.request_cancellation(
            first, actor=cashier, reason="Mauvais élève"
        )
        services.approve_cancellation(request, actor=head)
        credits = list(
            StudentCredit.objects.select_related("source_discount").order_by("created_at")
        )

    assert [(c.amount_minor, c.voided_at is not None) for c in credits] == [
        (6000, True),
        (3000, False),
    ]
    assert credits[1].source_discount == discount
    assert minerval(school, alpha)[:2] == [(9000, 0), (9000, 9000)]
    [voided] = entries(school, Action.FINANCE_CREDIT_VOIDED)
    assert voided.before["amount_minor"] == 6000

"""Sorties de caisse (FIN.2) : isolation entre écoles, droits (payer avec la caisse, annuler),
argent (entiers, par devise, jamais plus que ce que la caisse a reçu), clôture qui les déduit,
annulation sans effacement tant que la session est ouverte, audit, idempotence."""

from datetime import UTC, date, datetime

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.finance import expenses, services
from apps.finance.models import (
    CashOut,
    CashOutCancellation,
    CashSession,
    Expense,
    ExpenseCategory,
    ImmutablePaymentError,
)
from apps.finance.tests.test_api import entries
from apps.finance.tests.test_closing import counted
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.sync.tests.test_devices import remember
from apps.sync.tests.test_sync import payment_op, till
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

CASH_OUTS = "/api/cash-outs/"
SESSIONS = "/api/cash-sessions/"


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


def spend(school, actor, amount: int, currency: str = "USD", account: str = "cash") -> Expense:
    """Une dépense saisie par `actor` : validée d'office sous le seuil (200,00 $, 500 000 FC)."""
    with use_school(school):
        category = ExpenseCategory.objects.filter(name="Atelier").first()
        if category is None:
            category = expenses.create_category(actor=actor, name="Atelier")
        expense, _created = expenses.record_expense(
            actor=actor,
            category=category,
            beneficiary="Quincaillerie Mapendo",
            reason="Pièces du banc d'essai",
            amount_minor=amount,
            currency=currency,
            spent_on=date(2026, 10, 19),
            account=account,
        )
    return expense


def out(expense, **over) -> dict:
    return {"expense": str(expense.pk), "received_by": "Kahindo Jean-Claude", **over}


def code(response) -> str:
    assert response.status_code == 409, response.content
    return response.json()["code"]


# Isolation et droits


def test_a_school_neither_reads_nor_pays_nor_cancels_the_cash_outs_of_another(
    api, school, other_school, head, cashier, other_head, alpha
):
    pay(school, cashier, alpha["enrollment"], 30000, "USD")
    expense = spend(school, head, 18500)
    cash_out = api(cashier).post(CASH_OUTS, out(expense)).json()
    left = spend(school, head, 5000)
    school_with_fees(other_school, other_head)
    beta_cashier = MembershipFactory(school=other_school, roles=["cashier"]).user
    other = api(beta_cashier, "beta.localhost")

    assert other.get(f"{CASH_OUTS}payable/").json()["results"] == []
    assert other.get(CASH_OUTS).json()["results"] == []
    assert other.get(f"{CASH_OUTS}{cash_out['id']}/").status_code == 404
    # Payer la dépense d'une autre école : elle n'existe pas ici.
    assert other.post(CASH_OUTS, out(left)).status_code == 404
    boss = api(other_head, "beta.localhost")
    assert boss.get(CASH_OUTS).json()["results"] == []
    assert boss.post(f"{CASH_OUTS}{cash_out['id']}/cancel/", {"reason": "x"}).status_code == 404
    with use_school(school):
        assert not CashOutCancellation.objects.exists()
        assert Expense.objects.get(pk=left.pk).status == Expense.Status.APPROVED


def test_only_a_cashier_pays_out_and_only_cancel_expense_cancels(api, school, head, cashier, alpha):
    pay(school, cashier, alpha["enrollment"], 30000, "USD")
    expense = spend(school, head, 18500)
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    other_cashier = MembershipFactory(school=school, roles=["cashier"]).user

    assert api(secretary).get(f"{CASH_OUTS}payable/").status_code == 403
    assert api(secretary).post(CASH_OUTS, out(expense)).status_code == 403
    # Le préfet valide les dépenses mais ne tient pas la caisse.
    assert api(head).post(CASH_OUTS, out(expense)).status_code == 403
    cash_out = api(cashier).post(CASH_OUTS, out(expense)).json()
    url = f"{CASH_OUTS}{cash_out['id']}/"
    # Un autre caissier ne voit pas la sortie ; le préfet (rapports) la voit et l'annule.
    assert api(other_cashier).get(CASH_OUTS).json()["results"] == []
    assert api(other_cashier).get(url).status_code == 404
    assert api(cashier).post(f"{url}cancel/", {"reason": "Erreur"}).status_code == 403
    assert [c["id"] for c in api(head).get(CASH_OUTS).json()["results"]] == [cash_out["id"]]
    assert api(head).post(f"{url}cancel/", {"reason": "Erreur"}).status_code == 200


# Argent et clôture


def test_a_cash_out_leaves_the_session_and_the_closing_deducts_it(
    api, school, head, cashier, alpha
):
    """300,00 $ et 25 000 FC reçus, 185,00 $ sortis : 115,00 $ et 25 000 FC attendus."""
    pay(school, cashier, alpha["enrollment"], 30000, "USD")
    pay(school, cashier, alpha["enrollment"], 25000, "CDF")
    expense = spend(school, head, 18500)
    as_cashier = api(cashier)
    assert [e["number"] for e in as_cashier.get(f"{CASH_OUTS}payable/").json()["results"]] == [
        expense.number
    ]

    body = out(expense, id="01930000-0000-7000-8000-000000000001")
    created = as_cashier.post(CASH_OUTS, body)
    assert created.status_code == 201, created.content
    cash_out = created.json()
    assert (cash_out["amount_minor"], cash_out["currency"]) == (18500, "USD")
    assert cash_out["number"].startswith("ALPHA-C1-") and cash_out["number"].endswith("-S0001")
    # Même envoi rejoué (double clic, réseau) : la même sortie, pas une deuxième.
    again = as_cashier.post(CASH_OUTS, body)
    assert (again.status_code, again.json()["number"]) == (200, cash_out["number"])
    with use_school(school):
        assert CashOut.objects.count() == 1
        expense.refresh_from_db()
        session = CashSession.objects.get()
    assert expense.status == Expense.Status.PAID
    assert (
        api(head).get(f"/api/expenses/{expense.pk}/").json()["cash_out_number"]
        == (cash_out["number"])
    )
    assert as_cashier.get(f"{CASH_OUTS}payable/").json()["results"] == []
    current = as_cashier.get(f"{SESSIONS}current/").json()
    assert current["paid_out"] == [{"currency": "USD", "amount_minor": 18500, "count": 1}]

    summary = as_cashier.get(f"{SESSIONS}{session.pk}/closing/").json()
    lines = {
        (c["currency"], c["received_minor"], c["paid_out_minor"], c["expected_minor"])
        for c in summary["currencies"]
    }
    assert lines == {("USD", 30000, 18500, 11500), ("CDF", 25000, 0, 25000)}
    assert [(c["number"], c["expense_number"]) for c in summary["cash_outs"]] == [
        (cash_out["number"], expense.number)
    ]
    closed = as_cashier.post(f"{SESSIONS}{session.pk}/close/", counted(11500, 25000))
    assert closed.status_code == 200, closed.content
    frozen = {
        (line["currency"], line["difference_minor"]) for line in closed.json()["closing"]["lines"]
    }
    assert frozen == {("USD", 0), ("CDF", 0)}
    [audited] = entries(school, Action.FINANCE_CASH_OUT_RECORDED)
    assert audited.after == {
        "number": cash_out["number"],
        "expense": expense.number,
        "amount_minor": 18500,
        "currency": "USD",
        "received_by": "Kahindo Jean-Claude",
        "cash_register": "C1",
    }


def test_no_cash_out_without_the_money_an_open_session_or_an_approved_cash_expense(
    api, school, head, cashier, alpha
):
    as_cashier = api(cashier)
    expense = spend(school, head, 18500)
    assert code(as_cashier.post(CASH_OUTS, out(expense))) == "no_open_session"
    # 100,00 $ et 25 000 FC reçus : pas assez de dollars, les francs ne comptent pas.
    pay(school, cashier, alpha["enrollment"], 10000, "USD")
    pay(school, cashier, alpha["enrollment"], 25000, "CDF")
    assert code(as_cashier.post(CASH_OUTS, out(expense))) == "not_enough_cash"
    pending = spend(school, head, 25000)  # au-dessus du seuil : en attente
    by_bank = spend(school, head, 5000, account="bank")
    for refused in (pending, by_bank):
        assert code(as_cashier.post(CASH_OUTS, out(refused))) == "expense_not_payable_in_cash"
    small = spend(school, head, 4000)
    assert as_cashier.post(CASH_OUTS, out(small)).status_code == 201
    assert code(as_cashier.post(CASH_OUTS, out(small))) == "expense_already_paid"
    # Sortie de la caisse, la dépense ne s'annule plus : seule sa sortie s'annule.
    refused = api(head).post(f"/api/expenses/{small.pk}/cancel/", {"reason": "Doublon"})
    assert code(refused) == "expense_paid_from_cash_desk"
    cancelled = spend(school, head, 3000)
    with use_school(school):
        expenses.cancel_expense(cancelled, actor=head, reason="Doublon")
    assert code(as_cashier.post(CASH_OUTS, out(cancelled))) == "expense_cancelled"
    with use_school(school):
        assert CashOut.objects.count() == 1


def test_a_cancelled_cash_out_puts_the_money_back_until_the_closing(
    api, school, head, cashier, alpha
):
    pay(school, cashier, alpha["enrollment"], 30000, "USD")
    expense = spend(school, head, 18500)
    as_cashier, boss = api(cashier), api(head)
    wrong = as_cashier.post(CASH_OUTS, out(expense)).json()
    cancel = f"{CASH_OUTS}{wrong['id']}/cancel/"

    cancelled = boss.post(cancel, {"reason": "Mauvaise dépense choisie"})
    assert cancelled.status_code == 200, cancelled.content
    assert cancelled.json()["cancelled"] is True
    assert code(boss.post(cancel, {"reason": "Encore"})) == "cash_out_cancelled"
    with use_school(school):
        expense.refresh_from_db()
        session = CashSession.objects.get()
        kept = CashOut.objects.get(pk=wrong["id"])
    assert (expense.status, expense.paid_at) == (Expense.Status.APPROVED, None)
    summary = as_cashier.get(f"{SESSIONS}{session.pk}/closing/").json()
    usd = next(c for c in summary["currencies"] if c["currency"] == "USD")
    assert (usd["paid_out_minor"], usd["expected_minor"], summary["cash_outs"]) == (0, 30000, [])
    [audited] = entries(school, Action.FINANCE_CASH_OUT_CANCELLED)
    assert audited.after == {"cancelled": True, "reason": "Mauvaise dépense choisie"}

    # Payée de nouveau : un nouveau bon ; après la clôture, plus d'annulation.
    right = as_cashier.post(CASH_OUTS, out(expense)).json()
    assert right["number"].endswith("-S0002")
    assert as_cashier.post(f"{SESSIONS}{session.pk}/close/", counted(11500, 0)).status_code == 200
    late = boss.post(f"{CASH_OUTS}{right['id']}/cancel/", {"reason": "Trop tard"})
    assert code(late) == "cash_out_session_closed"
    # La sortie annulée reste, et ni le code ni la base ne la changent ou l'effacent.
    with use_school(school):
        with pytest.raises(ImmutablePaymentError):
            kept.save()
        with pytest.raises(ImmutablePaymentError):
            CashOut.objects.update(amount_minor=1)
        for sql in (
            "UPDATE finance_cashout SET amount_minor = 1",
            "DELETE FROM finance_cashoutcancellation",
        ):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)
        assert CashOut.objects.count() == 2


# Hors ligne (opération `cash_out.create`)

PUSH = "/api/sync/push/"


def cash_out_op(expense, device, session, *, seq=1, code="ALPHA", **payload) -> dict:
    return {
        "op_id": str(uuid7()),
        "type": "cash_out.create",
        "payload": {
            "id": str(uuid7()),
            "expense": str(expense.pk),
            "cash_session": str(session.pk),
            "number": f"{code}-{device['prefix']}-26-S{seq:04d}",
            "received_by": "Kahindo Jean-Claude",
            "paid_at": "2026-10-02T09:40:00Z",
            **payload,
        },
    }


def results(client, *operations) -> list:
    response = client.post(PUSH, {"operations": list(operations)})
    assert response.status_code == 200, response.content
    return response.json()["results"]


def test_an_offline_cash_out_is_kept_once_at_the_device_number_even_beyond_the_till(
    api, school, head, cashier, alpha
):
    """L'argent est sorti sur l'appareil : jamais refusé pour la caisse (l'attendu devient
    négatif), une fois même renvoyé (même opération, ou même sortie dans une autre opération
    après la purge), au numéro et à l'heure de l'appareil, que l'instantané rend."""
    client, device, session = till(api, school, cashier, alpha)
    expense = spend(school, head, 18500)
    payment = payment_op(alpha, device, session, 12000)
    op = cash_out_op(expense, device, session, seq=3)
    resent = {**op, "op_id": str(uuid7())}

    first = results(client, payment, op)
    again = results(client, op, resent)

    assert [r["status"] for r in first + again] == ["applied", "applied", "duplicate", "applied"]
    assert again[1]["result"] == first[1]["result"]
    with use_school(school):
        cash_out = CashOut.objects.get()
        expense.refresh_from_db()
        summary = services.closing_summary(session)
    assert (cash_out.number, cash_out.amount_minor, str(cash_out.device_id)) == (
        f"ALPHA-{device['prefix']}-26-S0003",
        18500,
        device["id"],
    )
    assert cash_out.paid_at == datetime(2026, 10, 2, 9, 40, tzinfo=UTC)
    assert (expense.status, expense.paid_at) == (Expense.Status.PAID, cash_out.paid_at)
    usd = next(row for row in summary["currencies"] if row["currency"] == "USD")
    assert (usd["received_minor"], usd["paid_out_minor"], usd["expected_minor"]) == (
        12000,
        18500,
        -6500,
    )
    [entry] = entries(school, Action.FINANCE_CASH_OUT_RECORDED)
    assert entry.device_time == cash_out.paid_at and "conflict" not in entry.after
    snapshot = client.get("/api/sync/snapshot/").json()
    assert snapshot["device"]["last_cash_out_seq"] == 3


def test_a_late_offline_cash_out_of_a_paid_expense_is_kept_apart_from_the_closing(
    api, school, head, cashier, alpha
):
    """Session clôturée depuis un autre poste, dépense déjà payée en ligne : la sortie de la
    tablette est gardée (l'argent est parti), hors de l'attendu figé, montrée au comptable
    « arrivée après la clôture », l'écart noté au journal ; la dépense reste payée une fois."""
    pay(school, cashier, alpha["enrollment"], 30000, "USD")
    expense = spend(school, head, 5000)
    online = api(cashier).post(CASH_OUTS, out(expense)).json()
    with use_school(school):
        session = CashSession.objects.get()
    api(cashier).post(f"{SESSIONS}{session.pk}/close/", counted(25000, 0))
    tablet = api(cashier)
    device = remember(tablet).json()

    [result] = results(tablet, cash_out_op(expense, device, session))

    assert result["status"] == "applied", result
    with use_school(school):
        assert CashOut.objects.filter(expense=expense).count() == 2
        assert Expense.objects.get(pk=expense.pk).status == Expense.Status.PAID
    detail = api(head).get(f"/api/cash-closings/{session.pk}/").json()
    usd = next(row for row in detail["currencies"] if row["currency"] == "USD")
    assert (usd["paid_out_minor"], usd["expected_minor"]) == (5000, 25000)
    assert [o["number"] for o in detail["cash_outs"]] == [online["number"]]
    assert [(o["number"], o["amount_minor"], o["cancelled"]) for o in detail["late_cash_outs"]] == [
        (f"ALPHA-{device['prefix']}-26-S0001", 5000, False)
    ]
    late = entries(school, Action.FINANCE_CASH_OUT_RECORDED)[-1]
    assert late.after["conflict"] == "already_paid"


def test_an_offline_cash_out_never_uses_another_school_another_session_or_number(
    api, school, other_school, head, other_head, cashier, alpha
):
    client, device, session = till(api, school, cashier, alpha)
    expense = spend(school, head, 5000)
    school_with_fees(other_school, other_head)
    foreign = spend(other_school, other_head, 5000)
    colleague = MembershipFactory(school=school, roles=["cashier"]).user
    with use_school(school):
        theirs = CashSession.objects.create(
            cash_register=alpha["register"],
            cashier=colleague,
            created_by=colleague,
            closed_at=timezone.now(),
        )

    rejected = results(
        client,
        cash_out_op(foreign, device, session),
        cash_out_op(expense, device, theirs),
        cash_out_op(expense, device, session, number="ALPHA-C1-26-S0001"),
    )

    assert [r["status"] for r in rejected] == ["rejected"] * 3
    assert "expense" in rejected[0]["error"]["fields"]
    assert [r["error"]["code"] for r in rejected[1:]] == [
        "cash_out_session_unknown",
        "cash_out_number_invalid",
    ]
    with use_school(school):
        assert not CashOut.objects.exists()
    with use_school(other_school):
        assert not CashOut.objects.exists()
        assert Expense.objects.get(pk=foreign.pk).status == Expense.Status.APPROVED

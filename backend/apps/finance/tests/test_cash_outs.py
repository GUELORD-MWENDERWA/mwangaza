"""Sorties de caisse (FIN.2) : isolation entre écoles, droits (payer avec la caisse, annuler),
argent (entiers, par devise, jamais plus que ce que la caisse a reçu), clôture qui les déduit,
annulation sans effacement tant que la session est ouverte, audit, idempotence."""

from datetime import date

import pytest
from django.db import DatabaseError, connection, transaction

from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.finance import expenses
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

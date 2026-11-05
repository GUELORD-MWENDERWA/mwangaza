"""Budget et rapports (FIN.3) : isolation entre écoles (rapport, budget, mouvements, Excel), droits
(lire, régler), argent (par devise, jamais additionnées ; annulés, en attente et autre année
exclus), comptes (départ, caisse, virements, dépenses), mouvements immuables annulés par une ligne
liée, audit."""

import io
from collections import defaultdict
from datetime import date

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone
from openpyxl import load_workbook

from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.finance import cash_outs, expenses
from apps.finance.models import (
    BudgetLine,
    ExpenseCategory,
    ImmutablePaymentError,
    PaymentCancellation,
    TreasuryMovement,
)
from apps.finance.tests.test_api import entries, setup
from apps.finance.tests.test_payments import pay, school_with_fees
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

BUDGET = "/api/budget/"
EXPORT = "/api/budget/export/"
MOVES = "/api/treasury-movements/"


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


@pytest.fixture
def accountant(school):
    return MembershipFactory(school=school, roles=["accountant"]).user


def category(school, actor, name="Atelier") -> ExpenseCategory:
    with use_school(school):
        found = ExpenseCategory.objects.filter(name=name).first()
        return found or expenses.create_category(actor=actor, name=name)


def spend(school, actor, amount, currency="USD", account="bank", *, on=date(2026, 10, 19)):
    """Dépense saisie par `actor` : validée d'office sous le seuil, payée si banque ou Mobile
    Money."""
    with use_school(school):
        expense, _created = expenses.record_expense(
            actor=actor,
            category=category(school, actor),
            beneficiary="Quincaillerie Mapendo",
            reason="Pièces du banc d'essai",
            amount_minor=amount,
            currency=currency,
            spent_on=on,
            account=account,
        )
    return expense


def lines(data, currency="USD", **amounts) -> dict:
    return {
        "academic_year": str(data["year"].pk),
        "currency": currency,
        "lines": [{"category": str(c.pk), "amount_minor": a} for c, a in amounts.values()],
    }


def opening(account, amount, currency="USD") -> dict:
    return {
        "kind": "opening",
        "to_account": account,
        "amount_minor": amount,
        "currency": currency,
        "made_on": "2026-09-01",
    }


def transfer(source, target, amount, currency="USD") -> dict:
    return {**opening(target, amount, currency), "kind": "transfer", "from_account": source}


def balances(report) -> dict:
    return {(a["account"], a["currency"]): a["balance_minor"] for a in report["accounts"]}


def test_a_school_neither_reads_nor_touches_the_budget_of_another(
    api, school, alpha, accountant, other_school, other_head
):
    atelier = category(school, accountant)
    client = api(accountant)
    assert client.put(BUDGET, lines(alpha, a=(atelier, 300000))).status_code == 200
    move = client.post(MOVES, opening("bank", 100000)).json()
    spend(school, accountant, 18500)

    beta = setup(other_school, other_head)
    other = api(other_head, "beta.localhost")
    report = other.get(BUDGET).json()
    assert report["budget"] == [] and report["planned_minor"] == report["spent_minor"] == 0
    assert {a["balance_minor"] for a in report["accounts"]} == {0}
    assert other.get(MOVES).json()["results"] == []
    assert other.post(f"{MOVES}{move['id']}/cancel/", {"reason": "x"}).status_code == 404
    # La catégorie et l'année d'une autre école sont refusées.
    assert other.put(BUDGET, lines(beta, a=(atelier, 1))).status_code == 400
    assert other.get(f"{BUDGET}?academic_year={alpha['year'].pk}").status_code == 400
    sheets = load_workbook(io.BytesIO(other.get(EXPORT).content))
    cells = {c for sheet in sheets for row in sheet.iter_rows(values_only=True) for c in row}
    assert "Atelier" not in cells
    with use_school(other_school):
        assert not BudgetLine.objects.exists() and not TreasuryMovement.objects.exists()


def test_reading_needs_the_reports_right_and_setting_the_budget_its_own(
    api, school, alpha, cashier, accountant
):
    atelier = category(school, accountant)
    promoter = MembershipFactory(school=school, roles=["promoter"]).user
    for path in (BUDGET, EXPORT, MOVES):
        assert api(cashier).get(path).status_code == 403
        assert api(promoter).get(path).status_code == 200
    assert api(promoter).put(BUDGET, lines(alpha, a=(atelier, 1))).status_code == 403
    assert api(promoter).post(MOVES, opening("cash", 1)).status_code == 403
    assert api(accountant).post(MOVES, opening("cash", 1)).status_code == 201


def test_budget_months_and_accounts_count_each_currency_alone(
    api, school, alpha, head, cashier, accountant
):
    atelier = category(school, accountant)
    upkeep = category(school, accountant, "Entretien")
    client = api(accountant)
    client.put(BUDGET, lines(alpha, a=(atelier, 300000), u=(upkeep, 50000)))
    client.put(BUDGET, lines(alpha, "CDF", a=(atelier, 1_000_000)))
    # Sorties : payées et non annulées, datées dans l'année.
    spend(school, accountant, 18500)  # banque, payée
    spend(school, accountant, 4000, account="mobile_money")
    spend(school, accountant, 50000, "CDF")
    cash = spend(school, accountant, 3000, account="cash")  # payée par la caisse ci-dessous
    with use_school(school):
        expenses.cancel_expense(spend(school, accountant, 2000), actor=head, reason="Doublon")
    spend(school, accountant, 25000)  # au-dessus du seuil : en attente
    spend(school, accountant, 1000, on=date(2025, 10, 1))  # autre année
    # Entrées : reçues à la caisse, non annulées.
    pay(school, cashier, alpha["enrollment"], 12000, "USD")
    pay(school, cashier, alpha["enrollment"], 25000, "CDF")
    wrong = pay(school, cashier, alpha["enrollment"], 5000, "USD")
    with use_school(school):
        PaymentCancellation.objects.create(
            payment=wrong,
            receipt_number=wrong.receipt_number,
            reason="Erreur de saisie",
            requested_by=cashier,
            approved_by=head,
        )
        cash_outs.record_cash_out(actor=cashier, expense=cash, received_by="Kahindo")
    # Comptes : départ, virements (un annulé).
    client.post(MOVES, opening("cash", 10000))
    client.post(MOVES, opening("bank", 100000))
    assert client.post(MOVES, opening("bank", 1)).json()["code"] == "opening_balance_exists"
    client.post(MOVES, transfer("cash", "bank", 5000))
    undone = client.post(MOVES, transfer("bank", "mobile_money", 1000)).json()
    client.post(f"{MOVES}{undone['id']}/cancel/", {"reason": "Mauvais compte"})
    same = client.post(MOVES, transfer("bank", "bank", 1))
    assert same.status_code == 400

    report = client.get(f"{BUDGET}?currency=USD").json()
    rows = {r["name"]: (r["planned_minor"], r["spent_minor"]) for r in report["budget"]}
    assert rows == {"Atelier": (300000, 25500), "Entretien": (50000, 0)}
    assert (report["planned_minor"], report["spent_minor"]) == (350000, 25500)
    expected = defaultdict(lambda: [0, 0])
    expected[date(2026, 10, 1)][1] = 25500
    expected[timezone.localdate().replace(day=1)][0] += 12000
    assert {
        date.fromisoformat(m["month"]): [m["receipts_minor"], m["expenses_minor"]]
        for m in report["months"]
    } == dict(expected)
    assert balances(report) == {
        ("cash", "USD"): 10000 + 12000 - 3000 - 5000,
        ("bank", "USD"): 100000 + 5000 - 18500,
        ("mobile_money", "USD"): -4000,
        ("cash", "CDF"): 25000,
        ("bank", "CDF"): -50000,
        ("mobile_money", "CDF"): 0,
    }
    francs = client.get(f"{BUDGET}?currency=CDF").json()
    assert [(r["name"], r["planned_minor"], r["spent_minor"]) for r in francs["budget"]] == [
        ("Atelier", 1_000_000, 50000),
        ("Entretien", 0, 0),
    ]
    # Excel : les mêmes chiffres, en unités de la devise, la devise dans sa colonne.
    book = load_workbook(io.BytesIO(client.get(EXPORT).content))
    budget_rows = list(book.worksheets[0].iter_rows(min_row=2, values_only=True))
    assert ("Atelier", "USD", 3000, 255, 2745, 9) in budget_rows
    assert ("Atelier", "CDF", 1_000_000, 50000, 950000, 5) in budget_rows


def test_the_budget_and_the_movements_are_audited_and_a_movement_never_changes(
    api, school, alpha, accountant
):
    atelier = category(school, accountant)
    client = api(accountant)
    client.put(BUDGET, lines(alpha, a=(atelier, 300000)))
    client.put(BUDGET, lines(alpha, a=(atelier, 300000)))  # rien ne change : pas d'entrée
    client.put(BUDGET, lines(alpha, a=(atelier, 0)))  # zéro retire la ligne
    logged = entries(school, Action.FINANCE_BUDGET_UPDATED)
    assert [(e.before.get("Atelier"), e.after.get("Atelier")) for e in logged] == [
        (0, 300000),
        (300000, 0),
    ]
    with use_school(school):
        assert not BudgetLine.objects.exists()

    move = client.post(MOVES, transfer("cash", "bank", 5000)).json()
    cancel = f"{MOVES}{move['id']}/cancel/"
    assert client.post(cancel, {"reason": "Mauvais montant"}).json()["cancelled"] is True
    assert client.post(cancel, {"reason": "x"}).json()["code"] == "treasury_movement_cancelled"
    assert len(entries(school, Action.FINANCE_TREASURY_MOVEMENT_RECORDED)) == 1
    assert entries(school, Action.FINANCE_TREASURY_MOVEMENT_CANCELLED)[0].after["reason"] == (
        "Mauvais montant"
    )
    with use_school(school):
        kept = TreasuryMovement.objects.get()
        with pytest.raises(ImmutablePaymentError):
            kept.save()
        with pytest.raises(ImmutablePaymentError):
            TreasuryMovement.objects.update(amount_minor=1)
        for sql in (
            "UPDATE finance_treasurymovement SET amount_minor = 1",
            "DELETE FROM finance_treasurymovementcancellation",
        ):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)
        assert TreasuryMovement.objects.count() == 1

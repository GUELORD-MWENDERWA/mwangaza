"""Crédits d'élèves (3.6.1, M14) : isolation entre écoles, droits, crédit d'une réduction sur une
échéance payée (seulement le nouveau trop-payé), annulé avec sa réduction, utilisé sur les
échéances les plus anciennes de sa devise sans paiement ; payé + crédit = argent reçu ; audit.
Surplus d'un paiement hors ligne : `apps/sync/tests/test_sync.py`."""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import (
    CreditAllocation,
    Discount,
    ImmutablePaymentError,
    Payment,
    StudentCredit,
)
from apps.finance.tests.test_api import entries
from apps.finance.tests.test_payments import pay, school_with_fees
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

CREDITS = "/api/student-credits/"


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


def scholarship(school, head, data, percent: int) -> Discount:
    with use_school(school):
        return services.grant_discount(
            data["enrollment"],
            actor=head,
            fee_type=data["fee_type"],
            kind=Discount.Kind.PERCENT,
            percent=percent,
            reason_code=Discount.Reason.SCHOLARSHIP,
            reason="Bourse de la paroisse",
        )


@pytest.fixture
def credit(school, head, cashier, alpha) -> StudentCredit:
    """1re tranche du minerval payée (120,00 $), puis une bourse de 25 % : 30,00 $ de trop."""
    pay(school, cashier, alpha["enrollment"], 12000, "USD")
    scholarship(school, head, alpha, 25)
    with use_school(school):
        return StudentCredit.objects.get()


def usd(school, data) -> tuple[int, int]:
    """(déjà payé, reste) en dollars."""
    with use_school(school):
        balance = services.balance(services.charges_of(data["enrollment"].pk))
    return next(
        (c.paid_minor, c.remaining_minor) for c in balance.currencies if c.currency == "USD"
    )


def minerval(school, data) -> list[tuple[int, int]]:
    """(dû après réductions, payé) de chaque tranche du minerval."""
    with use_school(school):
        charges = services.charges_of(data["enrollment"].pk)
    return [
        (c.amount_minor - c.discount_minor, c.paid_minor)
        for c in charges
        if c.fee_type_id == data["fee_type"].pk
    ]


# Isolation et droits


def test_a_school_neither_reads_nor_uses_the_credits_of_another(api, credit, other_head):
    client = api(other_head, "beta.localhost")
    assert client.get(CREDITS).json()["results"] == []
    assert client.get(f"{CREDITS}{credit.pk}/").status_code == 404
    assert client.post(f"{CREDITS}{credit.pk}/use/").status_code == 404
    assert client.get(f"{CREDITS}summary/").json()["to_process"] == 0


def test_reading_and_using_credits_need_their_rights(api, school, cashier, credit):
    promoter = MembershipFactory(school=school, roles=["promoter"]).user
    accountant = MembershipFactory(school=school, roles=["accountant"]).user
    assert api(cashier).get(CREDITS).status_code == 403
    assert api(promoter).get(f"{CREDITS}{credit.pk}/").status_code == 200
    assert api(promoter).post(f"{CREDITS}{credit.pk}/use/").status_code == 403
    assert api(accountant).post(f"{CREDITS}{credit.pk}/use/").status_code == 200


# Règles


def test_a_discount_on_a_paid_charge_credits_only_the_new_overpayment(
    school, head, cashier, alpha, credit
):
    """Payé 120,00 $, dû 90,00 $ après la bourse : 30,00 $ de crédit, jamais rendus d'office.
    Le payé de la tranche s'arrête à ce qu'elle doit : payé + crédit = argent reçu."""
    assert (credit.origin, credit.amount_minor, credit.currency) == ("discount", 3000, "USD")
    assert minerval(school, alpha)[0] == (9000, 9000)
    assert usd(school, alpha) == (9000, 18000)

    scholarship(school, head, alpha, 10)  # 35 % en tout : dû 78,00 $, 42,00 $ de trop
    with use_school(school):
        amounts = list(StudentCredit.objects.order_by("created_at").values_list("amount_minor"))
    assert amounts == [(3000,), (1200,)]
    created = entries(school, Action.FINANCE_CREDIT_CREATED)
    assert [entry.after["amount_minor"] for entry in created] == [3000, 1200]


def test_using_a_credit_pays_the_oldest_charges_of_its_currency_without_a_payment(
    api, school, head, credit, alpha
):
    response = api(head).post(f"{CREDITS}{credit.pk}/use/")

    assert response.status_code == 200, response.content
    assert response.json()["state"] == "used"
    assert minerval(school, alpha)[:2] == [(9000, 9000), (9000, 3000)]
    assert usd(school, alpha) == (12000, 15000)
    with use_school(school):
        assert Payment.objects.count() == 1
        allocation = CreditAllocation.objects.get()
    [entry] = entries(school, Action.FINANCE_CREDIT_USED)
    assert entry.actor == head and entry.after["amount_minor"] == 3000
    assert api(head).post(f"{CREDITS}{credit.pk}/use/").json()["code"] == "credit_used"

    with use_school(school), pytest.raises(ImmutablePaymentError):
        allocation.save()
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE finance_creditallocation SET amount_minor = 1")


def test_a_credit_larger_than_what_is_owed_keeps_its_rest_to_process(
    api, school, head, cashier, alpha
):
    """Minerval de l'année payé (360,00 $), puis une bourse de 50 % : 180,00 $ de trop et plus
    rien à payer en dollars. Rien n'est converti vers les francs : le crédit reste à traiter."""
    pay(school, cashier, alpha["enrollment"], 36000, "USD")
    scholarship(school, head, alpha, 50)
    with use_school(school):
        credit = StudentCredit.objects.get()

    response = api(head).post(f"{CREDITS}{credit.pk}/use/")

    assert response.json()["code"] == "nothing_owed"
    detail = api(head).get(f"{CREDITS}{credit.pk}/").json()
    assert (detail["state"], detail["remaining_minor"], detail["proposal"]) == (
        "to_process",
        18000,
        [],
    )


def test_revoking_the_discount_voids_its_credit_and_what_it_paid(api, school, head, credit, alpha):
    api(head).post(f"{CREDITS}{credit.pk}/use/")

    with use_school(school):
        services.revoke_discount(credit.source_discount, actor=head, reason="Bourse retirée")
    assert minerval(school, alpha)[:2] == [(12000, 12000), (12000, 0)]
    assert usd(school, alpha) == (12000, 24000)
    assert api(head).get(f"{CREDITS}{credit.pk}/").json()["state"] == "voided"
    [entry] = entries(school, Action.FINANCE_CREDIT_VOIDED)
    assert entry.before["amount_minor"] == 3000

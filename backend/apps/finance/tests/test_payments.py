"""Caisses et paiements (F1-F2) : isolation entre écoles, droits, répartition (devise reçue et
échéances les plus anciennes d'abord, ajustement, conversion), numéro de reçu, double envoi,
paiements immuables, solde après annulation, frais payés qui ne bougent plus."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import (
    CashRegister,
    ImmutablePaymentError,
    Payment,
    PaymentAllocation,
    PaymentCancellation,
    StudentCharge,
)
from apps.finance.services import Installment, Part, Scope
from apps.finance.tests.test_api import entries, field_code, setup
from apps.finance.tests.test_balance import at
from apps.finance.tests.test_charges import charges, once, rule
from apps.schools import organisation
from apps.students import services as students
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

REGISTERS = "/api/cash-registers/"
SESSIONS = "/api/cash-sessions/"
PAYMENTS = "/api/payments/"
BALANCE = "/api/student-charges/balance/"


def school_with_fees(school, actor, *, rate: str | None = "2850") -> dict:
    """`setup` (minerval de 3e : 3 x 120,00 $ aux 15/10, 15/01, 15/04), fonctionnement
    25 000 FC au 30/09, le taux de l'année, la caisse C1 et un élève inscrit en 3e."""
    data = setup(school, actor)
    with use_school(school):
        rule(actor, data, "Fonctionnement", "CDF", once("Fonctionnement", 25000))
        if rate:
            services.set_exchange_rate(actor=actor, academic_year=data["year"], rate=Decimal(rate))
        register = services.create_cash_register(actor=actor, name="Caisse 1", code="C1")
    student = enrolled(school, actor, data["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
    return {**data, "register": register, "enrollment": enrollment}


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


def pay(school, cashier, enrollment, amount: int, currency: str, code="C1", **fields) -> Payment:
    with use_school(school):
        if services.open_session_of(cashier) is None:
            register = CashRegister.objects.get(code=code)
            services.open_cash_session(actor=cashier, cash_register=register)
        payment, _created = services.record_payment(
            enrollment,
            actor=cashier,
            received_amount_minor=amount,
            received_currency=currency,
            **fields,
        )
    return payment


def lines(school, payment) -> list[tuple]:
    with use_school(school):
        allocations = payment.allocations.select_related("student_charge")
        return [
            (a.student_charge.label, a.received_minor, a.amount_minor)
            for a in allocations.order_by("student_charge__due_on")
        ]


def charge(school, enrollment, label: str) -> StudentCharge:
    with use_school(school):
        return StudentCharge.objects.get(enrollment=enrollment, label=label)


def body(enrollment, amount: int, currency: str, **fields) -> dict:
    return {
        "enrollment": str(enrollment.pk),
        "received_amount_minor": amount,
        "received_currency": currency,
        **fields,
    }


def ids(response) -> set[str]:
    assert response.status_code == 200, response.content
    return {item["id"] for item in response.json()["results"]}


# Isolation et droits


def test_a_school_neither_reads_nor_uses_the_registers_sessions_and_payments_of_another(
    api, school, other_school, head, other_head, cashier, alpha
):
    payment = pay(school, cashier, alpha["enrollment"], 12000, "USD")
    beta = school_with_fees(other_school, other_head)
    accountant = MembershipFactory(school=other_school, roles=["accountant"]).user
    other = api(accountant, host="beta.localhost")

    assert ids(other.get(PAYMENTS)) == set()
    assert other.get(f"{PAYMENTS}{payment.pk}/").status_code == 404
    registers = {item["id"] for item in other.get(REGISTERS).json()}
    assert registers == {str(beta["register"].pk)}
    assert other.patch(f"{REGISTERS}{alpha['register'].pk}/", {"name": "X"}).status_code == 404
    opened = other.post(SESSIONS, {"cash_register": str(alpha["register"].pk)})
    assert field_code(opened, "cash_register") == "does_not_exist"
    assert other.post(SESSIONS, {"cash_register": str(beta["register"].pk)}).status_code == 201
    paid = other.post(PAYMENTS, body(alpha["enrollment"], 1000, "USD"))
    assert field_code(paid, "enrollment") == "does_not_exist"
    with use_school(school):
        assert Payment.objects.count() == 1


def test_registers_sessions_and_payments_need_their_rights(api, school, head, cashier, alpha):
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    as_secretary = api(secretary)
    assert as_secretary.get(REGISTERS).status_code == 403
    assert as_secretary.get(PAYMENTS).status_code == 403
    register = {"cash_register": str(alpha["register"].pk)}
    assert as_secretary.post(SESSIONS, register).status_code == 403

    as_cashier, as_head = api(cashier), api(head)
    assert as_cashier.post(REGISTERS, {"name": "Caisse 2", "code": "C2"}).status_code == 403
    assert as_head.post(REGISTERS, {"name": "Caisse 2", "code": "C2"}).status_code == 201
    # Le préfet lit les rapports mais n'encaisse pas.
    assert as_head.post(SESSIONS, register).status_code == 403
    assert as_head.post(PAYMENTS, body(alpha["enrollment"], 1000, "USD")).status_code == 403

    # Un caissier ne voit que les paiements de ses sessions ; les rapports les voient tous.
    other_cashier = MembershipFactory(school=school, roles=["cashier"]).user
    mine = pay(school, cashier, alpha["enrollment"], 12000, "USD")
    theirs = pay(school, other_cashier, alpha["enrollment"], 5000, "CDF", code="C2")
    assert ids(as_cashier.get(PAYMENTS)) == {str(mine.pk)}
    assert as_cashier.get(f"{PAYMENTS}{theirs.pk}/").status_code == 404
    assert ids(as_head.get(PAYMENTS)) == {str(mine.pk), str(theirs.pk)}


# Caisses et sessions (M13)


def test_one_open_session_per_register_and_per_cashier(api, school, head, cashier, alpha):
    as_cashier = api(cashier)
    enrollment = alpha["enrollment"]
    refused = as_cashier.post(PAYMENTS, body(enrollment, 1000, "USD"))
    assert (refused.status_code, refused.json()["code"]) == (409, "no_open_session")
    second = api(head).post(REGISTERS, {"name": "Caisse 2", "code": "C2"}).json()

    session_id = str(uuid7())
    first = {"id": session_id, "cash_register": str(alpha["register"].pk)}
    assert as_cashier.post(SESSIONS, first).status_code == 201
    # Le même envoi répété rend la même session.
    assert as_cashier.post(SESSIONS, first).json()["id"] == session_id
    again = as_cashier.post(SESSIONS, {"cash_register": second["id"]})
    assert again.json()["code"] == "session_already_open"
    # « Libre » ou « Occupée » à l'ouverture : qui l'a ouverte, depuis quand.
    states = {item["code"]: item["open_session"] for item in as_cashier.get(REGISTERS).json()}
    assert states["C2"] is None
    assert (states["C1"]["id"], states["C1"]["cashier"]["id"]) == (session_id, str(cashier.pk))

    other = api(MembershipFactory(school=school, roles=["cashier"]).user)
    busy = other.post(SESSIONS, {"cash_register": str(alpha["register"].pk)})
    assert (busy.status_code, busy.json()["code"]) == (409, "cash_register_busy")
    assert api(head).patch(f"{REGISTERS}{second['id']}/", {"is_active": False}).status_code == 200
    closed = other.post(SESSIONS, {"cash_register": second["id"]})
    assert closed.json()["code"] == "cash_register_inactive"

    [updated] = entries(school, Action.FINANCE_CASH_REGISTER_UPDATED)
    assert (updated.before, updated.after) == ({"is_active": True}, {"is_active": False})
    assert len(entries(school, Action.FINANCE_CASH_SESSION_OPENED)) == 1


# Répartition, conversion, reçu (F2)


def test_default_allocation_pays_the_oldest_charges_in_the_received_currency_first(
    api, school, cashier, alpha
):
    as_cashier = api(cashier)
    enrollment = alpha["enrollment"]
    as_cashier.post(SESSIONS, {"cash_register": str(alpha["register"].pk)})

    dollars = as_cashier.post(PAYMENTS, body(enrollment, 15000, "USD"))
    assert dollars.status_code == 201, dollars.content
    dollars = dollars.json()
    assert (dollars["receipt_number"], dollars["rate_used"]) == (
        "ALPHA-C1-26-000001",
        "2850.000000",
    )
    # Les francs ne sont pas touchés par un paiement en dollars sans conversion.
    assert [(a["label"], a["amount_minor"]) for a in dollars["allocations"]] == [
        ("1re tranche", 12000),
        ("2e tranche", 3000),
    ]
    francs = as_cashier.post(PAYMENTS, body(enrollment, 10000, "CDF")).json()
    assert francs["receipt_number"] == "ALPHA-C1-26-000002"
    assert [(a["label"], a["amount_minor"]) for a in francs["allocations"]] == [
        ("Fonctionnement", 10000)
    ]

    balance = as_cashier.get(f"{BALANCE}?enrollment={enrollment.pk}").json()
    usd, cdf = balance["currencies"]
    assert (usd["paid_minor"], usd["remaining_minor"]) == (15000, 21000)
    assert (cdf["paid_minor"], cdf["remaining_minor"]) == (10000, 15000)
    current = as_cashier.get(f"{SESSIONS}current/").json()
    assert current["totals"] == [
        {"currency": "USD", "amount_minor": 15000, "count": 1},
        {"currency": "CDF", "amount_minor": 10000, "count": 1},
    ]
    assert (current["rate"], current["rate_is_fallback"]) == ("2850.000000", False)

    recorded = entries(school, Action.FINANCE_PAYMENT_RECORDED)[0]
    assert recorded.actor == cashier
    assert recorded.after["allocations"] == [
        {"fee": "Minerval — 1re tranche", "amount_minor": 12000, "currency": "USD"},
        {"fee": "Minerval — 2e tranche", "amount_minor": 3000, "currency": "USD"},
    ]


def test_conversion_divides_francs_multiplies_dollars_and_rounds_half_up(school, cashier, alpha):
    enrollment = alpha["enrollment"]
    tranche = charge(school, enrollment, "1re tranche")
    operating = charge(school, enrollment, "Fonctionnement")
    # 100 000 FC ÷ 2 850 = 35,087… $ → 35,09 $.
    francs = pay(school, cashier, enrollment, 100000, "CDF", parts=[Part(tranche.pk, 100000)])
    assert lines(school, francs) == [("1re tranche", 100000, 3509)]
    # 5,55 $ x 2 850 = 15 817,5 FC → 15 818 FC.
    dollars = pay(school, cashier, enrollment, 555, "USD", parts=[Part(operating.pk, 555)])
    assert lines(school, dollars) == [("Fonctionnement", 555, 15818)]
    # Par défaut avec conversion : devise reçue d'abord (reste 9 182 FC), puis l'autre devise ;
    # 40 818 FC ÷ 2 850 = 14,322… $ → 14,32 $.
    both = pay(school, cashier, enrollment, 50000, "CDF", convert=True)
    assert lines(school, both) == [("Fonctionnement", 9182, 9182), ("1re tranche", 40818, 1432)]


def test_a_wrong_allocation_or_more_than_owed_is_refused_and_nothing_is_written(
    api, school, cashier, alpha
):
    as_cashier = api(cashier)
    enrollment = alpha["enrollment"]
    tranche = str(charge(school, enrollment, "1re tranche").pk)
    as_cashier.post(SESSIONS, {"cash_register": str(alpha["register"].pk)})

    # Toute l'année en dollars : 360,00 $ ; au-delà, le caissier rend la monnaie.
    too_much = as_cashier.post(PAYMENTS, body(enrollment, 36001, "USD"))
    assert field_code(too_much, "received_amount_minor") == "more_than_due"
    parts = [{"student_charge": tranche, "received_minor": 9000}]
    short = as_cashier.post(PAYMENTS, body(enrollment, 10000, "USD", allocations=parts))
    assert field_code(short, "allocations") == "allocations_total_mismatch"
    parts = [{"student_charge": tranche, "received_minor": 13000}]
    over = as_cashier.post(PAYMENTS, body(enrollment, 13000, "USD", allocations=parts))
    assert field_code(over, "allocations.0.received_minor") == "not_within_due"
    parts = [{"student_charge": str(uuid7()), "received_minor": 1000}]
    unknown = as_cashier.post(PAYMENTS, body(enrollment, 1000, "USD", allocations=parts))
    assert field_code(unknown, "allocations.0.student_charge") == "not_owed"

    with use_school(school):
        assert not Payment.objects.exists()
    assert entries(school, Action.FINANCE_PAYMENT_RECORDED) == []


def test_the_same_payment_sent_twice_is_recorded_once(api, school, cashier, alpha):
    as_cashier = api(cashier)
    as_cashier.post(SESSIONS, {"cash_register": str(alpha["register"].pk)})
    sent = body(alpha["enrollment"], 12000, "USD", id=str(uuid7()))

    first = as_cashier.post(PAYMENTS, sent)
    again = as_cashier.post(PAYMENTS, sent)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json()
    with use_school(school):
        assert Payment.objects.count() == 1
    assert len(entries(school, Action.FINANCE_PAYMENT_RECORDED)) == 1
    other = as_cashier.post(PAYMENTS, {**sent, "received_amount_minor": 5000})
    assert (other.status_code, other.json()["code"]) == (409, "payment_id_taken")


def test_without_a_rate_this_year_the_last_known_one_is_used_and_flagged(
    api, school, head, cashier
):
    data = school_with_fees(school, head, rate=None)
    as_cashier = api(cashier)
    as_cashier.post(SESSIONS, {"cash_register": str(data["register"].pk)})
    sent = body(data["enrollment"], 12000, "USD")
    refused = as_cashier.post(PAYMENTS, sent)
    assert (refused.status_code, refused.json()["code"]) == (409, "no_exchange_rate")

    with use_school(school):
        last_year = organisation.create_year(
            actor=head, starts_on=date(2025, 9, 1), ends_on=date(2026, 7, 2)
        )
        services.set_exchange_rate(actor=head, academic_year=last_year, rate=Decimal("2800"))
    current = as_cashier.get(f"{SESSIONS}current/").json()
    assert (current["rate"], current["rate_is_fallback"]) == ("2800.000000", True)
    assert as_cashier.post(PAYMENTS, sent).json()["rate_used"] == "2800.000000"


# Paiements immuables, annulation


def test_payments_and_their_allocations_are_never_changed_or_deleted(school, cashier, alpha):
    payment = pay(school, cashier, alpha["enrollment"], 12000, "USD")
    with use_school(school):
        allocation = payment.allocations.get()
        for item in (payment, allocation):
            with pytest.raises(ImmutablePaymentError):
                item.save()
            with pytest.raises(ImmutablePaymentError):
                item.delete()
        with pytest.raises(ImmutablePaymentError):
            Payment.objects.update(note="modifié")
        with pytest.raises(ImmutablePaymentError):
            PaymentAllocation.objects.all().delete()
    for table in ("finance_payment", "finance_paymentallocation"):
        for sql in (f"UPDATE {table} SET updated_at = now()", f"DELETE FROM {table}"):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)
    assert PaymentAllocation.all_schools.get(pk=allocation.pk).amount_minor == 12000


def test_a_cancelled_payment_no_longer_counts_in_the_balance(
    api, monkeypatch, school, head, cashier, alpha
):
    at(monkeypatch, "2026-10-20")
    enrollment = alpha["enrollment"]
    payment = pay(school, cashier, enrollment, 6000, "USD")
    as_cashier = api(cashier)
    balance = as_cashier.get(f"{BALANCE}?enrollment={enrollment.pk}").json()
    # 1re tranche échue et payée à moitié : situation partielle.
    assert (balance["situation"], balance["currencies"][0]["overdue_minor"]) == ("partial", 6000)

    with use_school(school):
        PaymentCancellation.objects.create(
            payment=payment, reason="Erreur d'élève", requested_by=cashier, approved_by=head
        )
    balance = as_cashier.get(f"{BALANCE}?enrollment={enrollment.pk}").json()
    usd = balance["currencies"][0]
    assert (balance["situation"], usd["paid_minor"], usd["overdue_minor"]) == ("overdue", 0, 12000)
    assert as_cashier.get(f"{PAYMENTS}{payment.pk}/").json()["cancelled"] is True
    assert as_cashier.get(f"{SESSIONS}current/").json()["totals"] == []


# Frais payés : ils ne bougent plus (changement de classe, barème, échéancier)


def test_a_paid_charge_stays_and_holds_its_place_when_the_rule_or_the_class_changes(
    school, head, cashier, alpha
):
    enrollment = alpha["enrollment"]
    pay(school, cashier, enrollment, 5000, "USD")
    new_rule = [
        Installment(label, 15000, date.fromisoformat(day))
        for label, day in (
            ("1re tranche", "2026-10-15"),
            ("2e tranche", "2027-01-15"),
            ("3e tranche", "2027-04-15"),
        )
    ]
    with use_school(school):
        services.update_fee_rule(
            alpha["rule"],
            actor=head,
            currency="USD",
            total_amount_minor=45000,
            schedule_kind="installments",
            installments=new_rule,
            scope=Scope(level=alpha["level"]),
        )
        minerval = {c for c in charges(enrollment) if c[0] == "Minerval"}
        assert minerval == {
            ("Minerval", "1re tranche", 12000, "USD"),
            ("Minerval", "2e tranche", 15000, "USD"),
            ("Minerval", "3e tranche", 15000, "USD"),
        }

        # En 4e (3 x 130,00 $), la 1re tranche payée tient la place de celle de la 4e.
        fourth = organisation.create_class_group(
            actor=head,
            academic_year=alpha["year"],
            level=alpha["other_level"],
            track=alpha["track"],
            section="A",
            capacity=45,
        )
        services.create_fee_rule(
            actor=head,
            academic_year=alpha["year"],
            fee_type=alpha["fee_type"],
            currency="USD",
            total_amount_minor=39000,
            schedule_kind="installments",
            installments=[Installment(i.label, 13000, i.due_on) for i in new_rule],
            scope=Scope(level=alpha["other_level"]),
        )
        students.update_enrollment(enrollment, actor=head, class_group=fourth)
        minerval = {c for c in charges(enrollment) if c[0] == "Minerval"}
        assert minerval == {
            ("Minerval", "1re tranche", 12000, "USD"),
            ("Minerval", "2e tranche", 13000, "USD"),
            ("Minerval", "3e tranche", 13000, "USD"),
        }


def test_a_custom_schedule_only_replaces_the_charges_without_any_payment(
    school, head, cashier, alpha
):
    enrollment = alpha["enrollment"]
    pay(school, cashier, enrollment, 5000, "USD")
    versements = [
        Installment("Versement 1", 12000, date(2026, 11, 15)),
        Installment("Versement 2", 12000, date(2027, 2, 15)),
    ]
    with use_school(school):
        services.reschedule_charges(
            enrollment,
            actor=head,
            fee_type=alpha["fee_type"],
            installments=versements,
            reason="Arrangement avec la famille",
            parent_signed=True,
        )
        minerval = {c for c in charges(enrollment) if c[0] == "Minerval"}
        assert minerval == {
            ("Minerval", "1re tranche", 12000, "USD"),
            ("Minerval", "Versement 1", 12000, "USD"),
            ("Minerval", "Versement 2", 12000, "USD"),
        }

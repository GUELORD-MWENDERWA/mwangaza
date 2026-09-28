"""Solde et retards d'un élève (2.7) : par devise, après réductions (une réduction retirée n'a
plus d'effet), frais retirés ignorés, en retard dès le lendemain de l'échéance ; frais de l'année
sur la fiche d'inscription et situation des paiements sur la liste de classe ; droits et
isolation entre écoles."""

import io
from datetime import date

import openpyxl
import pytest

from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import StudentCharge
from apps.finance.tests.test_api import setup
from apps.finance.tests.test_charges import CHARGES, of, once, rule
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

BALANCE = f"{CHARGES}balance/"
ENROLLMENTS = "/api/enrollments/"
NBSP = "\xa0"


@pytest.fixture
def alpha(school, head):
    return setup(school, head)


@pytest.fixture
def beta(other_school, other_head):
    return setup(other_school, other_head)


@pytest.fixture
def owing(school, head, alpha):
    """Élève de 3e : minerval en 3 tranches de 120,00 $ (15/10, 15/01, 15/04) réduit de 25 %,
    fonctionnement 25 000 FC au 30/09 avec une réduction de 5 000 FC retirée, atelier 40,00 $
    au 15/09 retiré (changement de classe par exemple)."""
    with use_school(school):
        operating = rule(head, alpha, "Fonctionnement", "CDF", once("Fonctionnement", 25000))
        workshop = rule(head, alpha, "Atelier", "USD", once("Atelier", 4000, "2026-09-15"))
    student = enrolled(school, head, alpha["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
        grant = {"actor": head, "reason_code": "scholarship", "reason": "Bourse de la paroisse"}
        services.grant_discount(
            enrollment, fee_type=alpha["fee_type"], kind="percent", percent=25, **grant
        )
        revoked = services.grant_discount(
            enrollment, fee_type=operating.fee_type, kind="amount", amount_minor=5000, **grant
        )
        services.revoke_discount(revoked, actor=head, reason="Accordée par erreur")
        StudentCharge.objects.filter(enrollment=enrollment, fee_type=workshop.fee_type).update(
            status=StudentCharge.Status.REMOVED
        )
    return enrollment


def at(monkeypatch, day: str) -> None:
    monkeypatch.setattr(services, "today", lambda: date.fromisoformat(day))


def test_balance_is_per_currency_after_discounts_and_overdue_the_day_after_the_due_date(
    monkeypatch, school, head, alpha, owing
):
    with use_school(school):
        at(monkeypatch, "2026-10-15")
        charges = services.charges_of(owing.pk)
        balance = services.balance(charges)
        # Le jour de l'échéance, la 1re tranche n'est pas encore en retard.
        assert [(c.label, c.remaining_minor, c.state) for c in charges if c.state] == [
            ("Fonctionnement", 25000, "overdue"),
            ("1re tranche", 9000, "upcoming"),
            ("2e tranche", 9000, "upcoming"),
            ("3e tranche", 9000, "upcoming"),
        ]
        assert balance.next_due_on == date(2026, 10, 15)
        assert [
            (b.currency, b.total_minor, b.paid_minor, b.remaining_minor, b.overdue_minor)
            for b in balance.currencies
        ] == [("USD", 27000, 0, 27000, 0), ("CDF", 25000, 0, 25000, 25000)]

        at(monkeypatch, "2026-10-16")
        balance = services.balance(services.charges_of(owing.pk))
        assert (balance.situation, balance.next_due_on) == ("overdue", date(2027, 1, 15))
        assert [(b.overdue_minor, b.next_due_minor) for b in balance.currencies] == [
            (9000, 9000),
            (25000, 0),
        ]

        # Exonération totale du fonctionnement : plus rien à payer, donc plus en retard.
        services.grant_discount(
            owing,
            actor=head,
            fee_type=StudentCharge.objects.get(enrollment=owing, label="Fonctionnement").fee_type,
            kind="percent",
            percent=100,
            reason_code="waiver",
            reason="Enfant du personnel",
        )
        charges = services.charges_of(owing.pk)
        operating = next(c for c in charges if c.label == "Fonctionnement")
        assert (operating.remaining_minor, operating.state) == (0, "paid")
        cdf = services.balance(charges).currencies[1]
        assert (cdf.total_minor, cdf.remaining_minor, cdf.overdue_minor) == (0, 0, 0)


def test_balance_is_read_with_a_finance_right_in_the_students_school_only(
    monkeypatch, api, school, head, other_head, alpha, beta, owing
):
    at(monkeypatch, "2026-10-16")
    response = api(head).get(BALANCE, enrollment=str(owing.pk))
    assert response.status_code == 200
    assert response.json() == {
        "situation": "overdue",
        "next_due_on": "2027-01-15",
        "currencies": [
            {
                "currency": "USD",
                "total_minor": 27000,
                "paid_minor": 0,
                "remaining_minor": 27000,
                "overdue_minor": 9000,
                "next_due_minor": 9000,
            },
            {
                "currency": "CDF",
                "total_minor": 25000,
                "paid_minor": 0,
                "remaining_minor": 25000,
                "overdue_minor": 25000,
                "next_due_minor": 0,
            },
        ],
    }
    first = api(head).get(of(owing)).json()[0]
    assert (first["label"], first["paid_minor"], first["remaining_minor"], first["state"]) == (
        "Atelier",
        0,
        0,
        None,
    )

    # Secrétaire : voit l'élève, pas son argent. Autre école : rien sur cet élève.
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    assert api(secretary).get(BALANCE, enrollment=str(owing.pk)).status_code == 403
    other = api(other_head, host="beta.localhost").get(BALANCE, enrollment=str(owing.pk))
    assert other.status_code == 200 and other.json()["currencies"] == []


def test_registration_form_lists_the_fees_of_the_year_after_discounts_for_finance_rights(
    api, school, owing
):
    form = f"{ENROLLMENTS}{owing.pk}/form/"
    accountant = MembershipFactory(school=school, roles=["accountant"]).user
    preview = api(accountant).get(form, output="html", fees="true").content.decode()

    # Après réductions, groupés par devise ; le frais retiré n'y est pas.
    assert f"270,00{NBSP}$" in preview and "15/10, 15/01, 15/04" in preview
    assert f"25{NBSP}000{NBSP}FC" in preview and "Atelier" not in preview
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    assert api(secretary).get(form, output="html").status_code == 200
    assert api(secretary).get(form, output="html", fees="true").status_code == 403


def test_class_list_shows_what_is_overdue_only_with_the_reports_right(
    monkeypatch, api, school, head, cashier, alpha, owing
):
    at(monkeypatch, "2026-10-16")
    enrolled(school, head, alpha["group"], last_name="Paluku")
    query = {"class_group": str(alpha["group"].pk), "columns": ["payments"]}
    content = api(head).get(f"{ENROLLMENTS}class-list/", output="xlsx", **query).content
    rows = openpyxl.load_workbook(io.BytesIO(content)).active.iter_rows(values_only=True)
    header, *students = rows

    assert len(header) == 3
    # Le second élève doit, sans réduction, la 1re tranche, l'atelier et le fonctionnement.
    assert [row[2].split(": ")[-1] for row in students] == [
        f"90,00{NBSP}$ + 25{NBSP}000{NBSP}FC",
        f"160,00{NBSP}$ + 25{NBSP}000{NBSP}FC",
    ]
    assert api(cashier).get(f"{ENROLLMENTS}class-list/", **query).status_code == 403

"""Tableau de bord du directeur (G3) : droits, isolation entre écoles, montants par devise sans
les paiements annulés, recouvrement avec les francs au taux de l'année, alertes selon les seuils
de l'école (M5)."""

from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from apps.core.tenancy import use_school
from apps.finance import dashboard, services
from apps.finance.models import CashSession
from apps.finance.tests.test_balance import at
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.schools.services import update_school
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

DASHBOARD = "/api/dashboard/"


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


@pytest.fixture
def paid(school, head, cashier, alpha):
    """Minerval 3 x 120,00 $ dès le 15/10, fonctionnement 25 000 FC au 30/09 : Kasereka n'a rien
    payé ; Amani (bourse de 25 % sur le minerval, une fille) a payé 10 000 FC, puis 90,00 $
    annulés ; Paluku a payé 120,00 $ et 25 000 FC."""
    group = alpha["group"]
    students = [
        enrolled(school, head, group, last_name="Amani", sex="F"),
        enrolled(school, head, group, last_name="Paluku"),
    ]
    with use_school(school):
        amani, paluku = (student.enrollments.get() for student in students)
        services.grant_discount(
            amani,
            actor=head,
            fee_type=alpha["fee_type"],
            kind="percent",
            percent=25,
            reason_code="scholarship",
            reason="Bourse de la paroisse",
        )
    pay(school, cashier, amani, 10000, "CDF")
    cancelled = pay(school, cashier, amani, 9000, "USD")
    pay(school, cashier, paluku, 12000, "USD")
    pay(school, cashier, paluku, 25000, "CDF")
    with use_school(school):
        request, _created = services.request_cancellation(
            cancelled, actor=cashier, reason="Mauvais élève sélectionné (homonyme)"
        )
        services.approve_cancellation(request, actor=head)
    return alpha


def amounts(rows: list[dict], field="amount_minor") -> list[tuple]:
    return [(row["currency"], row[field]) for row in rows]


def test_only_reports_readers_see_the_dashboard_of_their_own_school(
    api, school, other_school, head, cashier, other_head, paid
):
    promoter = MembershipFactory(school=school, roles=["promoter"]).user
    assert api(cashier).get(DASHBOARD).status_code == 403
    assert api(promoter).get(DASHBOARD).status_code == 200

    # L'école beta, avec ses propres frais et un paiement, ne voit rien de l'école alpha.
    beta = school_with_fees(other_school, other_head)
    beta_cashier = MembershipFactory(school=other_school, roles=["cashier"]).user
    pay(other_school, beta_cashier, beta["enrollment"], 5000, "USD")
    seen = api(other_head, host="beta.localhost").get(DASHBOARD).json()
    assert amounts(seen["today"]) == [("USD", 5000), ("CDF", 0)]
    assert seen["enrolled"] == 1
    assert [row["id"] for row in seen["classes"]] == [str(beta["group"].pk)]
    assert [row["receipt_number"][:4] for row in seen["recent_payments"]] == ["BETA"]
    assert seen["alerts"]["pending_cancellations"] == 0
    assert api(head).get(DASHBOARD).json()["enrolled"] == 3


def test_amounts_are_per_currency_without_cancelled_payments_and_recovery_counts_francs_at_the_rate(
    monkeypatch, api, head, paid
):
    data = api(head).get(DASHBOARD).json()

    assert [(row["currency"], row["amount_minor"], row["count"]) for row in data["today"]] == [
        ("USD", 12000, 1),
        ("CDF", 35000, 2),
    ]
    assert amounts(data["month"]) == [("USD", 12000), ("CDF", 35000)]
    assert amounts(data["daily"][-1]["amounts"]) == [("USD", 12000), ("CDF", 35000)]
    assert len(data["daily"]) == dashboard.DAYS
    assert [p["received_amount_minor"] for p in data["recent_payments"]] == [25000, 12000, 10000]
    assert (data["enrolled"], data["male"], data["female"]) == (3, 2, 1)

    # Le 16/10 : fonctionnement (30/09) et 1re tranche (15/10) échus. Dû 330,00 $ et 75 000 FC,
    # payé 120,00 $ et 35 000 FC ; au taux de 2 850 FC : 37 % (ni 36 % en dollars seuls, ni
    # 43 % en additionnant dollars et francs).
    at(monkeypatch, "2026-10-16")
    data = api(head).get(DASHBOARD).json()
    assert amounts(data["overdue"]) == [("USD", 21000), ("CDF", 40000)]
    assert data["overdue_students"] == 2
    assert data["recovery_percent"] == 37
    assert [(row["enrolled"], row["recovery_percent"]) for row in data["classes"]] == [(3, 37)]


def test_alerts_follow_the_school_thresholds(school, head, cashier, paid):
    day = timezone.localdate()
    morning = timezone.make_aware(datetime.combine(day, time(10)))
    with use_school(school):
        session = services.open_session_of(cashier)
        payments = list(session.payments.filter(cancellation__isnull=True))
        for payment in payments[:2]:
            services.request_cancellation(payment, actor=cashier, reason="Erreur de saisie")
        alerts = dashboard.school_alerts(day, morning)
        # Deux demandes en attente ; avec celle déjà validée, 3 dans la journée : pas plus de 3.
        # Caisse ouverte ce matin : pas encore en retard à 10 h (clôture à 18 h).
        assert alerts["pending_cancellations"] == 2
        assert (alerts["cancellations"], alerts["unclosed"]) == ([], [])

        update_school(
            school, actor=head, alerts={"cancellations_per_day": 1, "closing_time": time(9)}
        )
        alerts = dashboard.school_alerts(day, morning)
        assert [(row["cashier"], row["count"]) for row in alerts["cancellations"]] == [(cashier, 3)]
        assert alerts["unclosed"] == [session]

        # Clôturée avec 15,00 $ de moins que l'attendu : signalée au-delà de 10 $, pas de 20 $.
        CashSession.objects.filter(pk=session.pk).update(opened_at=morning - timedelta(days=1))
        summary = services.closing_summary(session)
        expected = {row["currency"]: row["expected_minor"] for row in summary["currencies"]}
        services.close_cash_session(
            session,
            actor=cashier,
            counted={**expected, "USD": expected["USD"] - 1500},
            note="Billet de 20 $ refusé",
        )
        alerts = dashboard.school_alerts(day, morning)
        assert alerts["unclosed"] == []
        assert [(line.currency, line.difference_minor) for line in alerts["differences"]] == [
            ("USD", -1500)
        ]
        update_school(school, actor=head, alerts={"difference_minor": {"USD": 2000}})
        assert dashboard.school_alerts(day, morning)["differences"] == []

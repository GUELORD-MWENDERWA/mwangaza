"""Notifications à heure fixe (5.6.2) : relances aux parents de l'école qui les a activées
(échéance proche, retard), caisse encore ouverte pour ceux qui lisent les rapports, purge. Rien ne
sort de l'école, rien ne part deux fois le même jour, les montants sont ceux qui restent dus."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.core.money import format_amount
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.tests.test_balance import at
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.notifications import push, scheduled
from apps.notifications.models import Notification, ScheduledRun
from apps.notifications.tests.test_events import parent_of, received
from apps.students.models import Family
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

Kind = Notification.Kind
REMINDERS = [Kind.PAYMENT_DUE, Kind.PAYMENT_OVERDUE]
# Lundi 12 octobre, 9 h à Goma : la 1re tranche (120,00 $) tombe le 15, le fonctionnement
# (25 000 FC) est échu depuis le 30 septembre.
MORNING = datetime(2026, 10, 12, 9, 0, tzinfo=ZoneInfo("Africa/Lubumbashi"))


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


def enable_reminders(school, **values) -> None:
    school.settings = {**school.settings, "reminders": {"enabled": True, **values}}
    school.save()


def tick(monkeypatch, now: datetime) -> None:
    """Un passage à ce moment-là : le calcul des retards et la date des notifications créées le
    suivent (elles sont écrites à l'heure réelle)."""
    at(monkeypatch, now.date().isoformat())
    known = set(Notification.all_schools.values_list("pk", flat=True))
    scheduled.tick(now)
    Notification.all_schools.exclude(pk__in=known).update(created_at=now)


def test_reminders_go_once_to_the_parents_of_the_school_that_enabled_them(
    monkeypatch, school, other_school, head, other_head, alpha
):
    student = alpha["enrollment"].student
    parent = parent_of(school, alpha["enrollment"], language="en")
    beta = school_with_fees(other_school, other_head)
    parent_of(other_school, beta["enrollment"])
    enable_reminders(school)

    tick(monkeypatch, MORNING - timedelta(hours=2))
    assert received() == []  # 7 h : pas encore l'heure
    tick(monkeypatch, MORNING)
    tick(monkeypatch, MORNING + timedelta(minutes=15))

    # beta n'a pas activé les relances : rien pour sa famille, rien de beta chez alpha.
    due, overdue = received()
    assert {(n.user, n.school, n.app) for n in (due, overdue)} == {(parent, school, "portail")}
    assert (due.kind, overdue.kind) == (Kind.PAYMENT_DUE, Kind.PAYMENT_OVERDUE)
    assert due.title == f"Payment due on 15 October: {format_amount(12000, 'USD')}"
    assert overdue.title == f"Late payment: {format_amount(25000, 'CDF')}"
    assert str(student) in due.body and "30 September" in overdue.body
    assert due.url == overdue.url == f"/children/{student.pk}"

    # Le lendemain : l'échéance n'est plus à trois jours, le retard a été rappelé hier.
    tick(monkeypatch, MORNING + timedelta(days=1))
    assert len(received()) == 2
    # Sept jours après : relance du retard, 1re tranche comprise, sans additionner les devises.
    tick(monkeypatch, MORNING + timedelta(days=7))
    assert received()[-1].title == (
        f"Late payment: {format_amount(12000, 'USD')} + {format_amount(25000, 'CDF')}"
    )
    assert len(received()) == 3


def test_reminders_tell_what_is_still_owed(monkeypatch, school, head, cashier, alpha):
    enrollment = alpha["enrollment"]
    parent = parent_of(school, enrollment)
    enable_reminders(school, days_before=5)
    # Fonctionnement soldé, 50,00 $ sur la 1re tranche.
    pay(school, cashier, enrollment, 25000, "CDF")
    pay(school, cashier, enrollment, 5000, "USD")

    # Le 10, cinq jours avant l'échéance (réglage de l'école) : le reste de la tranche, et
    # aucun retard puisque le fonctionnement est payé.
    tick(monkeypatch, MORNING - timedelta(days=2))
    [due] = received(kind__in=REMINDERS)
    assert (due.user, due.kind) == (parent, Kind.PAYMENT_DUE)
    assert format_amount(7000, "USD") in due.title

    # Accès au portail suspendu par l'école : plus de relance, même la tranche une fois échue.
    with use_school(school):
        Family.objects.update(portal_suspended_at=timezone.now())
    tick(monkeypatch, MORNING + timedelta(days=7))
    assert len(received(kind__in=REMINDERS)) == 1


def test_open_register_alerts_those_who_read_the_reports_once_at_closing_time(
    monkeypatch, school, other_school, head, other_head, cashier, alpha
):
    accountant = MembershipFactory(school=school, roles=["accountant"]).user
    school_with_fees(other_school, other_head)
    with use_school(school):
        finance.open_cash_session(actor=cashier, cash_register=alpha["register"])

    tick(monkeypatch, MORNING)
    assert received(kind=Kind.REGISTER_OPEN) == []  # heure de clôture de l'école : 18:00
    evening = MORNING.replace(hour=18, minute=5)
    tick(monkeypatch, evening)
    tick(monkeypatch, evening + timedelta(minutes=15))

    # Ni la caissière (sans droit sur les rapports), ni le directeur de l'autre école.
    alerts = received(kind=Kind.REGISTER_OPEN)
    assert {alert.user for alert in alerts} == {head, accountant}
    assert {(a.school, a.app, a.url) for a in alerts} == {(school, "gestion", "/cash-closings")}
    assert "Caisse 1" in alerts[0].body and str(cashier) in alerts[0].body
    # Toujours ouverte le lendemain soir : signalée de nouveau.
    tick(monkeypatch, evening + timedelta(days=1))
    assert len(received(kind=Kind.REGISTER_OPEN)) == 4


def test_purge_removes_only_what_is_older_than_ninety_days(school, other_school, head, other_head):
    now = timezone.now()
    for owner, place in ((head, school), (other_head, other_school)):
        old, _recent = (
            push.notify([owner], school=place, app="gestion", kind=Kind.TEST, title=title)[0]
            for title in ("Ancienne", "Récente")
        )
        Notification.all_schools.filter(pk=old.pk).update(created_at=now - timedelta(days=91))
        with use_school(place):
            ScheduledRun.objects.create(job="reminders", day=now.date() - timedelta(days=91))
            ScheduledRun.objects.create(job="reminders", day=now.date())

    scheduled.purge(now)

    assert [n.title for n in received()] == ["Récente", "Récente"]
    assert ScheduledRun.all_schools.count() == 2

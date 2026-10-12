"""Notifications des événements (5.6.1) : paiement reçu et annonce pour le parent, écart de caisse
et annulation à valider pour ceux qui en ont le droit. Rien ne sort de l'école de l'événement, un
rejeu ne notifie pas deux fois, le texte est dans la langue du destinataire, et chacun ne règle
que les sortes qu'il peut recevoir."""

import pytest
from django.utils import timezone

from apps.core.ids import uuid7
from apps.core.money import format_amount
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.notifications import services
from apps.notifications.models import Notification
from apps.students.models import Family
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

Kind = Notification.Kind


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


def parent_of(school, enrollment, **fields):
    """Compte du portail de la famille de l'élève."""
    user = UserFactory(**fields)
    with use_school(school):
        Family.objects.filter(students__enrollments=enrollment).update(primary_user=user)
    return user


def received(**filters) -> list[Notification]:
    return list(Notification.all_schools.filter(**filters).order_by("created_at", "id"))


def test_payment_notifies_the_parent_of_that_school_once_in_their_language(
    school, other_school, other_head, cashier, alpha
):
    enrollment = alpha["enrollment"]
    parent = parent_of(school, enrollment, language="en")
    beta = school_with_fees(other_school, other_head)
    parent_of(other_school, beta["enrollment"])
    payment_id = uuid7()

    payment = pay(school, cashier, enrollment, 12000, "USD", payment_id=payment_id)
    # Renvoyé par l'appareil (nouvel essai de synchronisation) : pas de seconde notification.
    pay(school, cashier, enrollment, 12000, "USD", payment_id=payment_id)

    [notification] = received()
    assert (notification.user, notification.school) == (parent, school)
    assert (notification.app, notification.kind) == ("portail", Kind.PAYMENT_RECEIVED)
    assert notification.title == f"Payment received: {format_amount(12000, 'USD')}"
    assert payment.receipt_number in notification.body
    assert notification.url == f"/children/{enrollment.student_id}"

    # Accès au portail suspendu par l'école : plus rien pour cette famille.
    with use_school(school):
        Family.objects.update(portal_suspended_at=timezone.now())
    pay(school, cashier, enrollment, 5000, "USD")
    assert len(received()) == 1


def test_announcement_notifies_only_the_families_of_its_school(
    school, other_school, head, other_head, alpha
):
    parent = parent_of(school, alpha["enrollment"])
    beta = school_with_fees(other_school, other_head)
    parent_of(other_school, beta["enrollment"])

    with use_school(school):
        services.publish(
            actor=head,
            title="Réunion des parents",
            body="Samedi à 9 h, salle polyvalente.",
            audience="class_groups",
            class_groups=[alpha["group"]],
        )

    [notification] = received()
    assert (notification.user, notification.school) == (parent, school)
    assert (notification.app, notification.kind) == ("portail", Kind.ANNOUNCEMENT)
    assert notification.title == "Réunion des parents"
    assert notification.url == "/announcements"


def test_closing_beyond_the_threshold_alerts_those_who_read_the_reports(
    school, other_head, head, cashier, alpha
):
    accountant = MembershipFactory(school=school, roles=["accountant"]).user
    MembershipFactory(school=school, roles=["secretary"])
    enrollment = alpha["enrollment"]

    # Seuil par défaut : 10,00 $. Il manque 15,00 $.
    session = pay(school, cashier, enrollment, 12000, "USD").cash_session
    with use_school(school):
        finance.close_cash_session(
            session, actor=cashier, counted={"USD": 10500, "CDF": 0}, note="Billet manquant"
        )
    alerts = received(kind=Kind.CASH_DIFFERENCE)
    assert {alert.user for alert in alerts} == {head, accountant}
    assert {(alert.school, alert.app, alert.url) for alert in alerts} == {
        (school, "gestion", "/cash-closings")
    }
    assert format_amount(-1500, "USD") in alerts[0].body

    # Il manque 5,00 $ : sous le seuil, rien.
    session = pay(school, cashier, enrollment, 5000, "USD").cash_session
    with use_school(school):
        finance.close_cash_session(
            session, actor=cashier, counted={"USD": 4500, "CDF": 0}, note="Monnaie"
        )
    assert len(received(kind=Kind.CASH_DIFFERENCE)) == 2


def test_cancellation_request_alerts_the_approvers_and_tells_when_the_day_threshold_is_passed(
    school, other_head, head, cashier, alpha
):
    promoter = MembershipFactory(school=school, roles=["promoter"]).user
    with use_school(school):
        school.settings = {**school.settings, "alerts": {"cancellations_per_day": 1}}
        school.save(update_fields=["settings"])
    first = pay(school, cashier, alpha["enrollment"], 2000, "USD")
    second = pay(school, cashier, alpha["enrollment"], 3000, "USD")

    with use_school(school):
        request_id = uuid7()
        for _attempt in range(2):
            finance.request_cancellation(
                first, actor=cashier, reason="Erreur de montant", request_id=request_id
            )
        finance.request_cancellation(second, actor=cashier, reason="Mauvais élève")

    # Le promoteur lit les rapports mais ne valide pas : il n'est pas dérangé.
    assert received(user=promoter) == []
    one, two = received(kind=Kind.CANCELLATION_REQUEST)
    assert (one.user, one.school, one.url) == (head, school, "/cancellations")
    assert first.receipt_number in one.title
    assert "Erreur de montant" in one.body
    assert "demande du jour" not in one.body
    # Deuxième demande du jour, seuil à 1 : dit dans le message.
    assert "2e demande du jour" in two.body


def test_each_account_only_sets_the_kinds_it_can_receive_in_that_school(
    api, school, other_school, head
):
    """Le même compte : directeur à alpha, caissier à beta."""
    MembershipFactory(user=head, school=other_school, roles=["cashier"])
    preferences = "/api/notifications/preferences/"
    at_alpha, at_beta = api(head), api(head, "beta.localhost")

    assert at_alpha.get(preferences).json()["kinds"] == [
        "platform_news",
        "cancellation_request",
        "cash_difference",
    ]
    assert at_beta.get(preferences).json()["kinds"] == ["platform_news"]
    at_alpha.put(preferences, {"muted": ["cash_difference"]})
    # À beta, il ne coupe pas une alerte qu'il n'y reçoit pas, et son réglage ne défait pas
    # celui d'alpha.
    muted = at_beta.put(preferences, {"muted": ["cancellation_request", "platform_news"]})
    assert muted.json()["muted"] == ["platform_news"]
    assert at_alpha.get(preferences).json()["muted"] == ["cash_difference", "platform_news"]

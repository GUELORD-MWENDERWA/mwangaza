# ruff: noqa: F811
"""« Mon abonnement », rappels d'échéance et lecture seule (ABO.3, ABO.4) : droits, isolation entre
écoles, école fermée en écriture après le délai de grâce puis rouverte au paiement."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.billing import invoicing, reminders
from apps.billing.models import Invoice, ModuleRequest
from apps.billing.tests.test_billing import CONSOLE, END, START, essential, finance, member  # noqa: F401
from apps.billing.tests.test_invoicing import contract, invoice  # noqa: F401
from apps.core.tenancy import use_all_schools, use_school
from apps.notifications import scheduled
from apps.notifications.models import Notification
from apps.schools.models import School

pytestmark = pytest.mark.django_db


def today(school):
    return timezone.now().astimezone(ZoneInfo(school.timezone)).date()


def due(invoice, days_ago: int):
    """Facture échue il y a `days_ago` jours (négatif : à venir). Les factures ne se modifient
    pas par l'API ; ici seulement la date, pour jouer le temps."""
    with use_all_schools():
        Invoice.all_schools.filter(pk=invoice.pk).update(
            due_on=today(invoice.school) - timedelta(days=days_ago)
        )


def status(school):
    with use_all_schools():
        return School.objects.get(pk=school.pk).status


def test_subscription_is_for_billing_roles_and_for_their_own_school(
    api, invoice, school, head, cashier, other_head
):
    assert api(cashier).get("/api/subscription/").status_code == 403
    assert api(cashier).get("/api/subscription/invoices/").status_code == 403
    mine = api(head).get("/api/subscription/invoices/").json()
    rows = mine["results"] if isinstance(mine, dict) else mine
    assert [r["number"] for r in rows] == [invoice.number]
    assert api(head).get(f"/api/subscription/invoices/{invoice.pk}/pdf/").status_code == 200
    # L'autre école ne voit ni la facture, ni son PDF, ni le contrat.
    other = api(other_head, host="beta.localhost")
    theirs = other.get("/api/subscription/invoices/").json()
    assert (theirs["results"] if isinstance(theirs, dict) else theirs) == []
    assert other.get(f"/api/subscription/invoices/{invoice.pk}/pdf/").status_code == 404
    assert other.get("/api/subscription/contract/pdf/").status_code == 404
    summary = api(head).get("/api/subscription/").json()
    assert summary["balance"] == [{"currency": invoice.currency, "amount": invoice.total}]
    assert summary["next_due"]["number"] == invoice.number and not summary["late"]


def test_unpaid_invoice_makes_the_school_read_only_until_it_is_paid(
    api, finance, invoice, school, head, cashier
):
    due(invoice, 5)  # en retard, mais dans le délai de grâce
    assert reminders.refresh(school) is None and status(school) == "active"

    due(invoice, reminders.GRACE_DAYS + 1)
    assert reminders.refresh(school) == "readonly"
    admin = api(head)
    # On lit encore, on voit pourquoi ; on n'écrit plus (la caisse non plus).
    assert admin.get("/api/subscription/").json()["read_only"] is True
    assert admin.get("/api/academic-years/").status_code == 200
    blocked = admin.post("/api/academic-years/", {})
    assert blocked.status_code == 403 and blocked.json()["code"] == "school_read_only"
    # Les paiements de l'école à la plateforme rouvrent tout de suite.
    invoicing.record_payment(
        invoice, actor=finance, amount=invoice.total, method="cash", paid_on=today(school)
    )
    assert status(school) == "active"
    assert admin.post("/api/academic-years/", {}).status_code == 400  # validée, plus bloquée


def test_trial_and_suspended_schools_are_not_switched(invoice, school):
    due(invoice, reminders.GRACE_DAYS + 30)
    for state in ("trial", "suspended"):
        School.objects.filter(pk=school.pk).update(status=state)
        school.refresh_from_db()
        assert reminders.refresh(school) is None and status(school) == state


def test_reminders_go_once_to_those_who_see_the_subscription(
    invoice, school, head, cashier, other_head
):
    due(invoice, -7)
    scheduled.tick(timezone.now(), force=True)
    scheduled.tick(timezone.now(), force=True)  # rejouer n'envoie rien de plus
    with use_school(school):
        kinds = list(Notification.objects.values_list("user_id", "kind"))
    assert kinds == [(head.pk, "subscription")]  # ni le caissier, ni l'autre école
    due(invoice, reminders.GRACE_DAYS + 1)
    with use_all_schools():
        from apps.notifications.models import ScheduledRun

        ScheduledRun.all_schools.all().delete()
    scheduled.tick(timezone.now(), force=True)
    assert status(school) == "readonly"
    with use_school(school):
        assert Notification.objects.filter(kind="subscription").count() == 2


def test_module_request_is_kept_for_the_console(api, finance, school, head, other_head):
    School.objects.filter(pk=school.pk).update(modules=["students"])
    admin = api(head)
    created = admin.post("/api/subscription/module-requests/", {"module": "timetable"})
    assert created.status_code == 201
    assert (
        admin.post("/api/subscription/module-requests/", {"module": "timetable"}).status_code == 400
    )
    assert admin.post("/api/subscription/module-requests/", {"module": "nope"}).status_code == 400
    assert admin.get("/api/subscription/").json()["open_requests"] == ["timetable"]
    # L'autre école ne voit pas cette demande ; la console les voit toutes.
    assert (
        api(other_head, host="beta.localhost").get("/api/subscription/").json()["open_requests"]
        == []
    )
    rows = api(finance, host=CONSOLE).get("/api/console/billing/module-requests/").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert [(r["school"], r["module"]) for r in rows] == [("alpha", "timetable")]
    with use_all_schools():
        assert ModuleRequest.all_schools.count() == 1
    # La console la clôt (journal) ; l'école peut ensuite la redemander.
    request_id = rows[0]["id"]
    done = api(finance, host=CONSOLE).post(
        f"/api/console/billing/module-requests/{request_id}/handled/"
    )
    assert done.status_code == 200 and done.json()["status"] == "done"
    assert (
        PlatformAuditLog.objects.filter(action=PlatformAction.MODULE_REQUEST_HANDLED).count() == 1
    )
    assert admin.get("/api/subscription/").json()["open_requests"] == []

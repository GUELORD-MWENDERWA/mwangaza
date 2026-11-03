# ruff: noqa: F811
"""Affaires de la plateforme et cycle de vie d'une école (CON.1, CON.2) : sections du tableau de
bord selon les droits, espaces réels seulement, montants par devise ; export complet d'une école
(rien d'une autre, lien signé de 7 jours) remis par e-mail à l'arrêt ; changements d'état annoncés
au contact de l'école."""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core import mail
from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.utils import timezone
from openpyxl import load_workbook

from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.billing import invoicing
from apps.billing import services as billing
from apps.billing.tests.test_billing import CONSOLE, END, START, essential, finance, member  # noqa: F401
from apps.core.models import DemoRequest
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.schools import exports, services
from apps.schools.models import School, SchoolExport
from tests.factories import MembershipFactory, SchoolFactory

pytestmark = pytest.mark.django_db
BUSINESS = "/api/console/business/"


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()


def invoiced(finance, essential, school, students=40):
    draft = billing.draft_contract(
        actor=finance, school=school, plan=essential, start_date=START, end_date=END
    )
    contract = billing.activate_contract(draft, actor=finance, signature="online", signer_name="A")
    return invoicing.issue_invoice(contract, actor=finance, students=students, issued_on=START)


def test_business_sections_follow_the_rights_and_count_live_spaces_only(
    api, finance, essential, school, other_school
):
    SchoolFactory(code="essai", environment="test", status="active")
    invoice = invoiced(finance, essential, school)
    invoicing.record_payment(
        invoice, actor=finance, amount=1000, method="cash", paid_on=timezone.localdate()
    )
    DemoRequest.objects.create(name="Visiteur A", phone="+243970000001", status="new")
    DemoRequest.objects.create(name="Visiteur B", phone="+243970000002", status="dropped")

    data = api(finance, host=CONSOLE).get(BUSINESS).json()
    assert data["prospects_open"] is None  # la finance ne gère pas les prospects
    live = School.objects.filter(environment="live").count()
    assert sum(data["schools"].values()) == live  # l'espace d'essai n'y est pas
    usd = next(row for row in data["money"] if row["currency"] == "USD")
    assert usd["outstanding"] == invoice.total - 1000

    sales = api(member("commercial"), host=CONSOLE).get(BUSINESS).json()
    assert sales["prospects_open"] == 1
    assert sales["schools"] is None and sales["money"] is None and sales["renewals"] is None

    assert api(member("communication"), host=CONSOLE).get(BUSINESS).status_code == 403


def test_overdue_money_stays_in_its_own_currency(api, finance, essential, school):
    invoice = invoiced(finance, essential, school)
    first = api(finance, host=CONSOLE).get(BUSINESS).json()["money"]
    assert [row["currency"] for row in first] == ["USD"]
    assert first[0]["invoiced"] == first[0]["outstanding"] == invoice.total
    assert first[0]["overdue"] == 0  # échéance pas encore passée à la date du jour de la facture


def test_excel_exports_need_their_right(api, finance, essential, school):
    invoiced(finance, essential, school)
    assert (
        api(member("commercial"), host=CONSOLE).get(f"{BUSINESS}export/invoices/").status_code
        == 403
    )
    response = api(finance, host=CONSOLE).get(f"{BUSINESS}export/invoices/")
    assert response.status_code == 200
    rows = list(load_workbook(BytesIO(response.content)).active.values)
    assert len(rows) == 2 and rows[1][2] == school.name
    assert api(finance, host=CONSOLE).get(f"{BUSINESS}export/secrets/").status_code == 404


def test_export_holds_only_its_own_school_and_the_link_expires(
    school, other_school, head, other_head, cashier, platform_admin
):
    mine = school_with_fees(school, head)
    pay(school, cashier, mine["enrollment"], 12000, "USD")
    theirs = school_with_fees(other_school, other_head)
    other_cashier = MembershipFactory(school=other_school, roles=["cashier"]).user
    pay(other_school, other_cashier, theirs["enrollment"], 7777, "USD")

    export = exports.build(exports.request_export(school, actor=platform_admin))
    assert export.state == SchoolExport.State.READY
    book = load_workbook(export.file.open("rb"))
    assert len(list(book[book.sheetnames[0]].values)) == 2  # en-têtes + son seul élève
    assert 7777 not in {c for sheet in book for row in sheet.values for c in row}
    payments = list(book[book.sheetnames[4]].values)
    assert len(payments) == 2 and payments[1][4] == 12000

    token = exports.token(export)
    assert exports.resolve(token) == export
    assert exports.resolve(token + "x") is None
    old = TimestampSigner(salt=exports.SALT)
    SchoolExport.objects.filter(pk=export.pk).update(expires_at=timezone.now() - timedelta(hours=1))
    assert exports.resolve(old.sign(str(export.pk))) is None
    export.refresh_from_db()
    assert export.state == SchoolExport.State.EXPIRED and not export.file


def test_stopping_a_live_school_logs_exports_and_tells_the_contact(
    settings, school, platform_admin, head, django_capture_on_commit_callbacks
):
    settings.EMAIL_HOST, settings.EMAIL_HOST_USER = "smtp.test", "contact@test"
    School.objects.filter(pk=school.pk).update(contact_email="directeur@alpha.test")
    school.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        services.stop(school, actor=platform_admin, reason="Départ de l'école", confirm="alpha")

    export = SchoolExport.objects.get(school=school)
    assert export.state == SchoolExport.State.READY
    assert PlatformAuditLog.objects.filter(action=PlatformAction.SCHOOL_STOPPED).count() == 1
    assert [m.to for m in mail.outbox] == [["directeur@alpha.test"]]
    assert "/api/platform/school-exports/" in mail.outbox[0].body

    with django_capture_on_commit_callbacks(execute=True):
        services.reactivate(school, actor=platform_admin)
    assert len(mail.outbox) == 2


def test_no_email_without_contact_or_for_a_sandbox(
    settings, platform_admin, django_capture_on_commit_callbacks
):
    settings.EMAIL_HOST, settings.EMAIL_HOST_USER = "smtp.test", "contact@test"
    sandbox = SchoolFactory(code="essai", environment="test", contact_email="x@essai.test")
    live = SchoolFactory(code="sans-contact")
    with django_capture_on_commit_callbacks(execute=True):
        services.suspend(sandbox, actor=platform_admin)
        services.suspend(live, actor=platform_admin)
    assert mail.outbox == []

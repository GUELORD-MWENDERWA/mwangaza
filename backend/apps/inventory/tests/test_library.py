"""Bibliothèque (BIB.1 à BIB.3) : isolation entre écoles, droits, prêt et retour par la
synchronisation (rejoués sans doublon, « déjà prêté » refusé), constat de perte → dette payée à la
caisse et jamais retirée par les barèmes, rectification, pénalité de retard, import du catalogue."""

import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from openpyxl import Workbook

from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.models import StudentCharge
from apps.finance.services import Part
from apps.finance.tests.test_api import entries
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.inventory import catalogue, losses, rules
from apps.inventory import loans as loan_service
from apps.inventory.models import Copy, Item, Loan
from apps.students.models import Enrollment
from apps.students.tests.conftest import enrolled
from apps.sync.tests.test_devices import remember
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

PUSH = "/api/sync/push/"
BOOKS = "/api/library/books/"


@pytest.fixture
def librarian(school):
    return MembershipFactory(school=school, roles=["librarian"]).user


@pytest.fixture
def fees(school, head):
    """Minerval de 3e et une caisse (`school_with_fees`), un élève inscrit."""
    return school_with_fees(school, head)


@pytest.fixture
def book(school, head, fees):
    """« Électricité industrielle » : deux exemplaires, 38,00 $ le remplacement."""
    with use_school(school):
        item = catalogue.save_item(
            None,
            actor=head,
            location=catalogue.library(),
            kind=Item.Kind.BOOK,
            name="Électricité industrielle",
            author="Kabeya",
            price_minor=3800,
            currency="USD",
            copies=2,
        )
        return item, list(item.copies.order_by("number"))


def op(kind: str, **payload) -> dict:
    return {"op_id": str(uuid7()), "type": kind, "payload": payload}


def lend(client, copy, student, *, when=None, loan_id=None) -> dict:
    when = when or timezone.now()
    body = op(
        "inventory.loan",
        id=str(loan_id or uuid7()),
        copy=str(copy.pk),
        student=str(student.pk),
        lent_at=when.isoformat(),
    )
    return client.post(PUSH, {"operations": [body]}).json()["results"][0]


def give_back(client, copy, *, when=None, condition="good") -> dict:
    when = when or timezone.now()
    body = op(
        "inventory.return", copy=str(copy.pk), returned_at=when.isoformat(), condition=condition
    )
    return client.post(PUSH, {"operations": [body]}).json()["results"][0]


def desk(api, user, host="alpha.localhost"):
    client = api(user, host)
    response = remember(client)
    assert response.status_code == 201, response.json()
    return client


def test_a_school_never_sees_nor_lends_the_books_of_another(
    api, school, other_school, other_head, beta, book
):
    item, [copy, _other] = book
    stranger = enrolled(other_school, other_head, beta["group"])
    other = desk(
        api, MembershipFactory(school=other_school, roles=["librarian"]).user, "beta.localhost"
    )

    assert other.get(BOOKS).json()["count"] == 0
    assert other.get(f"{BOOKS}{item.pk}/").status_code == 404
    assert other.patch(f"{BOOKS}{item.pk}/", {"name": "Volé"}).status_code == 404
    assert other.post(f"{BOOKS}{item.pk}/copies/", {"count": 1}).status_code == 404
    assert other.get("/api/library/loans/").json()["count"] == 0
    # L'appareil d'une autre école ne connaît pas l'exemplaire : refusé, rien n'est prêté.
    result = lend(other, copy, stranger)
    assert (result["status"], result["error"]["code"]) == ("rejected", "invalid")
    with use_school(school):
        assert not Loan.objects.exists()


def test_without_library_rights_or_module_everything_is_refused(
    api, school, cashier, librarian, book
):
    assert api(cashier).get(BOOKS).status_code == 403
    assert api(librarian).put("/api/library/rules/", {}).status_code == 400
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(teacher).get("/api/library/desk/").status_code == 403
    school.modules = [code for code in school.modules if code != "library"]
    school.save()
    response = api(librarian).get(BOOKS)
    assert (response.status_code, response.json()["code"]) == (403, "module_missing")


def test_a_loan_made_offline_is_recorded_once_and_a_second_lender_is_refused(
    api, school, head, librarian, fees, book
):
    _item, [copy, _spare] = book
    student = fees["enrollment"].student
    other = enrolled(school, head, fees["group"], last_name="Mapendo", first_name="Amina")
    client = desk(api, librarian)
    loan_id = uuid7()

    first = lend(client, copy, student, loan_id=loan_id)
    again = lend(client, copy, student, loan_id=loan_id)
    # Un second appareil, hors ligne, a prêté le même exemplaire à une autre élève.
    second = MembershipFactory(school=school, roles=["librarian"]).user
    conflict = lend(desk(api, second), copy, other)

    assert (first["status"], first["result"]["already"]) == ("applied", False)
    assert (again["status"], again["result"]["already"]) == ("applied", True)
    assert (conflict["status"], conflict["error"]["code"]) == ("rejected", "copy_already_lent")
    with use_school(school):
        loan = Loan.objects.get()
        copy.refresh_from_db()
        settings = rules.rules()
    assert (loan.pk, loan.student_id, copy.state) == (loan_id, student.pk, Copy.State.LENT)
    assert loan.due_on == timezone.localdate() + timedelta(days=settings["student_days"])
    assert [entry.actor_id for entry in entries(school, Action.LOAN_CREATED)] == [librarian.pk]

    back = give_back(client, copy, condition="worn")
    twice = give_back(client, copy)
    assert (back["result"]["already"], twice["result"]["already"]) == (False, True)
    with use_school(school):
        loan.refresh_from_db()
        copy.refresh_from_db()
    assert (loan.return_condition, copy.state) == (Loan.Condition.WORN, Copy.State.AVAILABLE)
    assert len(entries(school, Action.LOAN_RETURNED)) == 1


def test_a_lost_book_becomes_a_debt_paid_at_the_cash_desk_and_kept_by_fee_rules(
    api, school, head, cashier, librarian, fees, book
):
    _item, [copy, _spare] = book
    enrollment = fees["enrollment"]
    client = desk(api, librarian)
    assert lend(client, copy, enrollment.student)["status"] == "applied"

    response = api(librarian).post(
        "/api/library/reports/",
        {"copy": str(copy.pk), "kind": "lost", "note": "Oublié dans le bus"},
    )

    assert response.status_code == 201, response.json()
    with use_school(school):
        charge = StudentCharge.objects.get(source=StudentCharge.Source.ITEM)
        copy.refresh_from_db()
        # Un changement de barème ou de classe ne la retire jamais.
        finance.sync_charges(Enrollment.objects.filter(pk=enrollment.pk), actor=head)
        charge.refresh_from_db()
    assert (charge.amount_minor, charge.currency, charge.status) == (3800, "USD", "active")
    assert charge.enrollment_id == enrollment.pk
    assert copy.state == Copy.State.LOST
    assert entries(school, Action.LOSS_REPORTED)[0].after["amount_minor"] == 3800

    # Payée à la caisse comme tout frais, elle ne se retire plus par une rectification.
    pay(school, cashier, enrollment, 3800, "USD", parts=[Part(charge.pk, 3800)])
    report_id = response.json()["id"]
    url = f"/api/library/reports/{report_id}/correct/"
    assert api(librarian).post(url, {"note": "Retrouvé"}).status_code == 403
    refused = api(head).post(url, {"note": "Retrouvé"})
    assert (refused.status_code, refused.json()["code"]) == (409, "charge_paid")


def test_a_correction_brings_the_copy_back_and_removes_the_unpaid_debt(
    api, school, head, librarian, fees, book
):
    _item, [copy, _spare] = book
    lend(desk(api, librarian), copy, fees["enrollment"].student)
    with use_school(school):
        report = losses.report(copy, actor=librarian, kind="damaged", note="Pages arrachées")

    response = api(head).post(
        f"/api/library/reports/{report.pk}/correct/", {"note": "Erreur de saisie"}
    )

    assert response.status_code == 201
    with use_school(school):
        report.charge.refresh_from_db()
        copy.refresh_from_db()
    assert (report.charge.status, copy.state) == ("removed", Copy.State.AVAILABLE)
    again = api(head).post(f"/api/library/reports/{report.pk}/correct/", {"note": "Encore"})
    assert again.json()["code"] == "report_already_corrected"
    assert len(entries(school, Action.LOSS_CORRECTED)) == 1


def test_a_late_return_costs_the_daily_penalty_capped_at_the_price(
    api, school, head, librarian, fees, book
):
    _item, [copy, _spare] = book
    with use_school(school):
        rules.update_rules(actor=head, values={"late_fee_minor": 50, "late_fee_currency": "USD"})
    client = desk(api, librarian)
    lent = timezone.now() - timedelta(days=120)
    with use_school(school):
        loan_service.lend(
            actor=librarian,
            permissions=frozenset({"library.lend"}),
            id=uuid7(),
            copy=copy,
            lent_at=lent,
            student=fees["enrollment"].student,
        )

    give_back(client, copy)

    with use_school(school):
        fee = StudentCharge.objects.get(source=StudentCharge.Source.ITEM)
    # 106 jours de retard x 0,50 $ = 53,00 $, plafonnés au prix du livre (38,00 $).
    assert (fee.amount_minor, fee.currency) == (3800, "USD")


def test_the_catalogue_import_previews_then_records_once(api, school, librarian, alpha):
    sheet = Workbook()
    rows = [
        ("Titre", "Auteur", "Niveau", "Exemplaires", "Prix"),
        ("Mécanique générale", "Mbuyi", "3e", 3, "25,50"),
        ("Dessin technique", "Kasongo", "9e", 1, ""),
        ("", "Sans titre", "", 1, ""),
    ]
    for row in rows:
        sheet.active.append(row)
    content = io.BytesIO()
    sheet.save(content)

    def upload(**extra):
        file = SimpleUploadedFile("catalogue.xlsx", content.getvalue())
        client = api(librarian)
        # Envoi multipart (fichier), pas JSON.
        return client.client.post(
            "/api/library/import/",
            {"file": file, "currency": "USD", **extra},
            HTTP_HOST=client.host,
        )

    preview = upload().json()
    assert (preview["ready_count"], preview["error_count"]) == (1, 2)
    assert upload(expected=1).status_code == 201
    with use_school(school):
        item = Item.objects.get()
        assert (item.price_minor, item.level.name, item.copies.count()) == (2550, "3e", 3)
    # Envoyé deux fois, le fichier ne crée rien de plus.
    assert upload(expected=1).json()["code"] == "preview_outdated"

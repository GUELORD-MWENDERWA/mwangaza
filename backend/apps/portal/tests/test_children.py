"""Paiements d'un enfant sur le portail (H3) : frais dus et leur état, reçus en PDF, photo avec le
consentement du parent ; seulement pour le compte relié à sa famille, jamais d'une autre famille
ou d'une autre école, rien si l'accès ou l'école est suspendu."""

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.money import format_amount
from apps.core.tenancy import use_all_schools, use_school
from apps.finance.models import PaymentCancellation
from apps.finance.tests.test_balance import at
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.finance.tests.test_prior_payments import earlier
from apps.portal import receipts
from apps.portal.tests.test_access import activate, new_family, portal
from apps.portal.tests.test_families import family_of
from apps.students import services as students
from apps.students.models import Student

CHILDREN = "/api/portal/children/"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64


def child_url(enrollment) -> str:
    return f"{CHILDREN}{enrollment.student_id}/"


def receipt_url(payment) -> str:
    return f"/api/portal/payments/{payment.pk}/receipt/"


def cancel(school, payment, cashier, head) -> None:
    with use_school(school):
        PaymentCancellation.objects.create(
            payment=payment, reason="Erreur d'élève", requested_by=cashier, approved_by=head
        )


def test_a_childs_fees_and_payments_are_shown_to_its_familys_account_only(
    school, other_school, head, other_head, cashier, monkeypatch
):
    alpha = school_with_fees(school, head)
    beta = school_with_fees(other_school, other_head)
    enrollment = alpha["enrollment"]
    client = portal()
    activate(client, family_of(school, enrollment).code)
    stranger = portal()
    activate(
        stranger,
        new_family(other_school, other_head, phone="+243990000001").code,
        phone="0990000001",
    )
    at(monkeypatch, "2026-10-20")
    first = pay(school, cashier, enrollment, 24000, "USD")
    pay(school, cashier, enrollment, 5000, "USD")
    cancel(school, pay(school, cashier, enrollment, 10000, "CDF"), cashier, head)

    child = client.get(child_url(enrollment)).json()

    assert (child["full_name"], child["class_name"]) == ("Kasereka Jean", "3e Électricité A")
    assert child["school_name"] == school.name and child["photo"] is None
    # Le 20/10 : 1re tranche payée, 2e payée d'avance, 3e entamée, fonctionnement (30/09) en
    # retard ; le paiement annulé ne compte pas.
    assert [
        (f["fee"], f["due_on"], f["currency"], f["amount_minor"], f["remaining_minor"], f["state"])
        for f in child["fees"]
    ] == [
        ("Fonctionnement", "2026-09-30", "CDF", 25000, 25000, "overdue"),
        ("Minerval · 1re tranche", "2026-10-15", "USD", 12000, 0, "paid"),
        ("Minerval · 2e tranche", "2027-01-15", "USD", 12000, 0, "paid_early"),
        ("Minerval · 3e tranche", "2027-04-15", "USD", 12000, 7000, "partial"),
    ]
    assert [
        (c["currency"], c["paid_minor"], c["remaining_minor"])
        for c in child["balance"]["currencies"]
    ] == [("USD", 29000, 7000), ("CDF", 0, 25000)]
    assert [
        (p["received_amount_minor"], p["received_currency"], p["cancelled"])
        for p in child["payments"]
    ] == [(10000, "CDF", True), (5000, "USD", False), (24000, "USD", False)]

    assert client.get(child_url(beta["enrollment"])).status_code == 404
    # Compte relié à une famille de l'autre école : ni l'enfant, ni sa photo, ni ses reçus.
    assert stranger.get(child_url(enrollment)).status_code == 404
    assert stranger.get(f"{child_url(enrollment)}photo/").status_code == 404
    assert stranger.get(receipt_url(first)).status_code == 404
    assert portal().get(child_url(enrollment)).status_code == 403
    assert portal("alpha.localhost").get(child_url(enrollment)).status_code == 404


def test_a_receipt_pdf_only_for_a_valid_payment_of_an_active_family(
    school, head, cashier, monkeypatch
):
    alpha = school_with_fees(school, head)
    enrollment = alpha["enrollment"]
    family = family_of(school, enrollment)
    client = portal()
    activate(client, family.code)
    stranger = portal()
    activate(stranger, new_family(school, head, phone="+243990000001").code, phone="0990000001")
    at(monkeypatch, "2026-10-20")
    payment = pay(school, cashier, enrollment, 15000, "USD", note="Par la tante")
    cancelled = pay(school, cashier, enrollment, 1000, "CDF")
    cancel(school, cancelled, cashier, head)

    pdf = client.get(receipt_url(payment))

    assert (pdf.status_code, pdf["Content-Type"]) == (200, "application/pdf")
    assert pdf.content.startswith(b"%PDF")
    # Même contenu que le reçu de la caisse : lignes, montant en lettres, solde juste après lui.
    with use_school(school):
        page = receipts.receipt_document(payment)
    assert [(line["fee"], line["amount"]) for line in page["lines"]] == [
        ("Minerval · 1re tranche", format_amount(12000, "USD")),
        ("Minerval · 2e tranche", format_amount(3000, "USD")),
    ]
    assert page["words"] == "Cent cinquante dollars américains"
    assert page["overdue"] == format_amount(25000, "CDF")
    assert page["remaining"] == f"{format_amount(21000, 'USD')} + {format_amount(25000, 'CDF')}"
    assert page["verify_url"] == f"{school.url}/v/{payment.pk}"

    assert client.get(receipt_url(cancelled)).status_code == 404
    assert stranger.get(receipt_url(payment)).status_code == 404
    # Payé avant que l'école n'utilise l'application (E6) : montré au parent, sans reçu.
    prior = earlier(school, head, enrollment, "30")
    shown = client.get(child_url(enrollment)).json()["payments"]
    assert [p["origin"] for p in shown if p["id"] == str(prior.pk)] == ["prior"]
    assert client.get(receipt_url(prior)).status_code == 404
    with use_school(school):
        students.set_portal_access(family, actor=head, suspended=True)
    assert client.get(receipt_url(payment)).status_code == 404
    assert client.get(child_url(enrollment)).status_code == 404


def test_the_childs_photo_only_with_the_parents_consent(school, head):
    alpha = school_with_fees(school, head)
    enrollment = alpha["enrollment"]
    client = portal()
    activate(client, family_of(school, enrollment).code)
    stranger = portal()
    activate(stranger, new_family(school, head, phone="+243990000001").code, phone="0990000001")
    with use_school(school):
        student = enrollment.student
        students.set_photo(student, SimpleUploadedFile("photo.jpg", JPEG), actor=head)
    photo_url = f"{child_url(enrollment)}photo/"

    assert client.get(child_url(enrollment)).json()["photo"] is None
    assert client.get(photo_url).status_code == 404

    with use_all_schools():
        Student.all_schools.filter(pk=student.pk).update(photo_consent=True)
    assert client.get(child_url(enrollment)).json()["photo"].startswith(photo_url)
    assert client.get(photo_url)["Content-Type"] == "image/jpeg"
    assert stranger.get(photo_url).status_code == 404

"""Reprise en cours d'année (4.19, E6) : ce que chaque élève avait payé avant que l'école
n'utilise l'application, importé d'un fichier — isolation entre écoles, permission dédiée,
aperçu qui n'écrit rien, enregistrement hors caisse et sans reçu, lignes en erreur laissées,
fichier envoyé deux fois, aperçu périmé, correction par l'annulation habituelle ; audit."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.support import SUPPORT_PERMISSIONS
from apps.core.documents import workbook
from apps.core.tenancy import use_school
from apps.finance import dashboard, prior_payments, services
from apps.finance.models import Payment
from apps.finance.tests.test_api import entries
from apps.finance.tests.test_payments import lines, pay, school_with_fees
from apps.finance.tests.test_verification import page
from apps.sync.models import ChangeLog
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

URL = "/api/prior-payments/"
HEADERS = ["MATRICULE", "NOM", "MONTANT PAYÉ", "DEVISE", "FRAIS (facultatif)"]


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


@pytest.fixture
def accountant(school):
    return MembershipFactory(school=school, roles=["accountant"]).user


def matricule(school, data) -> str:
    with use_school(school):
        return data["enrollment"].student.matricule


def upload(rows: list[list]) -> SimpleUploadedFile:
    return SimpleUploadedFile("reprise.xlsx", workbook(HEADERS, rows))


def send(client, rows, expected=None):
    body = {"file": upload(rows)}
    if expected is not None:
        body["expected"] = json.dumps(expected)
    return client.client.post(URL, body, HTTP_HOST=client.host)


def earlier(school, actor, enrollment, amount: str, currency: str = "USD") -> Payment:
    """Reprise d'un élève, par le service (autres modules : portail)."""
    with use_school(school):
        rows = [[enrollment.student.matricule, "", amount, currency, ""]]
        totals = prior_payments.check(upload(rows)).totals
        prior_payments.record(upload(rows), actor=actor, expected=totals)
        return Payment.objects.filter(origin="prior").latest("receipt_number")


def codes(response) -> list[tuple[int, list[str]]]:
    return [
        (line["line"], [issue["code"] for issue in line["issues"]])
        for line in response.json()["errors"]
    ]


def count(school) -> int:
    with use_school(school):
        return Payment.objects.count()


def test_a_school_never_records_for_the_students_of_another(
    api, school, other_school, head, other_head, alpha, accountant
):
    beta = school_with_fees(other_school, other_head)
    theirs = matricule(other_school, beta)
    assert theirs and theirs != matricule(school, alpha)

    preview = send(api(accountant), [[theirs, "", 100, "USD", ""]])

    assert codes(preview) == [(2, ["unknown_student"])]
    refused = send(api(accountant), [[theirs, "", 100, "USD", ""]], expected=[])
    assert (refused.status_code, refused.json()["code"]) == (409, "nothing_to_record")
    # Chacune chez elle : la reprise d'Alpha ne touche pas Beta, dont le modèle ne liste
    # que ses élèves.
    mine = [[matricule(school, alpha), "", 100, "USD", ""]]
    totals = send(api(accountant), mine).json()["totals"]
    assert send(api(accountant), mine, expected=totals).status_code == 201
    assert (count(school), count(other_school)) == (1, 0)
    with use_school(other_school):
        assert (
            services.balance(services.charges_of(beta["enrollment"].pk)).currencies[0].paid_minor
            == 0
        )
    template = api(other_head, "beta.localhost").get(f"{URL}template/")
    assert template.status_code == 200


def test_recording_earlier_payments_needs_its_own_permission(
    api, school, head, cashier, accountant, alpha
):
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    rows = [[matricule(school, alpha), "", 100, "USD", ""]]

    for user in (cashier, secretary):
        assert send(api(user), rows).status_code == 403
        assert api(user).get(f"{URL}template/").status_code == 403
    assert send(api(accountant), rows).status_code == 200
    assert send(api(head), rows).status_code == 200
    # Le support ne touche pas à l'argent.
    assert "finance.import_prior_payments" not in SUPPORT_PERMISSIONS
    assert count(school) == 0


def test_the_preview_writes_nothing_then_the_file_is_recorded_outside_the_cash_desk(
    api, school, head, cashier, accountant, alpha
):
    """150,00 $ : la 1re tranche puis 30,00 $ de la 2e, comme à la caisse ; 25 000 FC : le
    fonctionnement. Ni caisse, ni « encaissé », ni reçu ; l'élève doit moins."""
    enrollment = alpha["enrollment"]
    number = matricule(school, alpha)
    rows = [[number.lower(), "Élève", "150,00", "$", ""], [number, "", 25000, "FC", ""]]
    sold = pay(school, cashier, enrollment, 1000, "USD")

    preview = send(api(accountant), rows)

    assert preview.status_code == 200
    body = preview.json()
    assert (body["recorded"], body["ready_count"], body["error_count"]) == (False, 2, 0)
    assert body["totals"] == [
        {"currency": "USD", "amount_minor": 15000, "count": 1},
        {"currency": "CDF", "amount_minor": 25000, "count": 1},
    ]
    assert count(school) == 1

    recorded = send(api(accountant), rows, expected=body["totals"])

    assert (recorded.status_code, recorded.json()["recorded"]) == (201, True)
    with use_school(school):
        usd, cdf = Payment.objects.filter(origin="prior").order_by("receipt_number")
        assert (usd.receipt_number, cdf.receipt_number) == (
            "ALPHA-RP-26-000001",
            "ALPHA-RP-26-000002",
        )
        assert (usd.cash_session, usd.cashier, str(usd.rate_used)) == (
            None,
            accountant,
            "2850.000000",
        )
        balance = services.balance(services.charges_of(enrollment.pk))
        assert [(b.currency, b.paid_minor, b.remaining_minor) for b in balance.currencies] == [
            ("USD", 16000, 20000),
            ("CDF", 25000, 0),
        ]
        # Hors caisse : « encaissé » ne compte que le paiement de la caissière.
        day = timezone.now()
        collected = dashboard.collected(day - timezone.timedelta(days=1), day)
        assert [(row["currency"], row["amount_minor"]) for row in collected] == [
            ("USD", 1000),
            ("CDF", 0),
        ]
        assert [p.pk for p in dashboard.recent_payments()] == [sold.pk]
        assert services.session_totals(services.open_session_of(cashier)) == [
            {"currency": "USD", "amount_minor": 1000, "count": 1}
        ]
        # Les appareils reçoivent le nouveau solde de l'élève.
        assert ChangeLog.objects.filter(entity_id=enrollment.pk).exists()
    assert lines(school, usd) == [("1re tranche", 11000, 11000), ("2e tranche", 4000, 4000)]
    logged = entries(school, "finance.prior_payment_recorded")
    assert {(e.actor, e.entity_id) for e in logged} == {(accountant, usd.pk), (accountant, cdf.pk)}
    assert logged[0].after["file"] == "reprise.xlsx"
    # Dans l'historique de l'élève, sans reçu : ni lecture, ni réimpression, ni vérification.
    history = api(head).get("/api/payments/", enrollment=str(enrollment.pk)).json()
    assert {(p["origin"], p["cash_register"]) for p in history["results"]} == {
        ("prior", None),
        ("cash", "C1"),
    }
    assert api(head).get(f"/api/payments/{usd.pk}/").status_code == 404
    assert api(head).post(f"/api/payments/{usd.pk}/reprint/").status_code == 404
    assert page(api, usd.pk)[0].status_code == 404


def test_wrong_lines_are_listed_and_left_out_and_a_file_sent_twice_adds_nothing(
    api, school, accountant, alpha
):
    number = matricule(school, alpha)
    rows = [
        ["INCONNU-1", "", 100, "USD", ""],
        [number, "", "abc", "USD", ""],
        # « 25,000 » peut vouloir dire vingt-cinq mille : refusé plutôt que lu vingt-cinq.
        [number, "", "25,000", "CDF", ""],
        [number, "", 100, "EUR", ""],
        [number, "", 100, "USD", "Cantine"],
        [number, "", 500, "USD", "Minerval"],
        [number, "", "", "USD", ""],
        [number, "", 120, "USD", "minerval"],
    ]

    preview = send(api(accountant), rows)

    assert codes(preview) == [
        (2, ["unknown_student"]),
        (3, ["invalid_amount"]),
        (4, ["invalid_amount"]),
        (5, ["unknown_currency"]),
        (6, ["unknown_fee"]),
        (7, ["more_than_due"]),
    ]
    body = preview.json()
    assert body["errors"][5]["issues"][0]["due_minor"] == 36000
    assert (body["ready_count"], body["empty_count"]) == (1, 1)
    # Aperçu périmé : les totaux validés ne sont plus ceux du fichier.
    stale = [{"currency": "USD", "amount_minor": 99900, "count": 1}]
    refused = send(api(accountant), rows, expected=stale)
    assert (refused.status_code, refused.json()["code"]) == (409, "preview_outdated")
    assert count(school) == 0

    assert send(api(accountant), rows, expected=body["totals"]).status_code == 201
    again = send(api(accountant), rows, expected=body["totals"])

    assert (again.status_code, again.json()["code"]) == (409, "nothing_to_record")
    assert count(school) == 1
    assert (9, ["already_recorded"]) in codes(send(api(accountant), rows))
    assert len(entries(school, "finance.prior_payment_recorded")) == 1


def test_an_earlier_payment_is_corrected_by_the_usual_cancellation(
    api, school, head, cashier, accountant, alpha
):
    enrollment = alpha["enrollment"]
    rows = [[matricule(school, alpha), "", 240, "USD", ""]]
    totals = send(api(accountant), rows).json()["totals"]
    send(api(accountant), rows, expected=totals)
    with use_school(school):
        payment = Payment.objects.get()
    body = {"payment": str(payment.pk), "reason": "Montant recopié de la mauvaise ligne"}

    # La caissière ne demande que pour ses propres encaissements.
    assert api(cashier).post("/api/cancellations/", body).status_code == 403
    request = api(accountant).post("/api/cancellations/", body)
    approved = api(head).post(f"/api/cancellations/{request.json()['id']}/approve/")

    assert (request.status_code, approved.status_code) == (201, 200)
    with use_school(school):
        balance = services.balance(services.charges_of(enrollment.pk))
        assert balance.currencies[0].paid_minor == 0
    # Annulée, la reprise de l'élève se refait avec le bon montant.
    fixed = [[matricule(school, alpha), "", 120, "USD", ""]]
    totals = send(api(accountant), fixed).json()["totals"]
    assert send(api(accountant), fixed, expected=totals).status_code == 201
    with use_school(school):
        assert services.balance(services.charges_of(enrollment.pk)).currencies[0].paid_minor == (
            12000
        )

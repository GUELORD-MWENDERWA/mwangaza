"""Page publique de vérification d'un reçu `/v/{id}` (F4, 3.2.3) : ouverte par le QR code du
reçu, sans connexion ; le minimum, élève en initiales ; seulement les reçus de l'école de
l'adresse."""

from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.finance.models import PaymentCancellation
from apps.finance.tests.test_payments import pay, school_with_fees


def page(api, payment_id, host="alpha.localhost"):
    response = api(host=host).get(f"/v/{payment_id}")
    return response, response.content.decode()


def test_a_receipt_shows_the_minimum_then_its_cancellation(api, school, head, cashier):
    alpha = school_with_fees(school, head)
    payment = pay(school, cashier, alpha["enrollment"], 15025, "USD")

    response, html = page(api, payment.pk)

    assert response.status_code == 200
    assert response["Cache-Control"].startswith("max-age=0")
    assert "noindex" in response["X-Robots-Tag"]
    assert payment.receipt_number in html and "150,25\xa0$" in html
    # Élève en initiales seulement : ni nom, ni prénom, ni matricule.
    student = alpha["enrollment"].student
    assert "K. J." in html
    assert student.last_name not in html and student.first_name not in html
    assert student.matricule not in html
    assert 'data-state="valid"' in html

    with use_school(school):
        PaymentCancellation.objects.create(
            payment=payment, reason="Erreur d'élève", requested_by=cashier, approved_by=head
        )
    _response, html = page(api, payment.pk)
    assert 'data-state="cancelled"' in html and payment.receipt_number in html


def test_a_receipt_of_another_school_or_an_unknown_one_is_unknown(
    api, school, other_school, head, cashier
):
    alpha = school_with_fees(school, head)
    payment = pay(school, cashier, alpha["enrollment"], 12000, "USD")

    for host, payment_id in (("beta.localhost", payment.pk), ("alpha.localhost", uuid7())):
        response, html = page(api, payment_id, host)
        assert response.status_code == 404
        assert 'data-state="unknown"' in html
        assert payment.receipt_number not in html and "120,00" not in html
    # Hors de l'adresse d'une école : aucune page.
    assert page(api, payment.pk, host="localhost")[0].status_code == 404

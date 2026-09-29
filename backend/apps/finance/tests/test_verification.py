"""Page publique de vérification d'un reçu `/v/{id}` (F4, 3.2.3) : ouverte par le QR code du
reçu, sans connexion ; le minimum, élève en initiales ; seulement les reçus de l'école de
l'adresse. QR code signé par l'appareil (3.5.2) : reçu pas encore synchronisé vérifiable, reçu
modifié reconnu."""

import base64
from urllib.parse import urlencode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.finance.models import PaymentCancellation
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.sync import services as sync
from apps.sync.models import Device, SyncOperation


def page(api, payment_id, host="alpha.localhost", **claim):
    query = f"?{urlencode(claim)}" if claim else ""
    response = api(host=host).get(f"/v/{payment_id}{query}")
    return response, response.content.decode()


class Till:
    """Appareil mémorisé d'un caissier, avec sa clé privée (WebCrypto dans le navigateur)."""

    def __init__(self, api, user):
        self.key = ec.generate_private_key(ec.SECP256R1())
        spki = self.key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        client = api(user)
        body = {"label": "Windows · Edge", "public_key": base64.b64encode(spki).decode()}
        device = client.post("/api/me/devices/", body).json()
        self.id, self.prefix = device["id"], device["prefix"]

    def claim(self, payment_id, number, time, amount, currency="USD", register="C1") -> dict:
        """Ce que `features/cash/receiptQr.ts` écrit dans le QR code : `id|n|t|a|c|r` signé."""
        fields = [payment_id, number, time, amount, currency, register]
        message = "|".join(str(field) for field in fields).encode()
        r, s = decode_dss_signature(self.key.sign(message, ec.ECDSA(hashes.SHA256())))
        signature = base64.urlsafe_b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        return {
            "n": number,
            "t": time,
            "a": amount,
            "c": currency,
            "r": register,
            "s": signature.rstrip(b"=").decode(),
        }


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


def test_a_receipt_printed_offline_is_authentic_until_synced_unless_altered(
    api, school, other_school, head, cashier
):
    """Pas encore sur le serveur : la signature de l'appareil fait foi ; montant changé →
    falsifié ; appareil déconnecté ou encaissement refusé à la synchronisation → inconnu ;
    même QR code sur l'adresse d'une autre école → inconnu."""
    till = Till(api, cashier)
    payment_id, number = uuid7(), f"ALPHA-{till.prefix}-26-000007"
    claim = till.claim(payment_id, number, 1790000000, 2000)

    response, html = page(api, payment_id, **claim)
    assert response.status_code == 200 and 'data-state="pending"' in html
    assert number in html and "20,00\xa0$" in html and "C1" in html

    for altered in ({"a": 20000}, {"n": f"ALPHA-{till.prefix}-26-000008"}, {"s": "AAAA"}):
        _response, html = page(api, payment_id, **{**claim, **altered})
        assert 'data-state="forged"' in html and "200,00" not in html
    assert page(api, payment_id, host="beta.localhost", **claim)[0].status_code == 404

    with use_school(school):
        SyncOperation.objects.create(
            op_id=payment_id,
            device_id=till.id,
            type="payment.create",
            payload={},
            status=SyncOperation.Status.REJECTED,
            created_by=cashier,
        )
    assert 'data-state="unknown"' in page(api, payment_id, **claim)[1]
    other_id = uuid7()
    other = till.claim(other_id, f"ALPHA-{till.prefix}-26-000009", 1790000000, 2000)
    assert 'data-state="pending"' in page(api, other_id, **other)[1]
    with use_school(school):
        sync.revoke_device(Device.objects.get(pk=till.id), actor=head)
    response, html = page(api, other_id, **other)
    assert response.status_code == 404 and 'data-state="unknown"' in html


def test_a_recorded_receipt_whose_qr_code_says_otherwise_is_forged(api, school, head, cashier):
    """Une fois sur le serveur, la base fait foi : le QR code doit dire la même chose qu'elle."""
    alpha = school_with_fees(school, head)
    payment = pay(school, cashier, alpha["enrollment"], 12000, "USD")
    till = Till(api, cashier)
    time = int(payment.paid_at.timestamp())
    claim = till.claim(payment.pk, payment.receipt_number, time, 12000)

    assert 'data-state="valid"' in page(api, payment.pk, **claim)[1]
    # Même signé par un appareil de l'école, un QR code qui dit un autre montant est faux.
    altered = till.claim(payment.pk, payment.receipt_number, time, 1200)
    _response, html = page(api, payment.pk, **altered)
    assert 'data-state="forged"' in html and "120,00" not in html
    assert 'data-state="forged"' in page(api, payment.pk, n=payment.receipt_number, t="x")[1]

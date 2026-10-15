"""Cachet de l'école, signature du chef et signature de chaque personne (DOC.1) : dépôt
(`school.configure`, Mon compte), journal, images détourées, jamais publiques, propres à
chaque école ; signataire des documents du serveur."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw

from apps.accounts.models import Membership
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.signatures import signature_context
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

STAMP = "/api/school/settings/stamp/"
HEAD_SIGNATURE = "/api/school/settings/head-signature/"
MY_SIGNATURE = "/api/me/signature/"


def photographed_sheet(size=(1200, 600)) -> bytes:
    """Photo d'une signature : papier gris clair, trait bleu foncé, en JPEG."""
    image = Image.new("RGB", size, (214, 216, 210))
    ImageDraw.Draw(image).line([(100, 300), (600, 150), (1100, 400)], fill=(20, 30, 90), width=24)
    output = io.BytesIO()
    image.save(output, "JPEG", quality=92)
    return output.getvalue()


def send(client, url, content: bytes, name="signature.jpg"):
    return client.client.post(
        url, {"image": SimpleUploadedFile(name, content)}, HTTP_HOST=client.host
    )


def journal(school, action) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action=action).order_by("created_at"))


def test_stamp_is_cleaned_logged_and_shown_only_to_the_staff(api, client, school, head, cashier):
    response = send(api(head), STAMP, photographed_sheet())

    assert response.status_code == 200
    url = response.json()["stamp"]
    assert url.startswith("/api/school/stamp/?v=")
    [entry] = journal(school, Action.SCHOOL_SIGNATURE_CHANGED)
    assert entry.after == {"stamp": True}

    # Réduit, en PNG, papier transparent, trait opaque.
    school.refresh_from_db()
    with Image.open(school.stamp.path) as image:
        assert (image.format, image.mode, image.size) == ("PNG", "RGBA", (800, 400))
        assert image.getpixel((5, 5))[3] == 0
        assert image.getpixel((233, 150))[3] == 255  # milieu du premier trait

    # Le personnel connecté de l'école le lit (reçu imprimé, hors ligne ensuite) ; personne d'autre.
    seen = api(cashier).get(url)
    assert seen.status_code == 200
    assert seen["Cache-Control"] == "private, max-age=86400"
    assert client.get(url, HTTP_HOST="alpha.localhost").status_code == 403
    assert api(cashier).get("/api/school/").json().get("stamp") is None

    removed = api(head).delete(STAMP)
    assert removed.json()["stamp"] is None
    assert len(journal(school, Action.SCHOOL_SIGNATURE_CHANGED)) == 2


def test_only_school_configure_sets_the_stamp_and_head(api, school, cashier):
    assert send(api(cashier), STAMP, photographed_sheet()).status_code == 403
    assert send(api(cashier), HEAD_SIGNATURE, photographed_sheet()).status_code == 403
    response = api(cashier).patch("/api/school/settings/", {"head_name": "Faux Chef"})
    assert response.status_code == 403


def test_a_school_never_reads_the_stamp_or_signatures_of_another(
    api, school, other_school, head, cashier, other_head
):
    send(api(head), STAMP, photographed_sheet())
    send(api(head), HEAD_SIGNATURE, photographed_sheet())
    send(api(cashier), MY_SIGNATURE, photographed_sheet())
    beta = api(other_head, host="beta.localhost")

    assert beta.get("/api/school/stamp/").json()["code"] == "no_image"
    assert beta.get("/api/school/head-signature/").status_code == 404
    assert beta.get(f"/api/school/signatures/{cashier.pk}/").status_code == 404
    # Sur l'adresse de l'autre école, le compte de beta n'y a aucun accès.
    alpha = api(other_head)
    assert alpha.get("/api/school/stamp/").status_code == 403
    assert alpha.get(f"/api/school/signatures/{cashier.pk}/").status_code == 403
    assert send(alpha, MY_SIGNATURE, photographed_sheet()).status_code == 403


def test_each_person_signs_in_my_account(
    api, school, head, cashier, django_capture_on_commit_callbacks
):
    response = send(api(cashier), MY_SIGNATURE, photographed_sheet())

    assert response.status_code == 200
    documents = response.json()["school"]["documents"]
    assert documents["signature"].startswith(f"/api/school/signatures/{cashier.pk}/?v=")
    # Un collègue la voit sur un reçu de ce caissier qu'il réimprime.
    assert api(head).get(documents["signature"]).status_code == 200
    [entry] = journal(school, Action.STAFF_SIGNATURE_CHANGED)
    assert (entry.after, entry.actor_id) == ({"signature": True}, cashier.pk)

    file = Membership.objects.get(user=cashier, school=school).signature
    with django_capture_on_commit_callbacks(execute=True):
        removed = api(cashier).delete(MY_SIGNATURE)
    assert removed.json()["school"]["documents"]["signature"] is None
    assert not file.storage.exists(file.name)


def test_trapped_file_is_refused(api, school, cashier):
    response = send(api(cashier), MY_SIGNATURE, b"<svg onload=alert(1)>", "signature.png")

    assert response.status_code == 400
    assert response.json()["fields"]["image"][0]["code"] == "image_type"


def test_who_signs_the_documents_of_the_server(api, school, head):
    author = MembershipFactory(school=school, roles=["discipline_master"]).user
    with use_school(school):
        # Rien de déposé : le gabarit garde sa ligne à la main.
        assert signature_context(school) == {"signer": None, "stamp": ""}
        assert signature_context(school, author=author)["signer"]["name"] == str(author)

    send(api(author), MY_SIGNATURE, photographed_sheet())
    api(head).patch(
        "/api/school/settings/", {"head_name": "Kahindo Mapendo", "head_title": "Préfète"}
    )
    send(api(head), STAMP, photographed_sheet())
    school.refresh_from_db()
    with use_school(school):
        statement = signature_context(school)
        summons = signature_context(school, author=author)
        circular = signature_context(school, author=author, head_first=True)

    assert statement["signer"]["name"] == "Kahindo Mapendo"
    assert statement["signer"]["title"] == "Préfète"
    assert statement["signer"]["signature"] == ""
    assert statement["stamp"].startswith("data:image/png;base64,")
    assert summons["signer"]["signature"].startswith("data:image/png;base64,")
    assert circular["signer"] == statement["signer"]
    [entry] = journal(school, Action.SCHOOL_UPDATED)
    assert entry.after == {"head_name": "Kahindo Mapendo", "head_title": "Préfète"}

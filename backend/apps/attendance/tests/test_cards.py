"""Cartes d'élève et du personnel (6.1, A.5) : impression d'une sélection qui émet les cartes,
carte remplacée ou révoquée au journal, impression par lots des personnes sans carte, N° de carte,
photo officielle exigée et prise par l'école seule, carte « à réimprimer », isolation entre écoles
et droits."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Membership
from apps.attendance import cards
from apps.attendance.models import IdCard
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.models import PlatformSettings
from apps.core.tenancy import use_school
from apps.students import services as students
from apps.students.tests.conftest import enrolled
from tests.images import image_bytes

pytestmark = pytest.mark.django_db

PRINT = "/api/attendance/cards/print/"
STUDENTS = "/api/attendance/cards/students/"
STAFF = "/api/attendance/cards/staff/"
SUMMARY = "/api/attendance/cards/summary/"
ROSTER = "/api/attendance/roster/"
SETTINGS = "/api/school/settings/"


def revoke(client, card, reason="lost"):
    return client.post(f"/api/attendance/cards/{card.pk}/revoke/", {"reason": reason})


def pdf_of(client, result):
    return client.get(result["url"].split("?")[0], output="pdf")


PHOTOS = "/api/attendance/photos/"


def jpeg() -> SimpleUploadedFile:
    return SimpleUploadedFile("photo.jpg", image_bytes("JPEG"))


def send_photo(client, kind: str, pk):
    return client.client.post(
        f"{PHOTOS}{kind}/{pk}/", {"photo": jpeg()}, HTTP_HOST=client.host, **client.headers
    )


@pytest.fixture
def pupils(school, head, alpha):
    """Deux élèves inscrits, avec leur photo officielle (exigée par défaut sur la carte)."""
    found = [
        enrolled(school, head, alpha["group"], last_name=name, first_name="Élève")
        for name in ("Kambale", "Mapendo")
    ]
    with use_school(school):
        for pupil in found:
            students.set_photo(pupil, jpeg(), actor=head)
    return found


def test_printing_a_selection_issues_cards_and_reprinting_replaces_them(api, school, head, pupils):
    client = api(head)
    assert client.patch(SETTINGS, {"card": {"valid_until": "2099-08-31"}}).status_code == 200
    response = client.post(PRINT, {"students": [str(pupil.pk) for pupil in pupils]})
    assert response.status_code == 201, response.json()
    result = response.json()
    assert (result["issued"], result["remaining"]) == (2, 0)
    pdf = pdf_of(client, result)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    with use_school(school):
        issued = list(IdCard.objects.all())
        assert {str(card.valid_until) for card in issued} == {"2099-08-31"}
        assert AuditLog.objects.filter(action=Action.CARD_ISSUED).count() == 2

    # Le jeton n'est plus nulle part : réimprimer, c'est émettre une nouvelle carte.
    first = pupils[0]
    again = client.post(PRINT, {"students": [str(first.pk)], "layout": "card"})
    assert again.status_code == 201 and pdf_of(client, again.json()).status_code == 200
    with use_school(school):
        mine = IdCard.objects.filter(student=first)
        assert mine.filter(revoked_at__isnull=True).count() == 1
        assert mine.get(revoked_at__isnull=False).revoke_reason == "replaced"
        assert AuditLog.objects.filter(action=Action.CARD_REVOKED).count() == 1
    rows = {row["name"]: row for row in client.get(STUDENTS).json()["results"]}
    assert rows[first.full_name]["last_revoked"]["revoke_reason"] == "replaced"
    assert rows[first.full_name]["card"]["last4"] != rows[first.full_name]["last_revoked"]["last4"]


def test_people_without_a_card_are_printed_in_batches(api, school, head, pupils, monkeypatch):
    monkeypatch.setattr(cards, "MAX_PER_PRINT", 1)
    client = api(head)
    first = client.post(PRINT, {"missing": "students"}).json()
    assert (first["issued"], first["remaining"]) == (1, 1)
    assert client.get(STUDENTS, card="none").json()["count"] == 1
    second = client.post(PRINT, {"missing": "students"}).json()
    assert (second["issued"], second["remaining"]) == (1, 0)
    assert client.get(SUMMARY).json() == {
        "students": 2,
        "active": 2,
        "missing": 0,
        "lost_this_year": 0,
        "to_reprint": 0,
    }
    # Le directeur n'a pas encore de photo officielle : pas de carte tant qu'elle manque.
    refused = client.post(PRINT, {"missing": "staff"})
    assert (refused.status_code, refused.json()["without_photo"]) == (409, 1)
    client.patch(SETTINGS, {"card": {"require_photo": False}})
    staff = client.post(PRINT, {"missing": "staff"}).json()
    assert staff["issued"] == 1
    assert client.get(STAFF).json()["results"][0]["card"] is not None


def test_cards_are_numbered_in_order_and_a_changed_photo_asks_for_a_reprint(
    api, school, head, alpha, pupils
):
    client = api(head)
    late = enrolled(school, head, alpha["group"], last_name="Safari", first_name="Sans photo")
    everyone = [str(pupil.pk) for pupil in [*pupils, late]]
    result = client.post(PRINT, {"students": everyone}).json()
    assert (result["issued"], result["without_photo"]) == (2, 1)
    alone = client.post(PRINT, {"students": [str(late.pk)]})
    assert (alone.status_code, alone.json()["code"]) == (409, "card_needs_photo")

    first = pupils[0]
    client.post(PRINT, {"students": [str(first.pk)]})
    with use_school(school):
        assert sorted(IdCard.objects.values_list("number", flat=True)) == [1, 2, 3]
        assert IdCard.objects.get(student=first, revoked_at=None).number == 3
        log = AuditLog.objects.filter(action=Action.CARD_ISSUED).latest("created_at")
        assert log.after["number"] == 3

    # Nouvelle photo prise à la séance photo : au journal, et la carte est à réimprimer.
    assert send_photo(client, "students", first.pk).status_code == 200
    rows = {row["name"]: row for row in client.get(STUDENTS).json()["results"]}
    assert rows[first.full_name]["needs_reprint"] is True
    assert rows[pupils[1].full_name]["needs_reprint"] is False
    assert client.get(SUMMARY).json()["to_reprint"] == 1
    with use_school(school):
        replaced = AuditLog.objects.filter(
            action=Action.STUDENTS_STUDENT_UPDATED, entity_id=first.pk
        ).latest("created_at")
        assert replaced.before["photo"] != replaced.after["photo"]
    again = client.post(PRINT, {"missing": "reprint"}).json()
    assert (again["issued"], again["remaining"]) == (1, 0)
    assert client.get(SUMMARY).json()["to_reprint"] == 0


def test_staff_photo_is_taken_by_the_school_only_and_shown_at_the_door(
    api, school, head, cashier, other_head, beta
):
    member = Membership.objects.get(user=cashier, school=school)
    client = api(head)
    # La personne elle-même ne change jamais sa photo officielle (pas le droit des cartes).
    assert send_photo(api(cashier), "staff", member.pk).status_code == 403
    taken = send_photo(client, "staff", member.pk)
    assert taken.status_code == 200
    roster = {row["member"]: row for row in client.get(ROSTER).json()["staff"]}
    assert roster[str(member.pk)]["photo"] == taken.json()["photo"]
    image = client.get(taken.json()["photo"].split("?")[0])
    assert (image.status_code, image["Content-Type"]) == (200, "image/jpeg")
    with use_school(school):
        log = AuditLog.objects.get(action=Action.STAFF_PHOTO_CHANGED)
        assert (log.actor_id, log.after) == (head.pk, {"photo": True})
    other = api(other_head, host="beta.localhost")
    assert other.get(f"{PHOTOS}staff/{member.pk}/").status_code == 404
    assert send_photo(other, "staff", member.pk).status_code == 404


def test_the_printed_card_follows_the_platform_and_hides_private_fields_by_default(
    school, head, alpha
):
    """Ministère réglé par la plateforme (plus « EPST » en dur) ; téléphone du responsable et
    adresse absents tant que l'école ne les coche pas (une carte perdue est lue par tous)."""
    PlatformSettings.objects.update_or_create(pk=1, defaults={"ministry_line": "Ministère XYZ"})
    pupil = enrolled(school, head, alpha["group"], last_name="Kambale", first_name="Josué")
    with use_school(school):
        enrollment = cards.students_list().get(student=pupil)
        issued = cards.issue(actor=head, enrollments=[enrollment])
        _head, bodies = cards.document(issued, {pupil.pk: enrollment}, cards.CARD)
        front, back = bodies
        assert "Ministère XYZ" in front and "0001" in front and pupil.matricule in front
        assert "+243" not in back
        school.settings = {"card": {"printed_fields": ["guardian_phone"]}}
        school.save()
        _head, (front, back) = cards.document(issued, {pupil.pk: enrollment}, cards.CARD)
        assert "+243" in back


def test_a_revoked_card_is_gone_from_the_roster_and_cannot_be_revoked_twice(
    api, school, head, pupils
):
    client = api(head)
    client.post(PRINT, {"students": [str(pupils[0].pk)]})
    with use_school(school):
        card = IdCard.objects.get()
    before = client.get(ROSTER).json()
    hashes = {row["card_hash"] for row in before["students"]}
    assert card.token_hash in hashes
    assert before["matricule_check"] is False
    assert before["students"][0]["photo"].startswith(f"{PHOTOS}students/")
    # Rien à envoyer tant que rien ne change.
    assert client.get(ROSTER, version=before["version"]).json()["unchanged"] is True

    assert revoke(client, card).status_code == 200
    assert revoke(client, card).json()["code"] == "card_already_revoked"
    after = client.get(ROSTER, version=before["version"]).json()
    assert after["unchanged"] is False
    assert card.token_hash not in {row["card_hash"] for row in after["students"]}
    with use_school(school):
        log = AuditLog.objects.get(action=Action.CARD_REVOKED)
        assert (log.actor_id, log.after) == (head.pk, {"reason": "lost"})
    assert client.get(SUMMARY).json()["lost_this_year"] == 1


def test_cards_of_one_school_are_never_seen_printed_or_revoked_by_another(
    api, school, head, pupils, other_head, beta
):
    result = api(head).post(PRINT, {"students": [str(pupils[0].pk)]}).json()
    with use_school(school):
        card = IdCard.objects.get()
    other = api(other_head, host="beta.localhost")
    assert other.get(STUDENTS).json()["count"] == 0
    assert other.post(PRINT, {"students": [str(pupils[0].pk)]}).status_code == 400
    assert revoke(other, card).status_code == 404
    assert other.get(ROSTER).json()["students"] == []
    # Photo officielle : ni lue ni changée par l'autre école.
    assert other.get(f"{PHOTOS}students/{pupils[0].pk}/").status_code == 404
    assert send_photo(other, "students", pupils[0].pk).status_code == 404
    # Le PDF n'est servi qu'à qui l'a demandé, dans son école.
    assert pdf_of(other, result).status_code == 410
    with use_school(school):
        assert IdCard.objects.get().revoked_at is None


def test_cards_and_the_roster_need_their_right_and_the_module(api, school, head, cashier, pupils):
    clerk = api(cashier)
    assert clerk.get(STUDENTS).status_code == 403
    assert clerk.post(PRINT, {"missing": "students"}).status_code == 403
    assert clerk.get(ROSTER).status_code == 403
    assert clerk.get(f"{PHOTOS}students/{pupils[0].pk}/").status_code == 403
    school.modules = [code for code in school.modules if code != "attendance"]
    school.save()
    assert api(head).post(PRINT, {"missing": "students"}).status_code == 403

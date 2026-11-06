"""Cartes d'élève et du personnel (6.1, A.5) : impression d'une sélection qui émet les cartes,
carte remplacée ou révoquée au journal, impression par lots des personnes sans carte, isolation
entre écoles et droits."""

import pytest

from apps.attendance import cards
from apps.attendance.models import IdCard
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.students.tests.conftest import enrolled

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


@pytest.fixture
def pupils(school, head, alpha):
    return [
        enrolled(school, head, alpha["group"], last_name=name, first_name="Élève")
        for name in ("Kambale", "Mapendo")
    ]


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
    }
    staff = client.post(PRINT, {"missing": "staff"}).json()
    assert staff["issued"] == 1
    assert client.get(STAFF).json()["results"][0]["card"] is not None


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
    # Le PDF n'est servi qu'à qui l'a demandé, dans son école.
    assert pdf_of(other, result).status_code == 410
    with use_school(school):
        assert IdCard.objects.get().revoked_at is None


def test_cards_and_the_roster_need_their_right_and_the_module(api, school, head, cashier, pupils):
    clerk = api(cashier)
    assert clerk.get(STUDENTS).status_code == 403
    assert clerk.post(PRINT, {"missing": "students"}).status_code == 403
    assert clerk.get(ROSTER).status_code == 403
    school.modules = [code for code in school.modules if code != "attendance"]
    school.save()
    assert api(head).post(PRINT, {"missing": "students"}).status_code == 403

"""Communication de l'école (5.7) : annonce au personnel (lue par tous, jamais par une famille),
calendrier (lu par tous, écrit avec le droit), convocations (journal, annulation, lettre),
circulaire ; droits et isolation entre deux écoles."""

from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.notifications.models import Notification
from apps.students.tests.conftest import enrolled, new_student

pytestmark = pytest.mark.django_db

ANNOUNCEMENTS = "/api/announcements/"
STAFF_NEWS = "/api/staff-announcements/"
EVENTS = "/api/calendar-events/"
SUMMONS = "/api/summons/"
PDF = b"%PDF-1.4\n% note de service\n"


def to_staff(client, *, pdf=False):
    data = {"title": "Conseil des enseignants", "body": "Vendredi à 14 h.", "audience": "staff"}
    if pdf:
        data["attachment"] = SimpleUploadedFile("note.pdf", PDF)
    return client.client.post(ANNOUNCEMENTS, data, HTTP_HOST=client.host)


def event(client, **fields):
    day = (timezone.localdate() + timedelta(days=10)).isoformat()
    return client.post(EVENTS, {"title": "Réunion des parents", "starts_on": day, **fields})


def summon(client, student, **fields):
    data = {
        "student": str(student.pk),
        "reason": "Absences répétées depuis deux semaines.",
        "meeting_at": (timezone.now() + timedelta(days=3)).isoformat(),
        "meet_with": "Directeur de discipline",
        **fields,
    }
    return client.post(SUMMONS, data)


def test_staff_announcement_is_read_by_all_the_staff_and_notified_except_its_author(
    api, school, head, cashier, alpha
):
    enrolled(school, head, alpha["group"])
    recipients = api(head).get(f"{ANNOUNCEMENTS}recipients/", audience="staff").json()
    assert recipients == {"families": 0, "staff": 2}

    response = to_staff(api(head), pdf=True)
    assert response.status_code == 201, response.json()
    assert response.json()["class_groups"] == []

    # La caissière ne publie rien, mais elle la lit, avec son PDF.
    reader = api(cashier)
    [announcement] = reader.get(STAFF_NEWS).json()["results"]
    assert (announcement["title"], announcement["published_by"]["id"]) == (
        "Conseil des enseignants",
        str(head.pk),
    )
    pdf = reader.client.get(announcement["attachment"], HTTP_HOST=reader.host)
    assert b"".join(pdf.streaming_content) == PDF
    with use_school(school):
        notified = Notification.objects.filter(kind=Notification.Kind.STAFF_ANNOUNCEMENT)
        assert [(n.user, n.app, n.url) for n in notified] == [(cashier, "gestion", "/staff-news")]
        log = AuditLog.objects.get(action=Action.ANNOUNCEMENTS_PUBLISHED)
    assert (log.after["audience"], log.after["staff"]) == ("staff", 2)
    assert "families" not in log.after

    # Archivée : le personnel ne la voit plus.
    api(head).post(f"{ANNOUNCEMENTS}{announcement['id']}/archive/")
    assert reader.get(STAFF_NEWS).json()["count"] == 0


def test_calendar_is_read_by_all_the_staff_and_written_with_the_permission(api, head, cashier):
    client = api(head)
    created = event(client, kind="meeting", start_time="09:00")
    assert created.status_code == 201, created.json()
    meeting = created.json()
    assert meeting["ends_on"] == meeting["starts_on"]  # une seule journée
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
    event(client, title="Journée sportive", starts_on=yesterday)
    refused = event(client, ends_on=date(2020, 1, 1).isoformat())
    assert refused.status_code == 400
    assert refused.json()["fields"]["ends_on"][0]["code"] == "ends_before_start"

    reader = api(cashier)
    assert [e["title"] for e in reader.get(EVENTS).json()["results"]] == ["Réunion des parents"]
    assert [e["title"] for e in reader.get(EVENTS, past="true").json()["results"]] == [
        "Journée sportive"
    ]
    detail = f"{EVENTS}{meeting['id']}/"
    assert event(reader).status_code == 403
    assert reader.patch(detail, {"title": "Annulée"}).status_code == 403
    assert reader.delete(detail).status_code == 403

    assert client.patch(detail, {"audience": "staff"}).json()["audience"] == "staff"
    assert client.delete(detail).status_code == 204
    assert reader.get(EVENTS).json()["count"] == 0


def test_summons_is_audited_printed_and_cancelled_never_edited(api, school, head, cashier, alpha):
    student = enrolled(school, head, alpha["group"])
    client = api(head)
    response = summon(client, student)
    assert response.status_code == 201, response.json()
    summons = response.json()
    assert (summons["class_name"], summons["student"]["full_name"], summons["seen_at"]) == (
        alpha["group"].name,
        student.full_name,
        None,
    )
    with use_school(school):
        log = AuditLog.objects.get(action=Action.SUMMONS_ISSUED)
    assert (log.actor, log.after["student"], log.after["meet_with"]) == (
        head,
        student.full_name,
        "Directeur de discipline",
    )

    detail = f"{SUMMONS}{summons['id']}/"
    letter = client.get(f"{detail}letter/", output="html").content.decode()
    assert student.full_name in letter
    assert "Absences répétées" in letter

    # Jour passé, ou élève qui n'est pas inscrit cette année : refusé.
    past = summon(client, student, meeting_at=(timezone.now() - timedelta(days=1)).isoformat())
    assert past.json()["fields"]["meeting_at"][0]["code"] == "in_the_past"
    not_enrolled = summon(client, new_student(school, head, last_name="Paluku"))
    assert not_enrolled.json()["fields"]["student"][0]["code"] == "not_enrolled"

    assert client.post(f"{detail}cancel/").json()["cancelled_at"] is not None
    assert client.post(f"{detail}cancel/").status_code == 200
    with use_school(school):
        assert AuditLog.objects.filter(action=Action.SUMMONS_CANCELLED).count() == 1

    # Sans le droit de publier : rien.
    other = api(cashier)
    assert other.get(SUMMONS).status_code == 403
    assert summon(other, student).status_code == 403
    assert other.post(f"{detail}cancel/").status_code == 403
    assert other.get(f"{detail}letter/").status_code == 403
    assert other.get(f"{ANNOUNCEMENTS}{summons['id']}/circular/").status_code == 403


def test_another_school_neither_reads_nor_writes_the_communication(
    api, school, head, other_head, alpha, beta
):
    student = enrolled(school, head, alpha["group"])
    client = api(head)
    announcement = to_staff(client, pdf=True).json()
    meeting = event(client).json()
    summons = summon(client, student).json()
    assert (
        "Conseil des enseignants"
        in client.get(
            f"{ANNOUNCEMENTS}{announcement['id']}/circular/", output="html"
        ).content.decode()
    )

    other = api(other_head, host="beta.localhost")
    for path in (STAFF_NEWS, EVENTS, SUMMONS):
        assert other.get(path).json()["count"] == 0
    assert other.get(f"{STAFF_NEWS}{announcement['id']}/attachment/").status_code == 404
    assert other.get(f"{ANNOUNCEMENTS}{announcement['id']}/circular/").status_code == 404
    assert other.patch(f"{EVENTS}{meeting['id']}/", {"title": "Piraté"}).status_code == 404
    assert other.delete(f"{EVENTS}{meeting['id']}/").status_code == 404
    assert other.post(f"{SUMMONS}{summons['id']}/cancel/").status_code == 404
    assert other.get(f"{SUMMONS}{summons['id']}/letter/").status_code == 404
    # Un élève d'une autre école est « introuvable ».
    assert summon(other, student).status_code == 400

    # À l'adresse d'alpha, le directeur de beta n'est personne.
    stranger = api(other_head)
    for path in (STAFF_NEWS, EVENTS, SUMMONS):
        assert stranger.get(path).status_code == 403

    assert client.get(EVENTS).json()["results"][0]["title"] == "Réunion des parents"
    assert client.get(SUMMONS).json()["results"][0]["cancelled_at"] is None

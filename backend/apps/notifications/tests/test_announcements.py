"""Annonces aux familles (H4) : droits, isolation entre écoles, familles touchées (une fratrie
compte une fois, seulement les inscriptions actives des classes choisies), pièce jointe PDF,
audit de la publication et de l'archivage."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.students import services as students
from apps.students.models import Enrollment
from apps.students.tests.conftest import enrolled

pytestmark = pytest.mark.django_db

ANNOUNCEMENTS = "/api/announcements/"
PDF = b"%PDF-1.4\n% convocation\n"


def publish(client, *, audience="all_families", class_groups=(), content: bytes | None = None):
    data = {
        "title": "Réunion des parents de 3e année",
        "body": "Samedi à 9 h dans la grande salle.",
        "audience": audience,
        "class_groups": [str(group.pk) for group in class_groups],
    }
    if content is not None:
        data["attachment"] = SimpleUploadedFile("convocation.pdf", content)
    return client.client.post(ANNOUNCEMENTS, data, HTTP_HOST=client.host)


@pytest.fixture
def classes(school, head, alpha):
    """3e Électricité A : une fratrie et un élève qui a abandonné ; 4e Électricité A : un élève."""
    group = alpha["group"]
    with use_school(school):
        other = organisation.create_class_group(
            actor=head,
            academic_year=alpha["year"],
            level=alpha["other_level"],
            track=alpha["track"],
            section="A",
            capacity=45,
        )
    elder = enrolled(school, head, group, first_name="Grâce")
    with use_school(school):
        sibling, _created = students.create_student(
            actor=head, family=elder.family, last_name="Kasereka", first_name="Josué", sex="M"
        )
        students.enroll(sibling, actor=head, class_group=group)
    dropped = enrolled(school, head, group, last_name="Paluku")
    with use_school(school):
        Enrollment.objects.filter(student=dropped).update(status=Enrollment.Status.DROPPED)
    enrolled(school, head, other, last_name="Amani")
    return {"group": group, "other": other}


def test_publish_for_some_classes_counts_each_family_once_and_is_audited(
    api, school, head, classes
):
    client = api(head)
    recipients = f"{ANNOUNCEMENTS}recipients/"
    group = classes["group"]
    assert client.get(recipients, audience="all_families").json() == {"families": 2, "staff": 0}
    assert client.get(recipients, audience="class_groups", class_groups=[group.pk]).json() == {
        "families": 1,
        "staff": 0,
    }

    response = publish(client, audience="class_groups", class_groups=[group], content=PDF)
    assert response.status_code == 201, response.json()
    announcement = response.json()
    assert [g["name"] for g in announcement["class_groups"]] == [group.name]
    assert announcement["published_by"]["id"] == str(head.pk)
    pdf = client.client.get(announcement["attachment"], HTTP_HOST=client.host)
    assert pdf["Content-Type"] == "application/pdf"
    assert b"".join(pdf.streaming_content) == PDF

    with use_school(school):
        log = AuditLog.objects.get(action=Action.ANNOUNCEMENTS_PUBLISHED)
    assert log.actor == head
    assert log.after == {
        "title": "Réunion des parents de 3e année",
        "audience": "class_groups",
        "class_groups": [group.name],
        "attachment": True,
        "families": 1,
    }


def test_refused_without_class_or_with_a_file_that_is_not_a_pdf(api, head, classes):
    client = api(head)
    response = publish(client, audience="class_groups")
    assert response.status_code == 400
    assert "class_groups" in response.json()["fields"]
    response = publish(client, content=b"\x89PNG\r\n\x1a\n image")
    assert response.status_code == 400
    assert response.json()["fields"]["attachment"][0]["code"] == "attachment_type"
    assert client.get(ANNOUNCEMENTS).json()["count"] == 0


def test_archive_once_and_audited(api, school, head, classes):
    client = api(head)
    announcement = publish(client).json()
    archive = f"{ANNOUNCEMENTS}{announcement['id']}/archive/"
    assert client.post(archive).json()["archived_at"] is not None
    assert client.post(archive).status_code == 200
    with use_school(school):
        assert AuditLog.objects.filter(action=Action.ANNOUNCEMENTS_ARCHIVED).count() == 1


def test_publish_requires_the_permission(api, cashier, head, classes):
    client = api(cashier)
    assert client.get(ANNOUNCEMENTS).status_code == 403
    assert publish(client).status_code == 403
    assert client.get(f"{ANNOUNCEMENTS}recipients/", audience="all_families").status_code == 403
    announcement = publish(api(head)).json()
    assert client.post(f"{ANNOUNCEMENTS}{announcement['id']}/archive/").status_code == 403


def test_another_school_neither_reads_nor_archives_nor_targets_the_classes(
    api, school, head, other_head, classes, beta
):
    announcement = publish(api(head), content=PDF).json()
    other = api(other_head, host="beta.localhost")
    assert other.get(ANNOUNCEMENTS).json()["count"] == 0
    assert other.post(f"{ANNOUNCEMENTS}{announcement['id']}/archive/").status_code == 404
    attachment = other.client.get(announcement["attachment"], HTTP_HOST=other.host)
    assert attachment.status_code == 404
    response = publish(other, audience="class_groups", class_groups=[classes["group"]])
    assert response.status_code == 400
    recipients = other.get(
        f"{ANNOUNCEMENTS}recipients/", audience="class_groups", class_groups=[classes["group"].pk]
    )
    assert recipients.status_code == 400
    assert other.get(f"{ANNOUNCEMENTS}recipients/", audience="all_families").json() == {
        "families": 0,
        "staff": 0,
    }
    with use_school(school):
        assert AuditLog.objects.filter(action=Action.ANNOUNCEMENTS_ARCHIVED).count() == 0

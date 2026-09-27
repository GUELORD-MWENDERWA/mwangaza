"""Fiche élève (M9) et fiche famille (M10) : photo servie par l'API avec le consentement du
parent, historique lu dans le journal, doublon signalé avec la fiche existante, liaison à une
autre famille. Toujours dans l'école de l'adresse."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.students import services
from apps.students.models import Family, Student
from apps.students.tests.conftest import GUARDIAN, enrolled, new_student
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

STUDENTS = "/api/students/"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64


def photo_path(student) -> str:
    return f"{STUDENTS}{student.pk}/photo/"


def upload(client, student, content: bytes = JPEG):
    return client.client.post(
        photo_path(student),
        {"photo": SimpleUploadedFile("photo.jpg", content)},
        HTTP_HOST=client.host,
    )


def test_photo_is_served_only_to_the_school_and_replaced_cleanly(
    api, school, head, cashier, other_head, django_capture_on_commit_callbacks
):
    student = new_student(school, head)
    client = api(head)

    wrong_type = upload(client, student, b"%PDF-1.7")
    uploaded = upload(client, student)
    detail = client.get(f"{STUDENTS}{student.pk}/").json()

    assert wrong_type.status_code == 400
    assert uploaded.status_code == 200
    assert detail["photo"].startswith(photo_path(student))
    image = api(cashier).get(photo_path(student))
    assert (image.status_code, image["Content-Type"]) == (200, "image/jpeg")
    assert b"".join(image.streaming_content) == JPEG
    # Lire n'est pas changer ; l'autre école ne voit ni ne change rien.
    assert upload(api(cashier), student).status_code == 403
    beta = api(other_head, host="beta.localhost")
    assert beta.get(photo_path(student)).status_code == 404
    assert upload(beta, student).status_code == 404
    assert beta.delete(photo_path(student)).status_code == 404
    with use_school(school):
        stored = Student.objects.get(pk=student.pk).photo
        logged = AuditLog.objects.get(action=Action.STUDENTS_STUDENT_UPDATED)
    assert (logged.before, logged.after) == ({"photo": False}, {"photo": True})

    # Retirée : l'ancien fichier disparaît après l'enregistrement.
    with django_capture_on_commit_callbacks(execute=True):
        assert client.delete(photo_path(student)).json()["photo"] is None
    assert client.get(photo_path(student)).status_code == 404
    assert not stored.storage.exists(stored.name)


def test_history_of_the_student_its_enrollments_and_its_family(
    api, school, head, other_head, alpha
):
    student = enrolled(school, head, alpha["group"])
    other = new_student(school, head, last_name="Imani")
    with use_school(school):
        services.update_student(student, actor=head, first_name="Jean-Paul")
        services.update_family(
            student.family, actor=head, guardians=[{**GUARDIAN, "phone": "+243812345678"}]
        )
        services.update_student(other, actor=head, first_name="Autre")
    nobody = MembershipFactory(school=school).user
    path = f"{STUDENTS}{student.pk}/history/"

    rows = api(head).get(path).json()["results"]

    assert [row["action"] for row in rows] == [
        Action.STUDENTS_FAMILY_UPDATED,
        Action.STUDENTS_STUDENT_UPDATED,
        Action.STUDENTS_ENROLLED,
        Action.STUDENTS_STUDENT_CREATED,
        Action.STUDENTS_FAMILY_CREATED,
    ]
    assert rows[1]["after"] == {"first_name": "Jean-Paul"}
    assert "ip" not in rows[0] and "user_agent" not in rows[0]
    assert api(nobody).get(path).status_code == 403
    assert api(other_head, host="beta.localhost").get(path).status_code == 404


def test_a_possible_duplicate_points_to_the_existing_student(api, school, head):
    existing = new_student(school, head, birth_date=date(2012, 3, 14))
    with use_school(school):
        services.update_student(existing, actor=head, matricule="A-0001")
    body = {"last_name": "Kasereka", "first_name": "Jean", "sex": "M", "birth_date": "2012-03-14"}

    response = api(head).post(STUDENTS, {**body, "guardians": [GUARDIAN]})

    assert response.status_code == 409
    assert response.json()["duplicates"] == [
        {
            "id": str(existing.pk),
            "last_name": "Kasereka",
            "middle_name": "",
            "first_name": "Jean",
            "matricule": "A-0001",
        }
    ]


def test_linking_to_another_family_removes_the_family_left_empty(api, school, head):
    student = new_student(school, head)
    family = student.family
    with use_school(school):
        sibling, _ = services.create_student(
            actor=head, family=family, last_name="Kasereka", first_name="Esther", sex="F"
        )
    target = new_student(school, head, last_name="Imani").family
    client = api(head)

    # La famille garde l'autre enfant ; puis elle est vide et disparaît.
    client.patch(f"{STUDENTS}{student.pk}/", {"family": str(target.pk)})
    with use_school(school):
        kept = Family.objects.filter(pk=family.pk).exists()
    client.patch(f"{STUDENTS}{sibling.pk}/", {"family": str(target.pk)})

    with use_school(school):
        assert kept and not Family.objects.filter(pk=family.pk).exists()
        assert target.students.count() == 3
        deleted = AuditLog.objects.filter(action=Action.STUDENTS_FAMILY_DELETED)
        assert [log.entity_id for log in deleted] == [family.pk]

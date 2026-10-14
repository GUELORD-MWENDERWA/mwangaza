"""API des élèves : `students.view` / `students.edit`, isolation entre écoles (liste, recherche,
fiche, modification, familles, inscriptions), liste sans requêtes en rafale."""

import pytest

from apps.core.ids import uuid7
from apps.core.tenancy import use_all_schools, use_school
from apps.students.models import Enrollment
from apps.students.tests.conftest import GUARDIAN, enrolled, new_student
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

STUDENTS = "/api/students/"
FAMILIES = "/api/families/"
ENROLLMENTS = "/api/enrollments/"


def test_rights(api, school, head, cashier, alpha):
    student = new_student(school, head)
    nobody = MembershipFactory(school=school).user

    assert api(nobody).get(STUDENTS).status_code == 403
    # Le caissier lit les élèves (pour encaisser) mais ne les modifie pas.
    assert api(cashier).get(f"{STUDENTS}{student.pk}/").status_code == 200
    for path, body in [
        (STUDENTS, {"last_name": "Imani", "sex": "F"}),
        (FAMILIES, {"guardians": []}),
        (ENROLLMENTS, {"student": str(student.pk), "class_group": str(alpha["group"].pk)}),
    ]:
        assert api(cashier).post(path, body).status_code == 403
    assert api(cashier).patch(f"{STUDENTS}{student.pk}/", {"first_name": "X"}).status_code == 403


def test_create_enroll_and_read_a_student(api, head, alpha):
    client = api(head)
    student_id = str(uuid7())
    body = {"id": student_id, "last_name": "Kasereka", "first_name": "Jean", "sex": "M"}
    created = client.post(STUDENTS, {**body, "guardians": [GUARDIAN]})
    replayed = client.post(STUDENTS, {**body, "guardians": [GUARDIAN]})
    enrollment = client.post(
        ENROLLMENTS, {"student": student_id, "class_group": str(alpha["group"].pk)}
    )
    detail = client.get(f"{STUDENTS}{student_id}/").json()

    assert (created.status_code, replayed.status_code, enrollment.status_code) == (201, 200, 201)
    assert detail["matricule"] == "ALPHA-2026-0001"
    assert detail["family"]["guardians"][0]["phone"] == "+243971234567"
    assert detail["enrollments"][0]["class_group_name"] == "3e Électricité A"


def test_search_and_filters(api, school, head, alpha, beta):
    jean = enrolled(school, head, alpha["group"], middle_name="Mumbere")
    elie = enrolled(school, head, alpha["group"], last_name="Paluku", first_name="Élie")
    esther = new_student(school, head, last_name="Kavira", first_name="Esther", sex="F")
    with use_school(school):
        Enrollment.objects.filter(student=elie).update(status="transferred")
    client = api(head)

    def names(**params):
        return [row["first_name"] for row in client.get(STUDENTS, **params).json()["results"]]

    assert names(search="mumb kase") == ["Jean"]
    assert names(search="ELIE") == names(search="élie") == ["Élie"]
    assert names(search="2026-0001") == ["Jean"]
    with use_all_schools():
        assert names(search=esther.family.code) == ["Esther"]
    assert names(class_group=str(alpha["group"].pk)) == ["Jean", "Élie"]
    assert names(track=str(alpha["track"].pk), status="active") == ["Jean"]
    assert names(status="left") == ["Élie"]
    assert names(status="not_enrolled") == ["Esther"]
    # Une option d'une autre école n'est pas un filtre valable.
    assert client.get(STUDENTS, track=str(beta["track"].pk)).status_code == 400
    [row] = client.get(STUDENTS, search="jean").json()["results"]
    assert row["enrollment"]["class_group_name"] == "3e Électricité A"
    with use_all_schools():
        assert row["family_code"] == jean.family.code
    assert row["primary_guardian"]["full_name"] == "Kahindo Neema"


def test_the_list_reads_a_fixed_number_of_queries(
    api, school, head, alpha, django_assert_max_num_queries
):
    for first_name in ["Jean", "Esther", "Paul", "Neema", "Amani"]:
        enrolled(school, head, alpha["group"], first_name=first_name)
    client = api(head)

    with django_assert_max_num_queries(13):
        assert client.get(STUDENTS).json()["count"] == 5
    with django_assert_max_num_queries(13):
        assert client.get(FAMILIES).json()["count"] == 5


def test_another_school_neither_reads_nor_changes(
    api, school, other_school, head, other_head, alpha, beta
):
    student = enrolled(school, head, alpha["group"])
    beta_student = new_student(other_school, other_head, last_name="Kasereka")
    with use_school(school):
        enrollment = Enrollment.objects.get()
        family = student.family
    client = api(other_head, host="beta.localhost")

    assert [row["id"] for row in client.get(STUDENTS, search="kasereka").json()["results"]] == [
        str(beta_student.pk)
    ]
    assert client.get(FAMILIES, search=family.code).json()["results"] == []
    assert client.get(f"{STUDENTS}{student.pk}/").status_code == 404
    assert client.get(f"{FAMILIES}{family.pk}/").status_code == 404
    assert client.patch(f"{STUDENTS}{student.pk}/", {"first_name": "X"}).status_code == 404
    assert client.patch(f"{FAMILIES}{family.pk}/", {"guardians": []}).status_code == 404
    assert client.patch(f"{ENROLLMENTS}{enrollment.pk}/", {"status": "dropped"}).status_code == 404
    # Ni relier un élève à une famille d'une autre école, ni l'inscrire dans une de ses classes.
    linked = client.patch(f"{STUDENTS}{beta_student.pk}/", {"family": str(family.pk)})
    enrolled_there = client.post(
        ENROLLMENTS, {"student": str(beta_student.pk), "class_group": str(alpha["group"].pk)}
    )
    assert (linked.status_code, enrolled_there.status_code) == (400, 400)
    # Un identifiant d'élève de l'autre école n'écrase rien.
    taken = client.post(STUDENTS, {"id": str(student.pk), "last_name": "X", "sex": "M"})
    assert taken.status_code == 409
    with use_all_schools():
        student.refresh_from_db()
    assert student.first_name == "Jean"


def test_families_search_by_guardian(api, school, head):
    family = new_student(school, head).family
    client = api(head)

    for search in ["kahindo", "0971234567", family.code.lower()]:
        [row] = client.get(FAMILIES, search=search).json()["results"]
        assert (row["id"], row["student_count"]) == (str(family.pk), 1)
    [child] = row["students"]
    assert (child["first_name"], child["class_group_name"]) == ("Jean", "")


def test_class_count_and_next_matricule(api, school, head, alpha):
    enrolled(school, head, alpha["group"])
    dropped = enrolled(school, head, alpha["group"], first_name="Paul")
    with use_school(school):
        Enrollment.objects.filter(student=dropped).update(status="dropped")
    client = api(head)

    [group] = client.get("/api/class-groups/").json()
    assert (group["student_count"], group["capacity"]) == (1, 45)
    assert client.get("/api/matricule-format/").json()["example"] == "ALPHA-2026-0003"

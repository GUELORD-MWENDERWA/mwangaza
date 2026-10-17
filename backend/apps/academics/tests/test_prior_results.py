"""Reprise des résultats (8.4.7) : un élève sans aucune note cette année reçoit sa décision et le
pourcentage obtenu hors de Mwangaza, saisis dans la délibération ou importés du modèle Excel ;
jamais pour un élève noté ni dans une classe proclamée ; fichier envoyé deux fois sans effet,
aperçu périmé ; figé à la proclamation ; droits, isolation, journal."""

import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.academics.models import DeliberationSnapshot
from apps.academics.tests import test_resits
from apps.academics.tests.test_deliberation import decide
from apps.academics.tests.test_grades import setup
from apps.audit.models import AuditLog
from apps.core.documents import workbook
from apps.core.tenancy import use_school
from apps.students.models import Enrollment
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

physics_teacher = test_resits.physics_teacher
URL = "/api/deliberation/prior-results/"


@pytest.fixture
def data(school, head, physics_teacher):
    """Classe A notée (Bahati, Kambale) ; classe B sans aucune note (Sikuli, inscription `b`)."""
    data = setup(school, head, teacher=physics_teacher)
    test_resits.fill_year(school, data, data["physics"], {data["amani"]: 70, data["josue"]: 48})
    with use_school(school):
        data["class_b"] = Enrollment.objects.get(pk=data["b"]).class_group
    return data


@pytest.fixture
def director(api, school):
    return api(MembershipFactory(school=school, roles=["study_director"]).user)


def class_b(data, tail="") -> str:
    return f"/api/class-groups/{data['class_b'].pk}/deliberation/{tail}"


def row(client, data, key) -> dict:
    return next(
        r for r in client.get(class_b(data)).json()["students"] if r["enrollment"] == data[key]
    )


def send(client, data, rows, *, expected=None, held_on="2026-06-30"):
    body = {
        "file": SimpleUploadedFile(
            "resultats.xlsx", workbook(["MATRICULE", "DÉCISION", "%", "POURCENTAGE"], rows)
        ),
        "academic_year": str(data["year"].pk),
    }
    if expected is not None:
        body |= {"expected": expected, "held_on": held_on}
    return client.client.post(URL, body, HTTP_HOST=client.host)


def decided_log(school) -> int:
    with use_school(school):
        return AuditLog.objects.filter(action="deliberation.decided").count()


def test_a_student_without_grades_gets_a_prior_percent_frozen_at_proclamation(
    school, director, data
):
    # Kambale a des notes : son pourcentage se calcule, il ne se saisit pas.
    refused = director.put(
        f"/api/deliberation/enrollments/{data['josue']}/", {"decision": "resit", "percent": "50"}
    )
    assert (refused.status_code, refused.json()["code"]) == (400, "has_grades")
    too_high = director.put(
        f"/api/deliberation/enrollments/{data['b']}/", {"decision": "pass", "percent": "100.5"}
    )
    assert too_high.json()["code"] == "bad_percent"

    assert row(director, data, "b")["outcome"] == "unranked"
    done = director.put(
        f"/api/deliberation/enrollments/{data['b']}/", {"decision": "pass", "percent": "62.5"}
    )
    assert done.status_code == 200
    assert (row(director, data, "b")["percent"], row(director, data, "b")["deviates"]) == (
        "62.5",
        False,
    )
    with use_school(school):
        entry = AuditLog.objects.filter(action="deliberation.decided").latest("created_at")
    assert entry.after["prior_percent"] == "62.5"

    assert director.put(class_b(data), {"held_on": "2026-06-30"}).status_code == 200
    assert director.post(class_b(data, "proclaim/")).status_code == 200
    with use_school(school):
        [frozen] = DeliberationSnapshot.objects.get(deliberation__class_group=data["class_b"]).rows
    assert (frozen["percent"], frozen["decision"]) == ("62.5", "pass")


def test_the_school_imports_last_years_results_from_its_template(api, school, head, director, data):
    for key, name in (("kahindo", "Kahindo"), ("muhindo", "Muhindo")):
        student = enrolled(school, head, data["class_b"], last_name=name, first_name="X")
        with use_school(school):
            data[key] = str(student.enrollments.get().pk)
    with use_school(school):
        matricule = {
            str(e.pk): e.student.matricule for e in Enrollment.objects.select_related("student")
        }
    sikuli, kahindo, muhindo = (matricule[data[k]] for k in ("b", "kahindo", "muhindo"))

    # Le modèle ne liste que les élèves sans note (classe B), pas ceux de la classe A.
    template = director.get(f"{URL}template/?academic_year={data['year'].pk}")
    assert template.status_code == 200
    sheet = openpyxl.load_workbook(io.BytesIO(template.content)).active
    listed = {cells[0] for cells in sheet.iter_rows(min_row=2, values_only=True)}
    assert listed == {sikuli, kahindo, muhindo}

    rows = [
        [sikuli, "Admis", "", "62,5"],
        [kahindo, "Doublant", "", "44"],
        [muhindo, "passe", "", "130"],
        [matricule[data["amani"]], "Admis", "", "70"],
        ["XX-9999", "Admis", "", ""],
        [sikuli, "Double", "", ""],
        [muhindo, "", "", ""],
    ]
    preview = send(director, data, rows)
    assert preview.status_code == 200
    body = preview.json()
    assert (body["ready_count"], body["empty_count"], body["class_count"]) == (2, 1, 1)
    assert [(line["line"], [i["code"] for i in line["issues"]]) for line in body["errors"]] == [
        (4, ["invalid_percent"]),
        (5, ["has_grades"]),
        (6, ["unknown_student"]),
        (7, ["duplicate"]),
    ]
    # L'aperçu n'écrit rien ; un aperçu périmé n'enregistre rien.
    assert row(director, data, "b")["decision"] == ""
    assert send(director, data, rows, expected=3).json()["code"] == "preview_outdated"

    before = decided_log(school)
    saved = send(director, data, rows, expected=2)
    assert (saved.status_code, saved.json()["changed_count"]) == (201, 2)
    assert director.get(class_b(data)).json()["held_on"] == "2026-06-30"
    assert (row(director, data, "b")["decision"], row(director, data, "b")["percent"]) == (
        "pass",
        "62.5",
    )
    assert (
        row(director, data, "kahindo")["decision"],
        row(director, data, "kahindo")["percent"],
    ) == ("repeat", "44.0")
    # Deux décisions et la date de la classe au journal.
    assert decided_log(school) == before + 3

    # Le même fichier renvoyé : rien n'est réécrit ni journalisé.
    again = send(director, data, rows, expected=2)
    assert (again.status_code, again.json()["changed_count"]) == (201, 0)
    assert decided_log(school) == before + 3

    # Classe proclamée : figée, la reprise est refusée.
    assert decide(director, data, "muhindo", "dropped").status_code == 200
    assert director.post(class_b(data, "proclaim/")).status_code == 200
    closed = send(director, data, rows[:2])
    assert {i["code"] for line in closed.json()["errors"] for i in line["issues"]} == {
        "class_proclaimed"
    }
    assert send(director, data, rows[:2], expected=2).json()["code"] == "nothing_to_record"


def test_only_the_direction_of_studies_and_only_its_school(
    api, school, other_school, physics_teacher, data
):
    teacher = api(physics_teacher)
    assert teacher.get(f"{URL}template/?academic_year={data['year'].pk}").status_code == 403
    assert send(teacher, data, [["X", "Admis", "", ""]]).status_code == 403

    # L'autre école ne voit pas l'année : ni modèle (donc ni noms ni matricules), ni import.
    other = api(
        MembershipFactory(school=other_school, roles=["study_director"]).user, host="beta.localhost"
    )
    assert other.get(f"{URL}template/?academic_year={data['year'].pk}").status_code == 404
    assert send(other, data, [["X", "Admis", "", ""]]).status_code == 404

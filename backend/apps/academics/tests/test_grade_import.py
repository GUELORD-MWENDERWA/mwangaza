"""Import des points depuis Excel (8.2.4) : modèle de la feuille, contrôle ligne par ligne sans
rien écrire, enregistrement par la saisie ; mêmes droits que la feuille ; isolation entre écoles."""

from decimal import Decimal
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook, load_workbook

from apps.academics.models import Grade
from apps.academics.tests.test_grades import setup, sheet_url
from apps.core.tenancy import use_school
from apps.students.models import Enrollment
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


def import_url(course, term) -> str:
    return sheet_url(course, term) + "import/"


def upload(rows: list[list]) -> SimpleUploadedFile:
    book = Workbook()
    for row in rows:
        book.active.append(row)
    output = BytesIO()
    book.save(output)
    return SimpleUploadedFile("points.xlsx", output.getvalue())


def send(client, course, term, rows):
    url, body = import_url(course, term), {"file": upload(rows)}
    return client.client.post(url, body, HTTP_HOST=client.host)


def matricules(school, data) -> dict:
    with use_school(school):
        found = Enrollment.objects.filter(pk__in=[data["amani"], data["josue"]])
        return {str(e.pk): e.student.matricule for e in found.select_related("student")}


def scores(school) -> dict:
    with use_school(school):
        return {(str(g.enrollment_id), g.evaluation.name): g.score for g in Grade.objects.all()}


def test_the_file_is_checked_line_by_line_and_nothing_is_written_before_saving(api, school, head):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    data = setup(school, head, teacher=teacher)
    physics, p1, amani, josue = data["physics"], data["p1"], data["amani"], data["josue"]
    client = api(teacher)
    sheet = client.put(
        sheet_url(physics, p1),
        {"evaluations": [{"name": "Interro", "max_score": 10}, {"name": "TP", "max_score": 20}]},
    ).json()
    interro = sheet["evaluations"][0]["id"]
    client.put(
        sheet_url(physics, p1),
        {"grades": [{"enrollment_id": amani, "evaluation_id": interro, "score": "6"}]},
    )
    numbers = matricules(school, data)

    # Modèle : titre, puis matricule, nom et une colonne par évaluation, notes déjà saisies.
    response = client.get(import_url(physics, p1))
    assert response.status_code == 200
    rows = list(load_workbook(BytesIO(response.content)).active.values)
    assert rows[1][2:] == ("Interro /10", "TP /20")
    assert (rows[2][0], rows[2][2]) == (numbers[amani], 6)

    # Une note trop haute, un matricule inconnu, un élève deux fois, une note illisible.
    titles = ["MATRICULE", "NOM", "Interro /10", "TP /20"]
    wrong = [
        titles,
        [numbers[amani], "", 12, 15],
        ["XX-404", "Inconnu", 7, 14],
        ["", "KAMBALE X", "7,5", "abc"],
        [numbers[amani], "", 8, ""],
    ]
    result = send(client, physics, p1, wrong).json()
    issues = {line["number"]: [i["code"] for i in line["issues"]] for line in result["lines"]}
    assert issues == {
        2: ["above_maximum"],
        3: ["unknown_student"],
        4: ["invalid_score"],
        5: ["duplicate_student"],
    }
    assert result["error_count"] == 4 and result["grades"] == []
    assert scores(school) == {(amani, "Interro"): Decimal("6.0")}

    # Corrigé : la note inchangée n'est pas renvoyée ; l'élève sans matricule est reconnu par
    # son nom ; la saisie enregistre ensuite d'un seul envoi.
    right = [titles, [numbers[amani], "", 6, 15], ["", "KAMBALE X", "7,5", ""]]
    result = send(client, physics, p1, right).json()
    assert (result["error_count"], result["unchanged_count"], len(result["grades"])) == (0, 1, 2)
    body = {"evaluations": result["evaluations"], "grades": result["grades"]}
    assert client.put(sheet_url(physics, p1), body).status_code == 200
    assert scores(school) == {
        (amani, "Interro"): Decimal("6.0"),
        (amani, "TP"): Decimal("15.0"),
        (josue, "Interro"): Decimal("7.5"),
    }


def test_same_rights_as_the_sheet_and_a_totals_sheet_gets_its_total_column(api, school, head):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    data = setup(school, head, teacher=teacher)
    physics, workshop, p1 = data["physics"], data["workshop"], data["p1"]
    # Un enseignant qui ne donne pas le cours : refusé, comme pour la feuille.
    other = api(MembershipFactory(school=school, roles=["teacher"]).user)
    assert other.get(import_url(physics, p1)).status_code == 403
    assert send(other, physics, p1, [["MATRICULE", "Total /20"], ["X", 1]]).status_code == 403

    # `grades.enter_any` sur un cours sans évaluation : une colonne « total » créée à l'envoi.
    client = api(MembershipFactory(school=school, roles=["secretary"]).user)
    rows = list(load_workbook(BytesIO(client.get(import_url(workshop, p1)).content)).active.values)
    assert rows[1][2:] == ("Total /100",)
    numbers = matricules(school, data)
    result = send(client, workshop, p1, [rows[1], [numbers[data["amani"]], "", 64]]).json()
    assert [c["new"] for c in result["columns"]] == [True]
    assert result["evaluations"][0]["id"] == result["grades"][0]["evaluation_id"]
    body = {"evaluations": result["evaluations"], "grades": result["grades"]}
    assert client.put(sheet_url(workshop, p1), body).status_code == 200


def test_another_school_can_neither_download_nor_check_the_sheet(
    api, school, other_school, head, other_head
):
    data = setup(school, head)
    setup(other_school, other_head)
    outsider = MembershipFactory(school=other_school, roles=["secretary"]).user
    beta = api(outsider, host="beta.localhost")
    url = import_url(data["workshop"], data["p1"])
    assert beta.get(url).status_code == 404
    assert send(beta, data["workshop"], data["p1"], [["MATRICULE"], ["X"]]).status_code == 404

"""Import d'une liste d'élèves (D1) : vérification ligne par ligne, import sans doublon avec
fratries et matricules, isolation entre écoles, droit `students.import`, fichier réaliste."""

import io
from datetime import date, datetime

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.models import StudentCharge
from apps.students import imports
from apps.students.demo import import_rows, import_workbook
from apps.students.models import Enrollment, Family, Student, StudentImport
from apps.students.tests.conftest import new_student

IMPORTS = "/api/student-imports/"
HEADERS = [
    "NOM", "POSTNOM", "PRENOM", "SEXE", "DATE NAISS.", "CLASSE", "NOM DU PARENT", "TEL",
    "MATRICULE",
]  # fmt: skip
# Lignes 3 à 11 du fichier (titre en ligne 1, colonnes en ligne 2).
ROWS = [
    ["KAMBALE", "MUHINDO", "Josué", "M", datetime(2010, 5, 3), "3E ELEC A", "Kambale Paluku",
     "0971234567", ""],
    ["KAMBALE", "KAVIRA", "Neema", "F", "21/11/2011", "3ème Électricité A", "KAMBALE PALUKU",
     971234567, ""],
    ["PALUKU", "SIVIHWA", "Daniel", "M", "31/02/2008", "3E ELEC A", "", "", ""],
    ["KAVIRA", "NZIAVAKE", "Esther", "F", "05/06/2011", "4E MEC AUTO B", "", "", ""],
    ["KAMBALE", "MUHINDO", "JOSUÉ", "M", "03/05/2010", "3E ELEC A", "", "", ""],
    ["KASEREKA", "", "Jean", "M", "01/01/2010", "3E ELEC A", "", "", ""],
    ["MUMBERE", "", "Élie", "X", "09/07/2011", "3E ELEC A", "Mumbere Kule", "12345", ""],
    ["BAHATI", "AMANI", "Christian", "M", "", "3E ELEC A", "Bahati Jean", "+243 99 123 45 67",
     "ANCIEN-001"],
    ["SIKULI", "", "Grâce", "F", "17/01/2010", "3E ELEC A", "", "", "ANCIEN-001"],
]  # fmt: skip


def xlsx(rows=ROWS, headers=HEADERS, name="liste.xlsx") -> SimpleUploadedFile:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["ÉCOLE ALPHA — LISTE DES ÉLÈVES (fictive)"])
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    return SimpleUploadedFile(name, output.getvalue())


def upload(client, file, **data):
    return client.client.post(IMPORTS, {"file": file, **data}, HTTP_HOST=client.host)


def statuses(client, imp_id) -> dict:
    lines = client.get(f"{IMPORTS}{imp_id}/lines/").json()["results"]
    return {
        line["line"]: (line["status"], sorted(issue["code"] for issue in line["issues"]))
        for line in lines
    }


@pytest.fixture
def known(school, head, alpha):
    """Élève déjà dans l'école : la ligne 8 le répète."""
    return new_student(school, head, birth_date=date(2010, 1, 1))


def test_each_row_is_checked_then_imported_once_with_siblings_and_matricules(
    api, school, head, alpha, known, django_capture_on_commit_callbacks
):
    client = api(head)
    response = upload(client, xlsx())
    assert response.status_code == 201, response.json()
    imp = response.json()
    assert imp["counts"] == {"rows": 9, "ready": 2, "warning": 2, "error": 5}
    assert imp["missing_fields"] == []
    assert imp["mapping"]["birth_date"] == 4 and imp["mapping"]["guardian_phone"] == 7
    assert statuses(client, imp["id"]) == {
        3: ("ready", []),
        4: ("ready", ["same_family"]),
        5: ("error", ["invalid_date"]),
        6: ("error", ["unknown_class"]),
        7: ("warning", ["duplicate_in_file"]),
        8: ("error", ["already_in_school"]),
        9: ("error", ["invalid_phone", "invalid_sex"]),
        10: ("warning", ["missing_birth_date"]),
        11: ("error", ["matricule_repeated"]),
    }

    # La classe inconnue est associée à la main.
    group = alpha["group"]
    response = client.patch(
        f"{IMPORTS}{imp['id']}/", {"class_mapping": {"4E MEC AUTO B": str(group.pk)}}
    )
    assert response.json()["counts"]["error"] == 4
    assert response.json()["importable_count"] == 5

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(f"{IMPORTS}{imp['id']}/confirm/")
    assert response.status_code == 202 and response.json()["status"] == "importing"
    done = client.get(f"{IMPORTS}{imp['id']}/").json()
    assert done["status"] == "done" and done["created_count"] == 5

    with use_school(school):
        created = Student.objects.exclude(pk=known.pk).select_related("family")
        assert {student.last_name for student in created} == {"KAMBALE", "KAVIRA", "BAHATI"}
        siblings = {student.first_name: student.family for student in created}
        assert siblings["Josué"] == siblings["Neema"] != siblings["Christian"]
        guardian = siblings["Josué"].guardians.get()
        assert (guardian.full_name, guardian.phone, guardian.is_primary) == (
            "Kambale Paluku",
            "+243971234567",
            True,
        )
        numbers = [student.matricule for student in created]
        assert "ANCIEN-001" in numbers and len(set(numbers)) == 5 and all(numbers)
        assert Enrollment.objects.filter(class_group=group).count() == 5
        logs = AuditLog.objects.filter(action=Action.STUDENTS_STUDENT_IMPORTED)
        assert {log.entity_id for log in logs} == {student.pk for student in created}
        assert {log.actor_id for log in logs} == {head.pk}
        done = StudentImport.objects.get(pk=imp["id"])
        # Le fichier est effacé ; restent les lignes non importées, pour le rapport.
        assert done.rows == []
        assert [line["line"] for line in done.report["lines"]] == [5, 8, 9, 11]

    # Le même fichier envoyé de nouveau n'importe personne une seconde fois.
    again = upload(client, xlsx()).json()
    assert again["importable_count"] == 0
    response = client.post(f"{IMPORTS}{again['id']}/confirm/")
    assert response.status_code == 409 and response.json()["code"] == "nothing_to_import"
    response = client.post(f"{IMPORTS}{imp['id']}/confirm/")
    assert response.json()["code"] == "import_closed"


def test_import_of_one_school_is_invisible_to_another(api, school, head, alpha, other_head, beta):
    imp = upload(api(head), xlsx()).json()
    other = api(other_head, host="beta.localhost")
    path = f"{IMPORTS}{imp['id']}/"
    assert other.get(path).status_code == 404
    assert other.get(f"{path}lines/").status_code == 404
    assert other.get(f"{path}report/").status_code == 404
    assert other.patch(path, {"class_mapping": {}}).status_code == 404
    assert other.post(f"{path}confirm/").status_code == 404
    # Ni une classe ni une année d'une autre école.
    response = api(head).patch(path, {"class_mapping": {"4E MEC AUTO B": str(beta["group"].pk)}})
    assert response.status_code == 400 and "class_mapping" in response.json()["fields"]
    response = upload(api(head), xlsx(), academic_year=str(beta["year"].pk))
    assert response.status_code == 400 and "academic_year" in response.json()["fields"]
    with use_school(school):
        assert StudentImport.objects.get().class_mapping == {}


def test_import_needs_its_permission(api, alpha, cashier):
    client = api(cashier)
    assert upload(client, xlsx()).status_code == 403
    assert client.get(f"{IMPORTS}template/").status_code == 403


def test_template_and_report_are_read_back_by_the_import(api, head, alpha):
    client = api(head)
    template = client.get(f"{IMPORTS}template/")
    headers = [
        cell.value for cell in openpyxl.load_workbook(io.BytesIO(template.content)).active[1]
    ]
    assert None not in imports.guess_mapping(headers).values()

    imp = upload(client, xlsx()).json()
    report = openpyxl.load_workbook(io.BytesIO(client.get(f"{IMPORTS}{imp['id']}/report/").content))
    rows = list(report.active.iter_rows(values_only=True))
    assert [row[0] for row in rows[1:]] == [5, 6, 7, 9, 10, 11]
    assert rows[1][2:5] == ("PALUKU", "SIVIHWA", "Daniel")
    # Corrigé, le rapport se réimporte tel quel : mêmes colonnes reconnues.
    assert imports.guess_mapping(list(rows[0]))["class_name"] == imp["mapping"]["class_name"] + 2


def test_csv_from_excel_is_read_and_old_excel_refused(api, head, alpha):
    client = api(head)
    content = (
        "NOM;POSTNOM;PRENOM;SEXE;DATE NAISS.;CLASSE\nKAMBALE;MUHINDO;Josué;M;03/05/2010;3E ELEC A\n"
    )
    response = upload(client, SimpleUploadedFile("liste.csv", content.encode("cp1252")))
    assert response.json()["counts"]["ready"] == 1
    response = upload(client, SimpleUploadedFile("liste.xls", b"\xd0\xcf\x11\xe0"))
    assert response.status_code == 400 and response.json()["code"] == "old_excel"


def test_realistic_file_of_800_students_is_imported_in_a_few_queries(
    school, head, alpha, django_assert_max_num_queries
):
    content = import_workbook(import_rows(800, ["3E ELEC A", "3E ELECTRICITE A"]))
    with use_school(school):
        fee_type = finance.create_fee_type(actor=head, name="Minerval", category="tuition")
        finance.create_fee_rule(
            actor=head,
            academic_year=alpha["year"],
            fee_type=fee_type,
            currency="USD",
            total_amount_minor=24000,
            schedule_kind="installments",
            installments=[
                finance.Installment("1re tranche", 12000, date(2026, 10, 15)),
                finance.Installment("2e tranche", 12000, date(2027, 1, 15)),
            ],
        )
        imp = imports.create_import(
            actor=head, file=SimpleUploadedFile("eleves.xlsx", content), academic_year=alpha["year"]
        )
        counts = imp.report["counts"]
        assert counts["rows"] == 800 and counts["error"] >= 3
        StudentImport.objects.filter(pk=imp.pk).update(status=StudentImport.Status.IMPORTING)
        with django_assert_max_num_queries(40):
            imports.run(imp, actor=head)
        imp.refresh_from_db()
        assert imp.created_count == counts["ready"] + counts["warning"] == Student.objects.count()
        assert Family.objects.count() < imp.created_count  # fratries regroupées
        assert Student.objects.values("matricule").distinct().count() == imp.created_count
        assert StudentCharge.objects.count() == 2 * imp.created_count

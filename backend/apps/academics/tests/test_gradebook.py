"""Fiches de cotes (8.3.6) : statistiques d'un cours, tableau de la classe, droits, isolation entre
écoles, PDF noté dans le journal."""

from decimal import Decimal

import pytest

from apps.academics.tests.test_grades import setup
from apps.academics.tests.test_report_cards import put
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import ClassGroup
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


def url(data, key="a") -> str:
    return f"/api/class-groups/{data[key].pk}/grade-sheet/"


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


@pytest.fixture
def director(school):
    return MembershipFactory(school=school, roles=["study_director"]).user


@pytest.fixture
def sheets(school, head, teacher):
    data = setup(school, head, teacher=teacher)
    amani, josue = data["amani"], data["josue"]
    put(school, data["physics"], data["p1"], "Interro", 20, {amani: "18", josue: "8"})
    put(school, data["workshop"], data["p1"], "TP", 100, {amani: "80", josue: "80"})
    return data


def test_the_course_sheet_gives_average_highest_lowest_and_those_under_half(
    api, school, director, sheets
):
    page = api(director).get(
        url(sheets),
        kind="course",
        course=sheets["physics"].pk,
        output="html",
        columns=["matricule"],
    )
    assert page.status_code == 200
    context = page.context
    # Physique : deux semestres de P1, P2 et examen (le double).
    assert [c["maximum"] for c in context["shown"]] == [20, 20, 40, 20, 20, 40]
    first, second = context["statistics"][:2]
    assert (first["average"], first["high"], first["low"], first["below"]) == (
        Decimal("13.0"),
        Decimal("18"),
        Decimal("8"),
        1,
    )
    # Personne n'a de note en 2e période : rien à calculer, pas de zéro inventé.
    assert second == {"average": None, "high": None, "low": None, "below": None}
    assert [row["scores"][0] for row in context["rows"]] == [Decimal("18"), Decimal("8")]
    # Aucune feuille validée : le document le dit.
    assert context["provisional"] is True
    blank = api(director).get(url(sheets), kind="blank", course=sheets["physics"].pk, output="html")
    assert blank.context["statistics"] == [] and len(blank.context["blank_columns"]) == 8
    assert all(row["scores"] == [] for row in blank.context["rows"])


def test_the_class_table_gives_total_percent_and_place_and_prints_in_landscape(
    api, school, director, sheets
):
    column = str(sheets["p1"].pk)
    page = api(director).get(url(sheets), kind="class", column=column, output="html")
    context = page.context
    bahati, kambale = context["rows"]
    # 1re période : (18 + 80) et (8 + 80) sur 120.
    assert (bahati["total"].score, bahati["total"].place) == (Decimal("98"), 1)
    assert (kambale["total"].score, kambale["total"].place) == (Decimal("88"), 2)
    assert [item["maximum"] for item in context["shown"]] == [100, 20]
    assert "A4 landscape" in page.content.decode()
    portrait = api(director).get(
        url(sheets), kind="class", column=column, output="html", orientation="portrait"
    )
    assert "A4 portrait" in portrait.content.decode()
    # Une colonne inconnue est refusée ; l'année complète est la colonne par défaut.
    unknown = api(director).get(url(sheets), kind="class", column="x", output="html")
    assert unknown.status_code == 400
    assert api(director).get(url(sheets), kind="class", output="html").status_code == 200


def test_who_may_print_which_sheet(api, school, other_school, director, cashier, sheets, teacher):
    physics, workshop = sheets["physics"].pk, sheets["workshop"].pk
    mine = api(teacher)
    assert mine.get(url(sheets), kind="course", course=physics, output="html").status_code == 200
    refused = mine.get(url(sheets), kind="course", course=workshop, output="html")
    assert refused.status_code == 403 and refused.json()["code"] == "not_your_course"
    # Le tableau de la classe n'est pas à l'enseignant d'un seul cours.
    assert mine.get(url(sheets), kind="class", output="html").status_code == 403
    with use_school(school):
        ClassGroup.objects.filter(pk=sheets["a"].pk).update(homeroom_teacher=teacher)
    assert mine.get(url(sheets), kind="class", output="html").status_code == 200
    assert mine.get("/api/grading/").json()["classes"][0]["is_homeroom"] is True
    assert api(cashier).get(url(sheets), kind="class", output="html").status_code == 403
    # Le cours d'une autre classe : introuvable sur cette classe.
    other_course = sheets["b_physics"].pk
    assert api(director).get(url(sheets), kind="course", course=other_course).status_code == 404
    # Une classe d'une autre école est introuvable.
    foreign = MembershipFactory(school=other_school, roles=["study_director"]).user
    client = api(foreign, host="beta.localhost")
    assert client.get(url(sheets), kind="class", output="pdf").status_code == 404


def test_each_pdf_is_in_the_audit_log_and_a_preview_is_not(api, school, director, sheets):
    client = api(director)
    client.get(url(sheets), kind="class", output="html")
    with use_school(school):
        assert not AuditLog.objects.filter(action=Action.GRADES_SHEET_PRINTED).exists()
    pdf = client.get(url(sheets), kind="course", course=sheets["physics"].pk, output="pdf")
    assert pdf["Content-Type"] == "application/pdf"
    with use_school(school):
        [log] = AuditLog.objects.filter(action=Action.GRADES_SHEET_PRINTED)
        assert log.actor == director

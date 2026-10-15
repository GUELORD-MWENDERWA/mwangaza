"""Bulletin imprimé (8.3.2) : droits, isolation entre écoles, PDF noté, contenu du tableau et
vérification du QR code (initiales, école de l'adresse seulement)."""

from datetime import date
from decimal import Decimal

import pytest

from apps.academics.models import GradeSheet
from apps.academics.report_card_documents import verification_path
from apps.academics.report_cards import class_report
from apps.academics.tests.test_grades import setup
from apps.academics.tests.test_report_cards import put
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import Level
from apps.students.models import Enrollment
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


def url(data, key="a") -> str:
    return f"/api/class-groups/{data[key].pk}/report-card/"


@pytest.fixture
def director(school):
    return MembershipFactory(school=school, roles=["study_director"]).user


@pytest.fixture
def card(school, head):
    data = setup(school, head)
    amani, josue = data["amani"], data["josue"]
    put(school, data["physics"], data["p1"], "Interro", 20, {amani: "18", josue: "8"})
    put(school, data["workshop"], data["p1"], "TP", 100, {amani: "80", josue: "80"})
    return data


def test_the_card_shows_maxima_scores_low_marks_and_the_place(api, director, card):
    page = api(director).get(url(card), enrollment=card["josue"], output="html")
    context = page.context
    assert context["totals"]["place"][0] == "2e/2"
    assert context["totals"]["percent"][0] == Decimal("73.3")
    lines = context["lines"]
    # Cours par maxima croissants : la physique (20) puis l'atelier (100, sans examen), chacun
    # sous sa ligne de maxima ; 8 sur 20 est sous la moitié.
    assert [line.get("name") or line["maxima"][0] for line in lines] == [
        20,
        "Physique",
        100,
        "Atelier",
    ]
    physics, atelier = lines[1]["cells"], lines[3]["cells"]
    assert (physics[0]["score"], physics[0]["low"]) == (Decimal("8"), True)
    exam = [c["kind"] for c in context["columns"]].index("exam")
    assert (atelier[0]["low"], atelier[exam]["maximum"], physics[exam]["maximum"]) == (False, 0, 40)


def test_the_form_follows_the_official_one_and_the_last_year_has_the_state_exam(
    api, director, card, school
):
    school.province, school.city, school.epst_code = "Nord-Kivu", "Goma", "2610021"
    school.save()
    with use_school(school):
        person = Enrollment.objects.get(pk=card["josue"]).student
        person.national_id, person.permanent_number = "61022-6100210011533", "2-610021001115"
        person.save()
    url_html = (url(card), {"enrollment": card["josue"], "output": "html"})

    context = api(director).get(url_html[0], **url_html[1]).context
    # Une case par caractère, aucune case vide derrière.
    assert "".join(context["id_boxes"]) == "61022-6100210011533"
    assert "".join(context["perm_boxes"]) == "2-610021001115"
    assert "".join(context["code_boxes"]) == "2-610021"
    assert not context["state_exam"]
    # Deux semestres de deux périodes : les largeurs du scan, 199,5 mm en tout.
    assert round(sum(context["widths"]) + 40.7 + 5.6 + 30.6, 1) == 199.6
    # Aucune ligne vide : deux cours (4 lignes avec les maxima) + 7 lignes de totaux, étirées pour
    # remplir la hauteur du formulaire (au plus 9 mm chacune).
    assert len(context["lines"]) == 4
    assert context["row_height"] == 9.0

    with use_school(school):
        Level.objects.update(has_state_exam=True)
    context = api(director).get(url_html[0], **url_html[1]).context
    # Examen d'État : la colonne de droite a une entrée par ligne, la signature du responsable
    # (dernière ligne) n'a rien à sa droite.
    assert context["state_exam"] and len(context["footer_state"]) == 7
    assert context["footer_state"][-1] == {}


def test_the_state_exam_column_spreads_over_any_number_of_rows():
    from apps.academics.report_card_documents import _state_column

    for rows in (24, 30, 40):
        column = _state_column(rows)
        assert len(column) == rows and column[-1] == {}
        texts = [item for item in column if item]
        assert len(texts) == 16  # les cinq parties du formulaire, toutes présentes
        assert column[0].get("cols") and column[rows - 2]  # du haut au bas, sans trou à la fin


def validate_all(school, data):
    with use_school(school):
        for course in ("physics", "workshop"):
            GradeSheet.objects.update_or_create(
                course=data[course],
                term=data["p1"],
                defaults={"status": GradeSheet.Status.VALIDATED},
            )


def test_pdf_waits_for_every_course_to_be_validated_but_the_preview_does_not(
    api, school, director, card
):
    client = api(director)
    pdf = client.get(url(card), enrollment=card["amani"], output="pdf")
    assert (pdf.status_code, pdf.json()["code"], pdf.json()["missing_count"]) == (
        409,
        "report_incomplete",
        2,
    )
    assert {item["course"] for item in pdf.json()["missing"]} == {"Physique", "Atelier"}
    preview = client.get(url(card), enrollment=card["amani"], output="html")
    assert preview.status_code == 200 and preview.context["missing_count"] == 2
    validate_all(school, card)
    assert client.get(url(card), enrollment=card["amani"], output="pdf").status_code == 200


def test_pdf_is_audited_but_not_the_preview_and_needs_a_grades_right(
    api, school, director, cashier, card
):
    validate_all(school, card)
    client = api(director)
    assert client.get(url(card), enrollment=card["amani"], output="html").status_code == 200
    pdf = client.get(url(card), enrollment=card["amani"], output="pdf")
    assert pdf["Content-Type"] == "application/pdf"
    with use_school(school):
        [log] = AuditLog.objects.filter(action=Action.GRADES_REPORT_CARD_PRINTED)
        assert log.actor == director
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    for user in (cashier, teacher):
        assert api(user).get(url(card), enrollment=card["amani"], output="html").status_code == 403


def test_a_school_neither_prints_nor_verifies_the_card_of_another(
    api, school, other_school, director, card
):
    foreign = MembershipFactory(school=other_school, roles=["study_director"]).user
    # Une classe de l'école alpha, vue depuis beta : introuvable.
    assert (
        api(foreign, host="beta.localhost")
        .get(url(card), enrollment=card["amani"], output="html")
        .status_code
        == 404
    )
    # Un élève d'une autre classe de la même école : introuvable aussi.
    assert api(director).get(url(card), enrollment=card["b"], output="html").status_code == 404

    with use_school(school):
        report = class_report(card["a"])
        student = next(s for s in report.students if str(s.enrollment.pk) == card["amani"])
        keys = [c.key for c in report.columns]
        path = verification_path(student, keys, len(report.students), date(2026, 10, 16))
    page = api().get(path)
    body = page.content.decode()
    assert page.status_code == 200
    # Initiales seulement, et le résultat imprimé (Période 1 : 98 sur 120, première place).
    assert "B. X." in body and "Bahati" not in body
    assert "1" in body
    assert api(host="beta.localhost").get(path).status_code == 404
    assert api().get(f"{path[:-3]}abc").status_code == 404

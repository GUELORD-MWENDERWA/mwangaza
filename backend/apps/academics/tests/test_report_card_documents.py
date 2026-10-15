"""Bulletin imprimé (8.3.2) : droits, isolation entre écoles, PDF noté, contenu du tableau et
vérification du QR code (initiales, école de l'adresse seulement)."""

from datetime import date
from decimal import Decimal

import pytest

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
    # Cours par ordre alphabétique : l'atelier (sans examen) puis la physique, chacun sous sa
    # ligne de maxima ; 8 sur 20 est sous la moitié.
    assert [line.get("name") or line["maxima"][0] for line in lines] == [
        100,
        "Atelier",
        20,
        "Physique",
    ]
    atelier, physics = lines[1]["cells"], lines[3]["cells"]
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
    assert "".join(context["id_boxes"]).strip() == "61022-6100210011533"
    assert "".join(context["perm_boxes"]).strip() == "2-610021001115"
    assert "".join(context["code_boxes"]).strip() == "2-610021"
    assert not context["state_exam"]
    # Deux semestres de deux périodes : les largeurs du scan, 199,5 mm en tout.
    assert round(sum(context["widths"]) + 40.7 + 33.2, 1) == 199.5
    # Lignes vides jusqu'à la hauteur du formulaire (35 lignes en tout) ; les autres années
    # gardent les cases du repêchage, noires sur les lignes de maxima.
    assert len(context["lines"]) + len(context["blank_lines"]) + 7 == 35
    assert context["lines"][0]["side"] == {"resit": True}

    with use_school(school):
        Level.objects.update(has_state_exam=True)
    context = api(director).get(url_html[0], **url_html[1]).context
    assert context["state_exam"] and context["lines"][0]["side"]["cols"]
    sides = [line["side"] for line in context["lines"]]
    sides += [blank["side"] for blank in context["blank_lines"]] + context["footer_side"]
    assert any(item.get("boxes") for item in sides)


def test_pdf_is_audited_but_not_the_preview_and_needs_a_grades_right(
    api, school, director, cashier, card
):
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

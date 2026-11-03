# ruff: noqa: F811, F401
"""Notes et bulletin d'un enfant sur le Portail (8.8) : totaux des feuilles validées seulement,
bulletin remis après la proclamation et sauf frais échus sans dérogation, jamais les notes d'une
période non proclamée, isolation entre familles et entre écoles, limite d'essais."""

import pytest

from apps.academics import report_cards, waivers
from apps.academics.models import Deliberation, GradeSheet
from apps.academics.tests.test_resits import data, physics_teacher
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.portal import results
from apps.portal.tests.test_access import activate, new_family, portal
from apps.students.models import Enrollment

pytestmark = pytest.mark.django_db


def results_url(data, key="amani") -> str:
    return f"/api/portal/children/{student_of(data, key)}/results/"


def card_url(data, key="amani") -> str:
    return f"/api/portal/children/{student_of(data, key)}/report-card/"


def student_of(data, key):
    with use_school(data["a"].school):
        return Enrollment.objects.get(pk=data[key]).student_id


def parent_of(data, key="amani", phone="0971234567"):
    """Compte du parent de l'élève, famille activée."""
    school = data["a"].school
    with use_school(school):
        family = Enrollment.objects.get(pk=data[key]).student.family
    client = portal()
    assert activate(client, family.code, phone=phone).status_code == 200
    return client


@pytest.fixture
def released(school, data):
    """Physique validée en P1 (l'atelier non) et résultats de P1 proclamés."""
    with use_school(school):
        GradeSheet.objects.create(
            course=data["physics"], term=data["p1"], status=GradeSheet.Status.VALIDATED
        )
        Deliberation.objects.create(
            class_group=data["a"],
            term=data["p1"],
            status=Deliberation.Status.PROCLAIMED,
            version=1,
        )
    return data


def test_a_parent_sees_validated_totals_and_the_report_card_of_a_proclaimed_period(
    school, released, monkeypatch, django_assert_max_num_queries
):
    client = parent_of(released)

    # Budget de requêtes (PERF.6) : un appel par enfant, quel que soit le nombre de cours.
    with django_assert_max_num_queries(25):
        body = client.get(results_url(released)).json()
    # 70 % de 20 en Physique ; l'atelier n'est pas validé : rien.
    assert [(t["released"], t["courses"]) for t in body["terms"]] == [
        (True, [{"course": "Physique", "score": "14.0", "maximum": 20}])
    ]
    assert (body["report_available"], body["withheld"]) == (True, False)
    pdf = client.get(card_url(released))
    assert (pdf.status_code, pdf["Content-Type"]) == (200, "application/pdf")
    # Journal des consultations (S.10) : une ligne par lecture réussie du PDF.
    with use_school(released["a"].school):
        assert AuditLog.objects.filter(action="portal.report_viewed").count() == 1

    # Frais échus sans dérogation : le PDF est refusé, les notes restent visibles.
    monkeypatch.setattr(waivers, "withheld_ids", lambda rows: {e.pk for e in rows})
    body = client.get(results_url(released)).json()
    assert (body["report_available"], body["withheld"], len(body["terms"])) == (False, True, 1)
    refused = client.get(card_url(released))
    assert (refused.status_code, refused.json()["code"]) == (403, "report_withheld")


def test_reopened_results_take_the_report_card_back_and_other_periods_stay_hidden(school, released):
    client = parent_of(released)
    group = released["a"]
    with use_school(school):
        assert results.released_terms(group) == {released["p1"].pk}
        # Les notes d'une période non proclamée sont vides dans le bulletin des parents.
        report = report_cards.class_report(group, results.released_terms(group))
        cells = report.students[0].cells[released["physics"].pk]
        assert cells[str(released["p1"].pk)].score is not None
        assert cells[str(released["exam"].pk)].score is None
        Deliberation.objects.update(status=Deliberation.Status.DRAFT)

    assert client.get(card_url(released)).json()["code"] == "report_not_ready"
    assert client.get(results_url(released)).json()["report_available"] is False


def test_a_report_card_of_another_family_or_school_is_a_404_and_downloads_are_limited(
    school, other_school, head, other_head, released
):
    client = parent_of(released)
    # Autre famille de la même école, famille d'une autre école : même réponse que l'inconnu.
    neighbour = portal()
    activate(neighbour, new_family(school, head, phone="+243970000002").code, phone="0970000002")
    stranger = portal()
    other = new_family(other_school, other_head, phone="+243990000001")
    activate(stranger, other.code, phone="0990000001")
    for who in (neighbour, stranger):
        assert who.get(results_url(released)).status_code == 404
        assert who.get(card_url(released)).status_code == 404
    assert portal().get(results_url(released)).status_code == 403

    # Limite d'essais : 10 par minute et par compte, puis 429.
    with use_school(school):
        Deliberation.objects.update(status=Deliberation.Status.DRAFT)
    codes = [client.get(card_url(released)).status_code for _ in range(11)]
    assert codes == [409] * 10 + [429]

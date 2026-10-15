"""Calcul du bulletin (8.3.1) : totaux du semestre et de l'année, cours sans examen, case
incomplète sans total ni place, places ex æquo, mention, isolation entre écoles."""

from decimal import Decimal

import pytest

from apps.academics.models import Evaluation, Grade
from apps.academics.report_cards import YEAR_KEY, class_report, mention
from apps.academics.tests.test_grades import setup
from apps.core.tenancy import use_school
from apps.schools.models import Term

pytestmark = pytest.mark.django_db


def put(school, course, term, name, maximum, scores: dict) -> None:
    with use_school(school):
        evaluation = Evaluation.objects.create(
            course=course, term=term, name=name, max_score=maximum
        )
        for enrollment, score in scores.items():
            Grade.objects.create(evaluation=evaluation, enrollment_id=enrollment, score=score)


def by_name(report):
    return {s.enrollment.student.last_name: s for s in report.students}


def test_totals_places_and_mentions_follow_the_official_calculation(school, head):
    data = setup(school, head)
    amani, josue = data["amani"], data["josue"]
    physics, workshop, p1 = data["physics"], data["workshop"], data["p1"]
    put(school, physics, p1, "Interro", 20, {amani: "18", josue: "12"})
    put(school, workshop, p1, "TP", 100, {amani: "80", josue: "80"})

    with use_school(school):
        report = class_report(data["a"])
        students = by_name(report)
        bahati, kambale = students["Bahati"], students["Kambale"]
        # Période 1 : 98 / 120 et 92 / 120.
        assert bahati.totals[str(p1.pk)].score == Decimal("98")
        assert bahati.totals[str(p1.pk)].percent == Decimal("81.7")
        assert bahati.totals[str(p1.pk)].mention == "excellent"
        assert (bahati.totals[str(p1.pk)].place, kambale.totals[str(p1.pk)].place) == (1, 2)
        assert kambale.totals[str(p1.pk)].mention == "very_good"
        # Les périodes et examens suivants ne sont pas notés : ni semestre, ni T.G., ni place.
        semester = str(data["semester"].pk)
        for key in (semester, YEAR_KEY):
            assert bahati.totals[key].score is None
            assert bahati.totals[key].place is None
        # Les élèves d'une autre classe ne sont pas dans le bulletin.
        assert set(students) == {"Bahati", "Kambale"}

        # Deuxième période et examens de la physique : l'atelier n'a pas d'examen.
        p2 = Term.objects.filter(parent=data["semester"], kind="period").order_by("order")[1]
        exam = Term.objects.get(parent=data["semester"], kind="exam")
    put(school, physics, p2, "Interro", 20, {amani: "10", josue: "10"})
    put(school, workshop, p2, "TP", 100, {amani: "50", josue: "60"})
    put(school, physics, exam, "Examen", 40, {amani: "30", josue: "30"})
    with use_school(school):
        students = by_name(class_report(data["a"]))
        total = students["Bahati"].totals[semester]
        # Physique 18 + 10 + 30, atelier 80 + 50 : 188 sur 20 + 20 + 40 + 100 + 100.
        assert (total.score, total.maximum) == (Decimal("188"), 280)
        cells = students["Bahati"].cells[physics.pk]
        assert cells[str(exam.pk)].maximum == 40
        assert students["Bahati"].cells[workshop.pk][str(exam.pk)].maximum == 0
        # Le T.G. attend encore le second semestre.
        assert students["Bahati"].totals[YEAR_KEY].score is None


def test_equal_totals_share_the_place_and_a_missing_grade_leaves_no_total(school, head):
    data = setup(school, head)
    amani, josue = data["amani"], data["josue"]
    p1 = data["p1"]
    put(school, data["physics"], p1, "Interro", 20, {amani: "14", josue: "14"})
    put(school, data["workshop"], p1, "TP", 100, {amani: "70"})
    with use_school(school):
        tp = Evaluation.objects.get(course=data["workshop"], term=p1)

    with use_school(school):
        students = by_name(class_report(data["a"]))
    # Josué n'a pas la note de l'atelier : pas de total, donc pas de place.
    assert students["Kambale"].totals[str(p1.pk)].place is None
    assert students["Bahati"].totals[str(p1.pk)].place == 1

    with use_school(school):
        Grade.objects.create(evaluation=tp, enrollment_id=josue, score="70")
        students = by_name(class_report(data["a"]))
    assert [students[n].totals[str(p1.pk)].place for n in ("Bahati", "Kambale")] == [1, 1]


def test_the_report_of_another_school_is_empty(school, other_school, head):
    data = setup(school, head)
    put(school, data["physics"], data["p1"], "Interro", 20, {data["amani"]: "15"})
    with use_school(other_school):
        report = class_report(data["a"])
    assert report.students == []
    assert report.courses == []


def test_mentions_follow_the_percentage():
    assert [mention(Decimal(p)) for p in ("85", "70", "65", "50", "49.9")] == [
        "excellent",
        "very_good",
        "good",
        "satisfactory",
        "insufficient",
    ]
    assert mention(None) is None

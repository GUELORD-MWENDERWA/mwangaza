"""Situations de fin d'année (8.4.4) : comptes et taux aux deux critères, par cours (repêchage
compris), palmarès et ex æquo, lauréat, classes non proclamées hors des totaux, abandon d'après
l'inscription, journal du PDF, droits, isolation."""

from decimal import Decimal

import pytest

from apps.academics import situations
from apps.academics.tests import test_deliberation, test_resits
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.students.models import Enrollment
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

data = test_resits.data
physics_teacher = test_resits.physics_teacher
director = test_deliberation.director
SCHOOL = "/api/situation/"


def class_url(data) -> str:
    return f"/api/class-groups/{data['a'].pk}/situation/"


def page(client, address, criterion, *columns):
    response = client.get(address, criterion=criterion, columns=list(columns), output="html")
    assert response.status_code == 200
    return response.context


@pytest.fixture
def proclaimed(api, school, head, director, physics_teacher, data):
    """Classe A proclamée : Josué réussit son repêchage (55 %) mais double (écart motivé),
    Amani est admise ; un troisième élève a abandonné en cours d'année. Classe B pas proclamée."""
    gone = enrolled(school, head, data["a"], last_name="Paluku", first_name="Y")
    with use_school(school):
        Enrollment.objects.filter(student=gone).update(status=Enrollment.Status.DROPPED)
    api(physics_teacher).put(test_resits.resit_url(data), {"percent": "55"})
    deliberation = test_deliberation.url(data)
    director.put(deliberation, {"held_on": "2027-06-20"})
    test_deliberation.decide(director, data, "amani", "pass")
    test_deliberation.decide(director, data, "josue", "repeat", "Absences répétées")
    assert director.post(f"{deliberation}proclaim/").status_code == 200
    return data


def test_the_class_situation_counts_both_criteria(director, proclaimed):
    rules = page(director, class_url(proclaimed), "rules", "courses", "ranking")
    counts = rules["counts"]
    assert (counts.enrolled, counts.dropped, counts.deliberated) == (3, 1, 2)
    assert (counts.passed, counts.repeat, counts.failed, counts.deviations) == (1, 1, 1, 1)
    assert counts.rate == Decimal("50.0") and not rules["provisional"]
    physics = next(c for c in rules["courses"] if c["name"] == "Physique")
    # Règles : le repêchage réussi compte ; moyenne seule : 48 % reste un échec.
    assert (physics["graded"], physics["passed"]) == (2, 2)
    assert [(r["line"].place, r["line"].decision) for r in rules["ranking"]] == [
        (1, "pass"),
        (2, "repeat"),
    ]

    average = page(director, class_url(proclaimed), "average", "courses")
    counts = average["counts"]
    assert (counts.enrolled, counts.dropped, counts.deliberated, counts.passed) == (3, 1, 2, 2)
    assert counts.rate == Decimal("100.0")
    physics = next(c for c in average["courses"] if c["name"] == "Physique")
    assert (physics["passed"], physics["failed"]) == (1, 1)
    assert average["ranking"] == []


def test_ties_share_a_place_and_the_unranked_come_last():
    def line(name, percent, decision="pass"):
        return situations.Line(name, name, percent, decision, "", "", False)

    lines = [
        line("c", Decimal(70)),
        line("d", None),
        line("a", Decimal(80)),
        line("e", Decimal(90), "dropped"),
        line("b", Decimal(80)),
    ]
    ranked = situations.rank(lines)
    assert [(x.name, x.place) for x in ranked] == [
        ("a", 1),
        ("b", 1),
        ("c", 3),
        ("d", None),
        ("e", None),
    ]
    assert [x.name for x in situations.best(lines)] == ["a", "b"]


def test_a_class_not_proclaimed_is_provisional_and_out_of_the_school_totals(
    school, director, proclaimed, django_assert_max_num_queries
):
    other_class = proclaimed["b_physics"].class_group_id
    assert page(director, f"/api/class-groups/{other_class}/situation/", "rules")["provisional"]
    # Connexion, droits, année, puis classes, instantanés figés et inscriptions : le nombre de
    # lectures ne dépend ni du nombre de classes ni du nombre d'élèves.
    with django_assert_max_num_queries(10):
        school_page = page(director, SCHOOL, "rules", "deviations")
    assert school_page["pending"] == 1
    assert (school_page["total"].enrolled, school_page["total"].passed) == (3, 1)
    [laureate] = school_page["laureates"]
    assert (laureate["line"].enrollment, laureate["group"]) == (
        proclaimed["amani"],
        proclaimed["a"],
    )
    assert [d["line"].reason for d in school_page["deviations"]] == ["Absences répétées"]

    pdf = director.get(SCHOOL, criterion="average")
    assert pdf["Content-Type"] == "application/pdf"
    with use_school(school):
        assert AuditLog.objects.filter(action="grades.situation_printed").count() == 1


def test_only_the_direction_of_studies_prints_and_never_another_school(
    api, other_school, physics_teacher, data
):
    teacher = api(physics_teacher)
    assert teacher.get(class_url(data)).status_code == 403
    assert teacher.get(SCHOOL).status_code == 403
    other = api(
        MembershipFactory(school=other_school, roles=["study_director"]).user, host="beta.localhost"
    )
    assert other.get(class_url(data), output="html").status_code == 404
    elsewhere = page(other, SCHOOL, "rules")
    assert elsewhere["levels"] == [] and elsewhere["total"].enrolled == 0

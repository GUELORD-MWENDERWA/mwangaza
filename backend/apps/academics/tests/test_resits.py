"""Règles de réussite et repêchage (8.4.1) : cours échoués d'après les règles de l'école, issue
proposée, note de repêchage saisie et signée par l'enseignant du cours, journal, isolation."""

from decimal import Decimal

import pytest

from apps.academics.grades import term_maximum
from apps.academics.models import Evaluation, Grade
from apps.academics.tests.test_grades import setup
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import Term
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SETTINGS = "/api/school/settings/"


def fill_year(school, data, course, percents: dict) -> None:
    """Note toutes les périodes et tous les examens du cours : chaque élève à son pourcentage."""
    with use_school(school):
        terms = Term.objects.filter(academic_year=data["year"], kind__in=["period", "exam"])
        for term in terms:
            if term.kind == "exam" and not course.has_exam:
                continue
            maximum = term_maximum(course, term)
            evaluation = Evaluation.objects.create(
                course=course, term=term, name="Total", max_score=maximum
            )
            for enrollment, percent in percents.items():
                Grade.objects.create(
                    evaluation=evaluation,
                    enrollment_id=enrollment,
                    score=Decimal(percent) * maximum / 100,
                )


@pytest.fixture
def physics_teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


@pytest.fixture
def data(school, head, physics_teacher):
    data = setup(school, head, teacher=physics_teacher)
    # Bahati réussit tout ; Kambale a 48 % en Physique (échoué, repêchage ouvert dès 45 %).
    fill_year(school, data, data["physics"], {data["amani"]: 70, data["josue"]: 48})
    fill_year(school, data, data["workshop"], {data["amani"]: 80, data["josue"]: 80})
    return data


def class_url(data) -> str:
    return f"/api/class-groups/{data['a'].pk}/resits/"


def resit_url(data, key="josue", course="physics") -> str:
    return f"/api/resits/enrollments/{data[key]}/courses/{data[course].pk}/"


def student(client, data, key="josue") -> dict:
    rows = client.get(class_url(data)).json()["students"]
    return next(s for s in rows if s["enrollment"] == data[key])


def test_a_failed_course_opens_a_resit_and_the_outcome_follows_the_school_rules(
    api, school, head, data
):
    director = api(MembershipFactory(school=school, roles=["study_director"]).user)
    client = director
    rows = client.get(class_url(data)).json()["students"]
    # Bahati n'a aucun cours échoué : absent du tableau.
    assert [r["enrollment"] for r in rows] == [data["josue"]]
    kambale = rows[0]
    assert (kambale["outcome"], kambale["percent"]) == ("resit", "70.9")
    [course] = kambale["courses"]
    assert (course["course_name"], course["percent"], course["eligible"]) == (
        "Physique",
        "48.0",
        True,
    )
    assert course["resit_percent"] is None

    # Plancher à 49 %: 48 % n'ouvre plus de repêchage, l'échec est proposé tout de suite.
    settings = api(head)
    rules = {"pass_rules": {"resit_floor_percent": 49}}
    assert settings.patch(SETTINGS, rules).status_code == 200
    assert student(client, data)["outcome"] == "failed"
    # Mode « tout cours échoué » : le repêchage s'ouvre quel que soit le pourcentage.
    rules = {"pass_rules": {"resit_mode": "any_failed"}}
    assert settings.patch(SETTINGS, rules).status_code == 200
    assert student(client, data)["outcome"] == "resit"
    # Un plancher au niveau de la note de réussite d'un cours est refusé.
    bad = {"pass_rules": {"resit_floor_percent": 50}}
    assert settings.patch(SETTINGS, bad).status_code == 400
    # Les règles ne se changent qu'avec la permission des paramètres.
    assert (
        api(MembershipFactory(school=school, roles=["secretary"]).user)
        .patch(SETTINGS, rules)
        .status_code
        == 403
    )


def test_the_course_teacher_enters_and_signs_the_resit_grade_and_it_is_logged(
    api, school, head, physics_teacher, data
):
    other = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(other).put(resit_url(data), {"percent": "60"}).status_code == 403
    assert api(other).get(class_url(data)).status_code == 403

    client = api(physics_teacher)
    assert student(client, data)["courses"][0]["can_enter"] is True
    # Pas de repêchage pour un élève qui a réussi le cours, ni pour un cours réussi.
    assert client.put(resit_url(data, "amani"), {"percent": "60"}).status_code == 400
    workshop = resit_url(data, "josue", "workshop")
    assert client.put(workshop, {"percent": "60"}).status_code == 403  # pas son cours
    director = MembershipFactory(school=school, roles=["study_director"]).user
    assert api(director).put(workshop, {"percent": "60"}).json()["code"] == "not_a_resit_course"
    assert client.put(resit_url(data), {"percent": "101"}).status_code == 400

    done = client.put(resit_url(data), {"percent": "30"}).json()
    [course] = done["courses"]
    assert (course["resit_percent"], course["passed"]) == ("30.0", False)
    assert course["signed_by"] == physics_teacher.get_full_name()
    # Un échec au repêchage pour un seul cours : l'élève passe tant que le seuil de 2 n'est pas
    # atteint ; l'école peut le ramener à 1.
    assert done["outcome"] == "passed"
    api(head).patch(SETTINGS, {"pass_rules": {"resit_failures_to_fail": 1}})
    assert student(client, data)["outcome"] == "failed"
    redone = client.put(resit_url(data), {"percent": "55.5"}).json()
    assert (redone["outcome"], redone["courses"][0]["passed"]) == ("passed", True)

    with use_school(school):
        entries = list(AuditLog.objects.filter(action="resit.grade_changed").order_by("created_at"))
    assert [e.after["percent"] for e in entries] == ["30.0", "55.5"]
    assert entries[1].before["percent"] == "30.0"

    removed = client.delete(resit_url(data)).json()
    assert removed["outcome"] == "resit" and removed["courses"][0]["resit_percent"] is None
    with use_school(school):
        assert AuditLog.objects.filter(action="resit.grade_changed").count() == 3


def test_another_school_cannot_read_or_enter_a_resit_grade(api, other_school, data):
    other = api(
        MembershipFactory(school=other_school, roles=["study_director"]).user, host="beta.localhost"
    )
    assert other.get(class_url(data)).status_code == 404
    assert other.put(resit_url(data), {"percent": "60"}).status_code == 404

"""Application (8.5.1c) : cote proposée d'après le pourcentage de la période, corrigée par le
titulaire seulement, avec motif et journal ; elle remplit le bulletin ; isolation entre écoles."""

import pytest

from apps.academics.application import proposal
from apps.academics.tests.test_grades import setup
from apps.academics.tests.test_report_cards import put
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import ClassGroup
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def homeroom(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


@pytest.fixture
def data(school, head, homeroom):
    data = setup(school, head)
    with use_school(school):
        ClassGroup.objects.filter(pk=data["a"].pk).update(homeroom_teacher=homeroom)
    put(
        school,
        data["physics"],
        data["p1"],
        "Interro",
        20,
        {data["amani"]: "18", data["josue"]: "12"},
    )
    put(school, data["workshop"], data["p1"], "TP", 100, {data["amani"]: "80", data["josue"]: "80"})
    return data


def class_url(data) -> str:
    return f"/api/class-groups/{data['a'].pk}/application/"


def grade_url(data, key="amani") -> str:
    return f"/api/application/enrollments/{data[key]}/"


def test_the_cote_follows_the_percentage_of_the_period():
    from decimal import Decimal

    assert [proposal(Decimal(p)) for p in ("85", "80", "75", "60", "55", "20")] == [
        "TB",
        "TB",
        "B",
        "AB",
        "ME",
        "MA",
    ]
    assert proposal(None) == ""


def test_only_the_homeroom_teacher_corrects_with_a_reason_and_it_is_logged(
    api, school, head, homeroom, data
):
    body = {"term": str(data["p1"].pk), "grade": "TB", "reason": "Très appliqué en classe"}
    other = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(other).put(grade_url(data, "josue"), body).status_code == 403
    assert api(other).get(class_url(data)).status_code == 403

    client = api(homeroom)
    table = client.get(class_url(data)).json()
    assert table["may_correct"] is True
    rows = {s["enrollment"]: s["terms"][0] for s in table["students"]}
    assert (rows[data["amani"]]["proposed"], rows[data["josue"]]["proposed"]) == ("TB", "B")
    assert rows[data["josue"]]["percent"] == "76.7"

    assert client.put(grade_url(data, "josue"), {**body, "reason": " "}).status_code == 400
    assert client.put(grade_url(data, "josue"), {**body, "grade": "ZZ"}).status_code == 400
    exam = {**body, "term": str(data["exam"].pk)}
    assert client.put(grade_url(data, "josue"), exam).json()["code"] == "bad_term"

    changed = client.put(grade_url(data, "josue"), body).json()
    first = changed["terms"][0]
    assert (first["proposed"], first["grade"]) == ("B", "TB")
    assert first["override_reason"] == "Très appliqué en classe"
    with use_school(school):
        [entry] = AuditLog.objects.filter(action="application.grade_overridden")
    assert (entry.before["grade"], entry.after["grade"]) == ("B", "TB")

    cleared = client.delete(f"{grade_url(data, 'josue')}?term={data['p1'].pk}").json()
    assert cleared["terms"][0]["grade"] == "B"
    with use_school(school):
        assert AuditLog.objects.filter(action="application.grade_overridden").count() == 2

    # Le directeur des études (qui entre les notes de toutes les classes) peut aussi corriger.
    director = MembershipFactory(school=school, roles=["study_director"]).user
    assert api(director).put(grade_url(data, "josue"), body).status_code == 200


def periods(page) -> list[str]:
    return [c["grade"] for c in page.context["application"] if c["kind"] == "period"]


def test_the_report_card_shows_the_retained_application_grade(api, school, homeroom, data):
    api(homeroom).put(
        grade_url(data, "josue"),
        {"term": str(data["p1"].pk), "grade": "TB", "reason": "Conseil de classe"},
    )
    director = MembershipFactory(school=school, roles=["study_director"]).user
    url = f"/api/class-groups/{data['a'].pk}/report-card/"
    page = api(director).get(url, enrollment=data["amani"], output="html")
    josue = api(director).get(url, enrollment=data["josue"], output="html")
    assert periods(page)[0] == "TB" and periods(josue)[0] == "TB"
    assert all(c["grade"] == "" for c in page.context["application"] if c["kind"] != "period")


def test_another_school_cannot_read_or_correct_an_application_grade(api, other_school, data):
    other_teacher = MembershipFactory(school=other_school, roles=["study_director"]).user
    other = api(other_teacher, host="beta.localhost")
    body = {"term": str(data["p1"].pk), "grade": "B", "reason": "x"}
    assert other.get(class_url(data)).status_code == 404
    assert other.put(grade_url(data), body).status_code == 404

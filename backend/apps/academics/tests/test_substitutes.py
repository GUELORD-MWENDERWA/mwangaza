"""Remplaçant d'un cours (8.2.5) : désigné et retiré par le directeur des études seul ; un total
par élève, jamais le carnet de l'enseignant, et une feuille commencée par l'enseignant seulement
après son envoi (en ligne et hors ligne) ; motif pour toute correction par un autre, journal,
enseignant prévenu ; cours commun remplacé en entier ; isolation entre écoles."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.academics.models import CourseGroup, CourseSubstitute
from apps.academics.tests.test_grade_control import action_url, fill, notified
from apps.academics.tests.test_grades import GRADING, setup, sheet_url
from apps.audit.models import AuditLog
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.sync.tests.test_devices import remember
from apps.sync.tests.test_offline_grades import PUSH, grades_op
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SUBSTITUTES = "/api/course-substitutes/"


@pytest.fixture
def people(school):
    def member(role):
        return MembershipFactory(school=school, roles=[role]).user

    return {
        "teacher": member("teacher"),
        "substitute": member("teacher"),
        "director": member("study_director"),
    }


def designate(client, course, substitute, **extra):
    body = {"course": str(course.pk), "substitute_id": str(substitute.pk), "reason": "Congé"}
    return client.post(SUBSTITUTES, {**body, **extra})


def field_error(response, field: str) -> str:
    return response.json()["fields"][field][0]["code"]


def replaced(client) -> dict:
    """Cours de la liste des notes que le compte remplace, et son accès."""
    classes = client.get(GRADING).json()["classes"]
    return {c["id"]: c["access"] for k in classes for c in k["courses"] if c["replacing"]}


def log(school, action) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action=action).order_by("created_at"))


def test_the_director_of_studies_alone_designates_and_removes_a_substitute(
    api, school, head, people
):
    data = setup(school, head, teacher=people["teacher"])
    physics, sub = data["physics"], people["substitute"]
    director = api(people["director"])
    # Ni l'enseignant ni le préfet (sans `grades.validate`).
    assert designate(api(people["teacher"]), physics, sub).status_code == 403
    assert api(head).get(SUBSTITUTES).status_code == 403
    assert api(people["teacher"]).get(f"{SUBSTITUTES}candidates/").status_code == 403
    assert field_error(designate(director, physics, people["teacher"]), "substitute_id") == (
        "is_teacher"
    )
    past = (timezone.localdate() - timedelta(days=1)).isoformat()
    assert field_error(designate(director, physics, sub, ends_on=past), "ends_on") == (
        "ends_in_past"
    )

    response = designate(director, physics, sub, ends_on=None)
    assert response.status_code == 201
    row = response.json()
    assert row["label"] == f"Physique · {data['a'].name}"
    assert row["teacher"]["id"] == str(people["teacher"].pk) and row["ends_on"] is None
    assert designate(director, physics, people["director"]).status_code == 409
    assert [r["id"] for r in director.get(SUBSTITUTES).json()] == [row["id"]]
    assert log(school, "grades.substitute_set")[0].after["substitute"] == str(sub)
    # Le remplaçant et l'enseignant sont prévenus ; le remplaçant voit le cours, un total.
    assert {user for user, _ in notified(school, "course_teacher")} == {
        sub.pk,
        people["teacher"].pk,
    }
    assert replaced(api(sub)) == {str(physics.pk): "total"}

    assert director.delete(f"{SUBSTITUTES}{row['id']}/").status_code == 204
    assert log(school, "grades.substitute_removed")[0].before["course"] == row["label"]
    assert replaced(api(sub)) == {}
    assert api(sub).get(sheet_url(physics, data["p1"])).status_code == 403


def test_the_substitute_enters_totals_only_once_the_teacher_has_sent_the_sheet(
    api, school, head, people
):
    data = setup(school, head, teacher=people["teacher"])
    physics, p1, exam = data["physics"], data["p1"], data["exam"]
    designate(api(people["director"]), physics, people["substitute"])
    sub = api(people["substitute"])
    teacher = api(people["teacher"])

    # Brouillon de l'enseignant : fermé au remplaçant, en ligne et hors ligne.
    fill(teacher, data)
    for response in (sub.get(sheet_url(physics, p1)), sub.put(sheet_url(physics, p1), {})):
        assert response.status_code == 403
        assert response.json()["code"] == "sheet_with_teacher"
    remember(sub)
    offline = sub.post(PUSH, {"operations": [grades_op(data, uuid7())]}).json()["results"][0]
    assert offline["error"]["code"] == "sheet_with_teacher"

    # Une correction par un autre que l'enseignant demande un motif, même dans un brouillon.
    director = api(people["director"])
    sheet = director.get(sheet_url(physics, p1)).json()
    total = sheet["evaluations"][0]["id"]
    fix = {"grades": [{"enrollment_id": data["amani"], "evaluation_id": total, "score": "13"}]}
    assert director.put(sheet_url(physics, p1), fix).json()["code"] == "reason_required"
    assert director.put(sheet_url(physics, p1), {**fix, "reason": "Erreur"}).status_code == 200

    # Envoyée : il la lit (un total par élève) et la corrige avec un motif ; journal, enseignant.
    assert teacher.post(action_url(physics, p1, "submit")).status_code == 200
    assert sub.get(sheet_url(physics, p1)).status_code == 200
    fix["grades"][0]["score"] = "14"
    assert sub.put(sheet_url(physics, p1), fix).json()["code"] == "reason_required"
    assert sub.put(sheet_url(physics, p1), {**fix, "reason": "Recompté"}).status_code == 200
    entry = log(school, "grades.changed")[-1]
    assert entry.actor_id == people["substitute"].pk and entry.after["reason"] == "Recompté"
    assert entry.before["grades"][0]["score"] == "13.0"
    assert entry.after["grades"][0]["score"] == "14.0"
    with use_school(school):
        assert CourseSubstitute.objects.count() == 1
    assert (people["teacher"].pk, f"/grades?course={physics.pk}&term={p1.pk}") in notified(
        school, "grades_corrected"
    )

    # Examens pas commencés : il les saisit, corrige ses propres notes sans motif, et signe.
    url = sheet_url(physics, exam)
    evaluation = {"evaluations": [{"name": "Examen", "max_score": 40}]}
    exam_id = sub.put(url, evaluation).json()["evaluations"][0]["id"]
    for score in ("30", "31"):
        body = {
            "grades": [
                {"enrollment_id": data[key], "evaluation_id": exam_id, "score": score}
                for key in ("amani", "josue")
            ]
        }
        assert sub.put(url, body).status_code == 200
    submitted = sub.post(action_url(physics, exam, "submit")).json()
    assert submitted["status"] == "submitted"
    assert submitted["submitted_by"] == str(people["substitute"])


def test_a_joint_course_is_replaced_whole_and_an_expired_designation_gives_nothing(
    api, school, head, people
):
    data = setup(school, head, teacher=people["teacher"])
    with use_school(school):
        group = CourseGroup.objects.create(
            academic_year=data["year"],
            level=data["a"].level,
            name="Physique",
            teacher=people["teacher"],
        )
        for key in ("physics", "b_physics"):
            data[key].course_group = group
            data[key].save(update_fields=["course_group"])
    director = api(people["director"])
    row = designate(director, data["b_physics"], people["substitute"]).json()
    assert row["course_group"] == str(group.pk) and row["course"] is None
    sub = api(people["substitute"])
    assert set(replaced(sub)) == {str(data["physics"].pk), str(data["b_physics"].pk)}

    # Échue (hier) : plus rien, et le directeur peut en désigner un autre.
    with use_school(school):
        CourseSubstitute.objects.update(ends_on=timezone.localdate() - timedelta(days=1))
    assert replaced(sub) == {}
    assert sub.get(sheet_url(data["physics"], data["p1"])).status_code == 403
    assert director.get(SUBSTITUTES).json() == []
    assert designate(director, data["physics"], people["director"]).status_code == 201


def test_another_school_can_neither_see_nor_change_the_substitutes(
    api, school, other_school, head, other_head, people
):
    data = setup(school, head, teacher=people["teacher"])
    setup(other_school, other_head)
    row = designate(api(people["director"]), data["physics"], people["substitute"]).json()
    foreign = MembershipFactory(school=other_school, roles=["study_director"]).user
    beta = api(foreign, host="beta.localhost")
    assert beta.get(SUBSTITUTES).json() == []
    # Personnes qu'on peut désigner : seulement celles de son école.
    assert str(foreign.pk) in {p["id"] for p in beta.get(f"{SUBSTITUTES}candidates/").json()}
    assert str(people["teacher"].pk) not in {
        p["id"] for p in beta.get(f"{SUBSTITUTES}candidates/").json()
    }
    assert beta.delete(f"{SUBSTITUTES}{row['id']}/").status_code == 404
    assert designate(beta, data["physics"], foreign).status_code == 404
    # Un compte d'une autre école ne remplace pas ici.
    with use_school(school):
        CourseSubstitute.objects.all().delete()
    outsider = designate(api(people["director"]), data["physics"], foreign)
    assert field_error(outsider, "substitute_id") == "not_staff"

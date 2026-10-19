"""Espace du titulaire (NB.3) : sa classe dans une période, et « Bulletins prêts »."""

import pytest

from apps.academics.models import Course
from apps.academics.tests.test_grade_control import (
    VALIDATION,
    action_url,
    fill,
    notified,
)
from apps.academics.tests.test_grades import setup
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import ClassGroup
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SPACE = "/api/homeroom/"
READY = "/api/homeroom/ready/"


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


@pytest.fixture
def director(school):
    return MembershipFactory(school=school, roles=["study_director"]).user


@pytest.fixture
def titular(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


def prepared(school, head, teacher, titular) -> dict:
    """Classe A avec la seule Physique (l'atelier n'est pas suivi), `titular` pour titulaire."""
    data = setup(school, head, teacher=teacher)
    with use_school(school):
        Course.objects.filter(pk=data["workshop"].pk).update(is_taught=False)
        ClassGroup.objects.filter(pk=data["a"].pk).update(homeroom_teacher=titular)
    return data


def logged(school, action) -> int:
    with use_school(school):
        return AuditLog.objects.filter(action=action).count()


def board_class(client, data) -> dict:
    classes = client.get(VALIDATION, term=data["p1"].pk).json()["classes"]
    return next(c for c in classes if c["id"] == str(data["a"].pk))


def test_the_homeroom_teacher_checks_the_class_then_declares_the_report_cards_ready(
    api, school, head, teacher, director, titular, django_assert_max_num_queries
):
    data = prepared(school, head, teacher, titular)
    own = api(titular)
    assert own.get("/api/me/").json()["school"]["homeroom"] is True
    assert api(teacher).get("/api/me/").json()["school"]["homeroom"] is False
    fill(api(teacher), data)
    target = {"class_group": data["a"].pk, "term": data["p1"].pk}

    # Notes en cours chez l'enseignant : ni moyenne ni élèves (NB.1), et pas encore prêts.
    space = own.get(SPACE).json()
    assert space["class_group"]["id"] == str(data["a"].pk) and space["term"] == str(data["p1"].pk)
    [row] = space["courses"]
    assert (row["course"]["status"], row["average"]) == ("in_progress", None)
    assert space["students"] == [] and space["stats"] is None and space["complete"] is False
    refused = own.post(READY, target)
    assert refused.status_code == 409 and refused.json()["code"] == "sheets_missing"

    # Envoyée : moyenne du cours ; validée : vérification élève par élève et chiffres.
    api(teacher).post(action_url(data["physics"], data["p1"], "submit"))
    [row] = own.get(SPACE).json()["courses"]
    assert (row["average"], row["below_half"]) == ("67.5", 0)
    api(director).post(action_url(data["physics"], data["p1"], "validate"))
    with django_assert_max_num_queries(26):
        space = own.get(SPACE, **target).json()
    assert [
        (s["full_name"].split()[0], s["total"]["percent"], s["total"]["place"], s["application"])
        for s in space["students"]
    ] == [("Bahati", "60.0", 2, "AB"), ("Kambale", "75.0", 1, "B")]
    assert {s["conduct"] for s in space["students"]} == {"TB"}
    assert space["stats"] == {
        "students": 2,
        "graded": 2,
        "average": "67.5",
        "highest": "75.0",
        "lowest": "60.0",
        "at_least_half": 2,
    }

    # Déclarés prêts : au journal, le directeur des études averti et le voit ; pas deux fois.
    assert own.post(READY, target).status_code == 204
    assert own.post(READY, target).status_code == 204
    assert logged(school, "grades.report_cards_ready") == 1
    link = f"/grade-validation?term={data['p1'].pk}"
    assert notified(school, "report_cards_ready") == [(director.pk, link)]
    assert board_class(api(director), data)["ready_by"] == titular.get_full_name()
    assert own.get(SPACE).json()["ready_at"]

    # Renvoyée puis validée de nouveau : le signal tombe, à déclarer encore.
    boss = api(director)
    boss.post(action_url(data["physics"], data["p1"], "reopen"), {"reason": "Erreur de report"})
    api(teacher).post(action_url(data["physics"], data["p1"], "submit"))
    boss.post(action_url(data["physics"], data["p1"], "validate"))
    assert board_class(boss, data)["complete"] is True
    assert board_class(boss, data)["ready_at"] is None
    assert own.post(READY, target).status_code == 204
    assert board_class(boss, data)["ready_at"]

    # Retirée par le titulaire : au journal.
    assert own.delete(f"{READY}?class_group={data['a'].pk}&term={data['p1'].pk}").status_code == 204
    assert own.get(SPACE).json()["ready_at"] is None
    assert logged(school, "grades.report_cards_withdrawn") == 1


def test_only_the_homeroom_teacher_of_this_school_opens_the_space(
    api, school, other_school, head, other_head, teacher, director, titular
):
    data = prepared(school, head, teacher, titular)
    target = {"class_group": data["a"].pk, "term": data["p1"].pk}
    delete = f"{READY}?class_group={data['a'].pk}&term={data['p1'].pk}"
    # Enseignant du cours, directeur des études : pas titulaires de la classe.
    for user in (teacher, director):
        client = api(user)
        assert client.get(SPACE, class_group=data["a"].pk).status_code == 403
        assert client.post(READY, target).status_code == 403
        assert client.delete(delete).status_code == 403
        assert client.get(SPACE).json()["classes"] == []
    # Le préfet n'a aucun droit de notes.
    assert api(head).get(SPACE).status_code == 403
    # Un semestre n'a pas de fiches : 400.
    semester = {"class_group": data["a"].pk, "term": data["semester"].pk}
    assert api(titular).post(READY, semester).status_code == 400

    # Titulaire d'une autre école : la classe d'ici est introuvable.
    other = setup(other_school, other_head)
    foreign = MembershipFactory(school=other_school, roles=["teacher"]).user
    with use_school(other_school):
        ClassGroup.objects.filter(pk=other["a"].pk).update(homeroom_teacher=foreign)
    beta = api(foreign, host="beta.localhost")
    assert beta.get(SPACE, class_group=data["a"].pk).status_code == 404
    assert beta.post(READY, target).status_code == 404
    assert beta.delete(delete).status_code == 404
    own = beta.get(SPACE).json()
    assert [c["id"] for c in own["classes"]] == [str(other["a"].pk)]
    assert beta.get(SPACE, class_group=other["a"].pk, term=data["p1"].pk).json()["term"] == str(
        other["p1"].pk
    )

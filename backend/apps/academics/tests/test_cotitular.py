"""Saisie d'une fiche de cotes rendue sur papier (NB.7) : le titulaire et le cotitulaire de la
classe, comme `grades.enter_any`, y mettent un total par élève puis l'envoient ; jamais dans le
carnet d'un enseignant qui a ses devoirs ; le cotitulaire ouvre « Ma classe » sans déclarer les
bulletins prêts ; une autre école ne voit rien."""

import pytest

from apps.academics.tests.test_grade_control import action_url
from apps.academics.tests.test_grades import GRADING, setup, sheet_url
from apps.academics.tests.test_homeroom import READY, SPACE
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import ClassGroup
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

CLASSES = "/api/class-groups/"


def enter_totals(client, data, course) -> dict:
    """Le total de chaque élève de la classe A dans `course` (sur 100 : l'atelier)."""
    url = sheet_url(course, data["p1"])
    first = client.put(url, {"evaluations": [{"name": "Total", "max_score": 100}]})
    assert first.status_code == 200, first.json()
    evaluation = first.json()["evaluations"][0]["id"]
    body = {
        "grades": [
            {"enrollment_id": data["amani"], "evaluation_id": evaluation, "score": "64"},
            {"enrollment_id": data["josue"], "evaluation_id": evaluation, "score": "51"},
        ]
    }
    saved = client.put(url, body)
    assert saved.status_code == 200, saved.json()
    return saved.json()


def test_homeroom_and_co_homeroom_complete_a_paper_sheet(api, school, head):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    titular = MembershipFactory(school=school, roles=["teacher"]).user
    helper = MembershipFactory(school=school, roles=["teacher"]).user
    stranger = MembershipFactory(school=school, roles=["teacher"]).user
    data = setup(school, head, teacher=teacher)
    client = api(head)

    # Le cotitulaire se règle sur la classe, jamais le titulaire lui-même ; au journal.
    url = f"{CLASSES}{data['a'].pk}/"
    same = client.patch(
        url, {"homeroom_teacher": str(titular.pk), "co_homeroom_teacher": str(titular.pk)}
    )
    assert same.status_code == 400 and "co_homeroom_teacher" in same.json()["fields"]
    saved = client.patch(
        url, {"homeroom_teacher": str(titular.pk), "co_homeroom_teacher": str(helper.pk)}
    )
    assert saved.status_code == 200, saved.json()
    assert saved.json()["co_homeroom_teacher"]["id"] == str(helper.pk)
    with use_school(school):
        entry = AuditLog.objects.filter(action="organisation.class_updated").latest("created_at")
    assert entry.after["co_homeroom_teacher"] == str(helper)

    # Un enseignant qui donne ses devoirs dans l'application garde son carnet.
    notebook = sheet_url(data["physics"], data["p1"])
    two = [{"name": "Interro", "max_score": 10}, {"name": "TP", "max_score": 10}]
    assert api(teacher).put(notebook, {"evaluations": two, "grades": []}).status_code == 200
    for user in (titular, helper):
        refused = api(user).put(notebook, {"evaluations": [], "grades": []})
        assert (refused.status_code, refused.json()["code"]) == (403, "notebook_private")

    # L'atelier, rendu sur papier : le titulaire saisit les totaux et l'envoie ; le cotitulaire
    # aussi (un autre cours) ; un enseignant d'une autre classe ne peut rien.
    listed = api(helper).get(GRADING).json()["classes"]
    assert [c["is_homeroom"] for c in listed] == [True]
    assert {c["name"]: c["access"] for c in listed[0]["courses"]} == {
        "Physique": "total",
        "Atelier": "total",
    }
    assert api(teacher).get(GRADING).json()["classes"][0]["courses"][0]["access"] == "notebook"
    assert api(stranger).get(sheet_url(data["workshop"], data["p1"])).status_code == 403
    sheet = enter_totals(api(helper), data, data["workshop"])
    assert sheet["entry"] == "totals"
    assert [row["total"] for row in sheet["students"]] == ["64.0", "51.0"]
    sent = api(titular).post(action_url(data["workshop"], data["p1"], "submit"))
    assert (sent.status_code, sent.json()["status"]) == (200, "submitted")

    # « Ma classe » : le cotitulaire l'ouvre, seul le titulaire déclare les bulletins prêts.
    space = api(helper).get(SPACE).json()
    assert space["classes"] == [
        {"id": str(data["a"].pk), "name": data["a"].name, "is_titular": False}
    ]
    target = {"class_group": data["a"].pk, "term": data["p1"].pk}
    assert api(helper).post(READY, target).status_code == 403
    assert api(titular).get(SPACE).json()["classes"][0]["is_titular"] is True
    me = api(helper).get("/api/me/").json()
    assert me["school"]["homeroom"] is True


def test_another_school_cannot_name_a_co_homeroom_teacher_nor_enter(
    api, school, other_school, head, other_head
):
    data = setup(school, head)
    theirs = setup(other_school, other_head)
    helper = MembershipFactory(school=school, roles=["teacher"]).user
    foreign = MembershipFactory(school=other_school, roles=["teacher"]).user
    beta = api(other_head, host="beta.localhost")
    # Une personne d'une autre école n'est pas cotitulaire ; une classe d'ici est introuvable.
    refused = api(head).patch(f"{CLASSES}{data['a'].pk}/", {"co_homeroom_teacher": str(foreign.pk)})
    assert refused.status_code == 400
    assert beta.patch(f"{CLASSES}{data['a'].pk}/", {"co_homeroom_teacher": None}).status_code == 404
    with use_school(other_school):
        ClassGroup.objects.filter(pk=theirs["a"].pk).update(co_homeroom_teacher=foreign)
    with use_school(school):
        ClassGroup.objects.filter(pk=data["a"].pk).update(co_homeroom_teacher=helper)
    outsider = api(foreign, host="beta.localhost")
    assert outsider.get(sheet_url(data["workshop"], data["p1"])).status_code == 404
    assert [c["id"] for c in outsider.get(SPACE).json()["classes"]] == [str(theirs["a"].pk)]
    assert api(helper).get(sheet_url(theirs["workshop"], theirs["p1"])).status_code == 404

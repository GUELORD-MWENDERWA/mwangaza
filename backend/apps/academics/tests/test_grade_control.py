"""Contrôle des notes (8.2.2) : état de la feuille (brouillon, envoyée, validée), date limite de
saisie, motif d'une modification après envoi, validation et réouverture par `grades.validate`,
maximum d'un cours déjà noté, historique et isolation entre écoles."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.academics.models import GradeDeadline
from apps.academics.tests.test_courses import courses_url
from apps.academics.tests.test_grades import setup, sheet_url
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

VALIDATION = "/api/grading/validation/"


def deadline_url(term) -> str:
    return f"/api/terms/{term.pk}/grades-deadline/"


def action_url(course, term, action) -> str:
    return f"{sheet_url(course, term)}{action}/"


@pytest.fixture
def secretary(school):
    return MembershipFactory(school=school, roles=["secretary"]).user


@pytest.fixture
def director(school):
    return MembershipFactory(school=school, roles=["study_director"]).user


def fill(client, data, *, amani="12", josue="15", reason=None) -> dict:
    """Une évaluation sur 20 et les deux notes ; renvoie la feuille."""
    url = sheet_url(data["physics"], data["p1"])
    body = {"evaluations": [{"name": "Interro", "max_score": 20}]}
    first = client.put(url, body).json()["evaluations"][0]["id"]
    body = {
        "grades": [
            {"enrollment_id": data["amani"], "evaluation_id": first, "score": amani},
            {"enrollment_id": data["josue"], "evaluation_id": first, "score": josue},
        ],
        **({"reason": reason} if reason else {}),
    }
    return client.put(url, body)


def test_a_sheet_goes_from_draft_to_sent_then_validated_and_is_then_closed(
    api,
    school,
    head,
    secretary,
    director,
):
    data = setup(school, head)
    client, boss = api(secretary), api(director)
    submit = action_url(data["physics"], data["p1"], "submit")
    assert fill(client, data).json()["status"] == "draft"

    # Une case manque : refusé ; complète : envoyée, et le directeur des études la voit à valider.
    url = sheet_url(data["physics"], data["p1"])
    evaluation = client.get(url).json()["evaluations"][0]["id"]
    client.put(
        url,
        {"grades": [{"enrollment_id": data["josue"], "evaluation_id": evaluation, "score": None}]},
    )
    refused = client.post(submit)
    assert refused.status_code == 400 and refused.json()["code"] == "incomplete_sheet"
    client.put(
        url,
        {"grades": [{"enrollment_id": data["josue"], "evaluation_id": evaluation, "score": "15"}]},
    )
    assert client.post(submit).json()["status"] == "submitted"
    assert client.post(submit).json()["code"] == "sheet_not_draft"
    pending = boss.get(VALIDATION).json()["sheets"]
    assert [(row["course_name"], row["class_group"]) for row in pending] == [
        ("Physique", "1RE ÉLECTRICITÉ A")
    ]

    # Envoyée : changer une note demande un motif, gardé dans l'historique de la feuille.
    sent = {
        "grades": [{"enrollment_id": data["amani"], "evaluation_id": evaluation, "score": "13"}]
    }
    refused = client.put(url, sent)
    assert refused.status_code == 400 and refused.json()["code"] == "reason_required"
    changed = client.put(url, {**sent, "reason": "Erreur de copie"}).json()
    assert (
        changed["history"][0]["reason"] == "Erreur de copie"
        and changed["history"][0]["changes"] == 1
    )

    # Seul qui a `grades.validate` valide ; la feuille validée est fermée à tous.
    assert client.post(action_url(data["physics"], data["p1"], "validate")).status_code == 403
    assert (
        boss.post(action_url(data["physics"], data["p1"], "validate")).json()["status"]
        == "validated"
    )
    closed = client.put(url, {**sent, "reason": "Encore"})
    assert closed.status_code == 409 and closed.json()["code"] == "sheet_validated"

    # Rouverte avec un motif : brouillon de nouveau, et le motif est au journal.
    assert (
        boss.post(action_url(data["physics"], data["p1"], "reopen"), {"reason": ""}).status_code
        == 400
    )
    reopened = boss.post(
        action_url(data["physics"], data["p1"], "reopen"), {"reason": "Note à corriger"}
    )
    assert reopened.json()["status"] == "draft" and reopened.json()["reopened"] is True
    with use_school(school):
        actions = list(
            AuditLog.objects.filter(action__startswith="grades.")
            .values_list("action", flat=True)
            .order_by("created_at")
        )
        reason = AuditLog.objects.get(action="grades.reopened").after["reason"]
    assert "grades.submitted" in actions
    assert actions[-3:] == ["grades.changed", "grades.validated", "grades.reopened"]
    assert reason == "Note à corriger"


def test_the_deadline_closes_the_entry_except_for_a_reopened_sheet_or_the_validator(
    api,
    school,
    head,
    secretary,
    director,
):
    data = setup(school, head)
    client, boss = api(secretary), api(director)
    fill(client, data)
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
    assert client.put(deadline_url(data["p1"]), {"due_on": yesterday}).status_code == 403
    assert boss.put(deadline_url(data["p1"]), {"due_on": yesterday}).status_code == 200
    # Pas une période regroupant d'autres : on ne note que périodes et examens.
    assert boss.put(deadline_url(data["semester"]), {"due_on": yesterday}).status_code == 400

    url = sheet_url(data["physics"], data["p1"])
    evaluation = client.get(url).json()["evaluations"][0]["id"]
    late = {"grades": [{"enrollment_id": data["amani"], "evaluation_id": evaluation, "score": "9"}]}
    refused = client.put(url, late)
    assert refused.status_code == 409 and refused.json()["code"] == "deadline_passed"
    assert client.get(url).json()["due_on"] == yesterday
    # Le jour même est encore permis ; le directeur des études peut saisir après la date.
    today = timezone.localdate().isoformat()
    boss.put(deadline_url(data["p1"]), {"due_on": today})
    assert client.put(url, late).status_code == 200
    boss.put(deadline_url(data["p1"]), {"due_on": yesterday})
    assert boss.put(url, late).status_code == 200
    # Une feuille envoyée puis rouverte n'est plus fermée par la date.
    assert client.post(action_url(data["physics"], data["p1"], "submit")).status_code == 200
    boss.post(action_url(data["physics"], data["p1"], "reopen"), {"reason": "Retard justifié"})
    assert client.put(url, late).status_code == 200
    boss.put(deadline_url(data["p1"]), {"due_on": None})
    with use_school(school):
        assert not GradeDeadline.objects.exists()


def test_the_maximum_of_a_graded_course_changes_only_with_validation_rights(
    api,
    school,
    head,
    secretary,
    director,
):
    data = setup(school, head)
    fill(api(secretary), data)
    grid = [
        {
            "id": str(c["id"]),
            "name": c["name"],
            "period_max": c["period_max"],
            "has_exam": c["has_exam"],
        }
        for c in api(head).get(courses_url(data["a"])).json()
    ]
    for row in grid:
        if row["name"] == "Physique":
            row["period_max"] = 40
    # Le directeur (`courses.configure` seul) est refusé ; le directeur des études passe.
    refused = api(head).put(courses_url(data["a"]), {"courses": grid})
    assert refused.status_code == 409 and refused.json()["code"] == "max_graded"
    assert api(director).put(courses_url(data["a"]), {"courses": grid}).status_code == 200


def test_another_school_cannot_see_validate_or_reopen_these_grades(
    api,
    school,
    other_school,
    head,
    other_head,
    secretary,
    director,
):
    data = setup(school, head)
    setup(other_school, other_head)
    fill(api(secretary), data)
    api(secretary).post(action_url(data["physics"], data["p1"], "submit"))
    foreign = MembershipFactory(school=other_school, roles=["study_director"]).user
    beta = api(foreign, host="beta.localhost")
    assert beta.get(VALIDATION).json()["sheets"] == []
    for action in ("validate", "reopen", "submit"):
        assert (
            beta.post(action_url(data["physics"], data["p1"], action), {"reason": "x"}).status_code
            == 404
        )
    assert beta.put(deadline_url(data["p1"]), {"due_on": None}).status_code == 404
    assert beta.get(sheet_url(data["physics"], data["p1"])).status_code == 404
    assert api(director).get(sheet_url(data["physics"], data["p1"])).json()["status"] == "submitted"

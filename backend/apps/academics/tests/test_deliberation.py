"""Délibération d'une classe (8.4.2) : décision proposée et décision prise, écart motivé,
proclamation figée, réouverture et version suivante, droits, journal, isolation."""

import pytest

from apps.academics.models import DeliberationSnapshot
from apps.academics.tests import test_resits
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

# Mêmes élèves, cours et notes que le repêchage.
data = test_resits.data
physics_teacher = test_resits.physics_teacher


def url(data, tail="") -> str:
    return f"/api/class-groups/{data['a'].pk}/deliberation/{tail}"


def decide(client, data, key, decision, reason=""):
    return client.put(
        f"/api/deliberation/enrollments/{data[key]}/", {"decision": decision, "reason": reason}
    )


@pytest.fixture
def director(api, school):
    return api(MembershipFactory(school=school, roles=["study_director"]).user)


def row(client, data, key):
    rows = client.get(url(data)).json()["students"]
    return next(r for r in rows if r["enrollment"] == data[key])


def test_proposal_follows_the_rules_and_a_gap_needs_a_reason(director, data):
    # Amani réussit tout, Josué (48 % en Physique) attend son repêchage.
    assert row(director, data, "amani")["proposed"] == "pass"
    assert row(director, data, "josue")["proposed"] == "resit"

    refused = decide(director, data, "josue", "pass")
    assert (refused.status_code, refused.json()["code"]) == (400, "reason_required")
    assert decide(director, data, "josue", "nonsense").status_code == 400

    done = decide(director, data, "josue", "pass", "Moyenne forte en atelier").json()
    kambale = next(r for r in done["students"] if r["enrollment"] == data["josue"])
    assert (kambale["deviates"], kambale["decision"]) == (True, "pass")
    assert done["deviations"] == 1
    # Avec la décision proposée, aucun motif.
    assert decide(director, data, "amani", "pass").json()["deviations"] == 1


def test_proclaiming_needs_a_date_every_decision_and_freezes_the_results(director, data):
    assert director.post(url(data, "proclaim/")).json()["code"] == "date_required"
    assert director.put(url(data), {"held_on": "2027-06-20"}).status_code == 200
    assert director.post(url(data, "proclaim/")).json()["code"] == "undecided"
    assert director.post(url(data, "apply-proposals/")).status_code == 200
    assert row(director, data, "josue")["decision"] == "resit"

    done = director.post(url(data, "proclaim/")).json()
    assert (done["status"], done["version"]) == ("proclaimed", 1)
    # Classe proclamée : plus de décision, plus de date.
    assert decide(director, data, "josue", "repeat", "x").json()["code"] == "deliberation_closed"
    assert director.put(url(data), {"held_on": "2027-06-21"}).status_code == 400

    # Correction : motif obligatoire ; la proclamation suivante crée la version 2, la 1 reste.
    assert director.post(url(data, "reopen/"), {"reason": " "}).status_code == 400
    assert director.post(url(data, "reopen/"), {"reason": "Repêchage corrigé"}).status_code == 200
    assert decide(director, data, "josue", "repeat", "Échec au repêchage").status_code == 200
    again = director.post(url(data, "proclaim/")).json()
    assert (again["version"], again["latest"]["reason"]) == (2, "Repêchage corrigé")
    assert again["deviations"] == 1

    with use_school(data["a"].school):
        old, new = DeliberationSnapshot.objects.order_by("version")
        josue = str(data["josue"])
        assert [r["decision"] for r in old.rows if r["enrollment"] == josue] == ["resit"]
        assert [r["decision"] for r in new.rows if r["enrollment"] == josue] == ["repeat"]
        actions = AuditLog.objects.filter(action__startswith="deliberation.")
        assert {a.action for a in actions} == {
            "deliberation.decided",
            "deliberation.proclaimed",
            "deliberation.reopened",
        }


def test_only_the_direction_of_studies_deliberates(api, school, physics_teacher, data):
    teacher = api(physics_teacher)
    assert teacher.get(url(data)).status_code == 403
    assert decide(teacher, data, "amani", "pass").status_code == 403
    assert teacher.post(url(data, "proclaim/")).status_code == 403


def test_another_school_cannot_read_or_decide(api, other_school, data):
    other = api(
        MembershipFactory(school=other_school, roles=["study_director"]).user, host="beta.localhost"
    )
    assert other.get(url(data)).status_code == 404
    assert decide(other, data, "amani", "pass").status_code == 404
    assert other.post(url(data, "proclaim/")).status_code == 404

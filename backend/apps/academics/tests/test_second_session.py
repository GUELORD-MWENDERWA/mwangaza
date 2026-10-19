"""Seconde session (NB.6) : élèves envoyés au repêchage par la proclamation de fin d'année, date de
l'examen et convocations, note de repêchage, délibération de seconde session (décision finale)
qui remplace « repêchage » sur le bulletin, dans les situations et au passage de classe ; droits,
journal, isolation."""

import pytest

from apps.academics import deliberation
from apps.academics.tests import test_resits
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

data = test_resits.data
physics_teacher = test_resits.physics_teacher
resit_url = test_resits.resit_url
SECOND = "?second=true"


def url(data, tail="") -> str:
    return f"/api/class-groups/{data['a'].pk}/{tail}"


@pytest.fixture
def director(api, school):
    return api(MembershipFactory(school=school, roles=["study_director"]).user)


def proclaim_year(director, data) -> None:
    director.put(url(data, "deliberation/"), {"held_on": "2027-07-02"})
    director.post(url(data, "deliberation/apply-proposals/"))
    assert director.post(url(data, "deliberation/proclaim/")).status_code == 200


def decide(client, data, key, decision, reason=""):
    return client.put(
        f"/api/deliberation/enrollments/{data[key]}/{SECOND}",
        {"decision": decision, "reason": reason},
    )


def test_the_second_session_gives_the_final_decision_read_everywhere(
    api, director, physics_teacher, data
):
    # Rien de proclamé : pas de seconde session.
    refused = director.get(url(data, "deliberation/") + SECOND)
    assert refused.json()["code"] == "no_second_session"
    proclaim_year(director, data)
    year = director.get(url(data, "deliberation/")).json()
    assert year["has_second_session"] is True

    # Date de l'examen, puis convocations : Josué seul, Physique à repasser.
    session = director.get(url(data, "resits/")).json()["second_session"]
    assert (session["students"], session["exam_on"]) == (1, None)
    no_date = director.get(url(data, "resits/convocations/"), output="html")
    assert no_date.json()["code"] == "exam_date_required"
    assert (
        director.put(url(data, "resits/exam-date/"), {"exam_on": "2027-08-23"}).status_code == 200
    )
    notices = director.get(url(data, "resits/convocations/"), output="html")
    [notice] = notices.context["rows"]
    assert [line["course"] for line in notice.resits] == ["Physique"]
    assert str(notices.context["exam_on"]) == "2027-08-23"

    # Seconde session : Josué seul, sans proposition tant que la note manque ; jamais un nouveau
    # repêchage ; Amani n'y est pas.
    board = director.get(url(data, "deliberation/") + SECOND).json()
    assert board["kind"] == "second"
    [josue] = board["students"]
    assert (josue["enrollment"], josue["proposed"]) == (str(data["josue"]), "")
    assert decide(director, data, "josue", "resit").json()["code"] == "resit_again"
    assert decide(director, data, "amani", "pass").json()["code"] == "not_in_second_session"

    # La note de repêchage décide ; l'élève garde son pourcentage de l'année.
    assert api(physics_teacher).put(resit_url(data), {"percent": "55"}).status_code == 200
    board = director.get(url(data, "deliberation/") + SECOND).json()
    [josue] = board["students"]
    assert (josue["proposed"], josue["percent"]) == ("pass", year_percent(year, data))
    assert josue["resits"] == [
        {"course": "Physique", "percent": "48.0", "resit_percent": "55.0", "passed": True}
    ]
    director.put(url(data, "deliberation/") + SECOND, {"held_on": "2027-08-27"})
    director.post(url(data, "deliberation/apply-proposals/") + SECOND)
    done = director.post(url(data, "deliberation/proclaim/") + SECOND).json()
    assert (done["status"], done["version"]) == ("proclaimed", 1)

    # Note bloquée une fois la seconde session proclamée.
    closed = api(physics_teacher).put(resit_url(data), {"percent": "40"})
    assert closed.json()["code"] == "second_session_closed"

    # Bulletin : la décision et la date de la seconde session ; Amani garde la fin d'année.
    def end(key):
        page = director.get(url(data, "report-card/"), enrollment=data[key], output="html").context
        return page["end"]

    assert (end("josue")["keep"], str(end("josue")["date"])) == ("move", "2027-08-27")
    assert (end("amani")["keep"], str(end("amani")["date"])) == ("move", "2027-07-02")
    # Situations et passage de classe lisent la même décision finale.
    with use_school(data["a"].school):
        rows = deliberation.year_results([data["a"]])[data["a"].pk].rows
        assert rows[str(data["josue"])]["decision"] == "pass"
        proclaimed = AuditLog.objects.filter(action="deliberation.proclaimed")
        assert [a.after["second_session"] for a in proclaimed.order_by("created_at")] == [
            False,
            True,
        ]
    minutes = director.get(url(data, "deliberation/minutes/") + SECOND + "&output=html")
    assert minutes.status_code == 200
    assert minutes.context["session"] == "Seconde session"


def year_percent(year, data) -> str:
    return next(r["percent"] for r in year["students"] if r["enrollment"] == str(data["josue"]))


def test_a_resit_granted_by_the_council_opens_every_failed_course(
    api, head, director, physics_teacher, data
):
    # Repêchage à partir de 75 % : Josué (70,9 %) devrait doubler ; pas de note possible.
    api(head).patch(f"/api/levels/{data['a'].level_id}/", {"pass_rules": {"resit_percent": 75}})
    teacher = api(physics_teacher)
    assert teacher.put(resit_url(data), {"percent": "60"}).json()["code"] == "not_a_resit_course"
    # Le conseil accorde le repêchage (écart motivé) et proclame.
    director.put(url(data, "deliberation/"), {"held_on": "2027-07-02"})
    director.post(url(data, "deliberation/apply-proposals/"))
    director.put(
        f"/api/deliberation/enrollments/{data['josue']}/",
        {"decision": "resit", "reason": "Progrès au troisième trimestre"},
    )
    director.post(url(data, "deliberation/proclaim/"))
    # Le cours échoué se repasse ; la note seule décide.
    assert teacher.put(resit_url(data), {"percent": "60"}).status_code == 200
    [josue] = director.get(url(data, "deliberation/") + SECOND).json()["students"]
    assert (josue["proposed"], josue["rule"]) == ("pass", "resits_passed")


def test_rights_and_isolation_of_the_second_session(
    api, school, other_school, director, physics_teacher, data
):
    proclaim_year(director, data)
    secretary = api(MembershipFactory(school=school, roles=["secretary"]).user)
    teacher = api(physics_teacher)
    for client in (secretary, teacher):
        assert (
            client.put(url(data, "resits/exam-date/"), {"exam_on": "2027-08-23"}).status_code == 403
        )
        assert client.get(url(data, "resits/convocations/")).status_code == 403
    # Membre du conseil : il lit la seconde session, il ne décide pas.
    assert teacher.get(url(data, "deliberation/") + SECOND).status_code == 200
    assert decide(teacher, data, "josue", "pass").status_code == 403
    assert secretary.get(url(data, "deliberation/") + SECOND).status_code == 403

    other = api(
        MembershipFactory(school=other_school, roles=["study_director"]).user, host="beta.localhost"
    )
    assert other.get(url(data, "deliberation/") + SECOND).status_code == 404
    assert other.put(url(data, "resits/exam-date/"), {"exam_on": "2027-08-23"}).status_code == 404
    assert other.get(url(data, "resits/convocations/")).status_code == 404
    assert decide(other, data, "josue", "pass").status_code == 404

"""Analyse et propositions (IA.2b) : ce que l'IA reçoit, actions vérifiées une à une, application
par les services normaux avec journal, droits et isolation. L'API de l'IA est simulée."""

import pytest

from apps.academics.models import Course
from apps.academics.tests.test_courses import classes
from apps.ai import services
from apps.ai.models import AiCall
from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.timetable import assistant, constraints, review
from apps.timetable.models import TimetableRule
from apps.timetable.tests.test_assistant import director, reply, sent  # noqa: F401
from apps.timetable.tests.test_constraints import new
from apps.timetable.tests.test_timetable import log
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

REVIEW = "/api/timetable/review/"


def allow(school, platform_admin):
    services.set_allowance(
        school, actor=platform_admin, uses_=[review.USE], monthly_credits=100, paused=False
    )


def act(kind, ref, pattern="", note="Aide."):
    return {"kind": kind, "ref": ref, "pattern": pattern, "note": note}


def ask(client_):
    return client_.post(REVIEW, {"request_id": str(uuid7())})


def test_actions_checked_applied_with_journal_once(
    api,
    school,
    head,
    other_school,
    other_head,
    platform_admin,
    reply,  # noqa: F811
):
    allow(school, platform_admin)
    mine = new(classes(school, head)["a"], "Atelier", 6)
    foreign = new(classes(other_school, other_head)["a"], "Théâtre", 6)
    user = director(school)
    client_ = api(user)
    with use_school(school):
        rule = constraints.create_rule(
            actor=user,
            kind="course_not_slot",
            params={"target": {"scope": "name", "value": "Atelier"}, "weekday": 1},
            strength="hard",
        )
    rule_code = assistant._ref("L", rule.pk)
    reply.clear()
    reply.update(
        explanation="La classe est trop chargée.",
        actions=[
            act("soften_rule", rule_code),
            act("set_pattern", assistant._ref("C", mine.pk), "3+3"),
            act("set_pattern", assistant._ref("C", mine.pk), "2+2"),  # ne fait pas 6 h
            act("set_pattern", assistant._ref("C", foreign.pk), "3+3"),  # autre école
            act("pause_rule", "L00000000"),  # règle inventée
            act("need_teacher", ""),
        ],
    )

    asked = ask(client_)
    assert asked.status_code == 202, asked.json()
    state = client_.get(f"{REVIEW}{asked.json()['id']}/").json()
    assert "Théâtre" not in sent[0]
    proposal = state["proposal"]
    assert proposal["explanation"] == "La classe est trop chargée."
    assert [a["kind"] for a in proposal["actions"]] == [
        "soften_rule",
        "set_pattern",
        "need_teacher",
    ]
    soften, pattern, _advice = proposal["actions"]

    done = client_.post(f"{REVIEW}{state['id']}/apply/", {"key": soften["key"]})
    assert done.status_code == 200, done.json()
    assert [a["kind"] for a in done.json()["proposal"]["actions"]] == [
        "set_pattern",
        "need_teacher",
    ]
    assert client_.post(f"{REVIEW}{state['id']}/apply/", {"key": soften["key"]}).status_code == 409
    assert client_.post(f"{REVIEW}{state['id']}/apply/", {"key": pattern["key"]}).status_code == 200
    with use_school(school):
        assert TimetableRule.objects.get(pk=rule.pk).strength == "soft"
        assert Course.objects.get(pk=mine.pk).lesson_pattern == "3+3"
    assert len(log(school, Action.TIMETABLE_RULE_CHANGED)) == 2  # création + assouplie
    assert len(log(school, Action.COURSES_CHANGED)) == 1

    assert client_.post(f"{REVIEW}{state['id']}/finish/", {"applied": True}).status_code == 204
    with use_school(school):
        assert AiCall.objects.get(pk=state["id"]).state == "kept"
    assert client_.post(f"{REVIEW}{state['id']}/finish/", {"applied": True}).status_code == 409
    assert client_.post(f"{REVIEW}{state['id']}/apply/", {"key": pattern["key"]}).status_code == 409


def test_rights_and_other_schools(
    api,
    school,
    head,
    other_school,
    other_head,
    platform_admin,
    reply,  # noqa: F811
):
    allow(school, platform_admin)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert ask(api(teacher)).status_code == 403
    no_ai = director(school, ("timetable.manage",))
    refusal = ask(api(no_ai))
    assert (refusal.status_code, refusal.json()["code"]) == (403, "ai_forbidden")
    assert ask(api(other_head, host="beta.localhost")).status_code == 403  # usage non affecté

    reply.clear()
    reply.update(explanation="Tout va bien.", actions=[])
    mine = ask(api(director(school))).json()
    stranger = api(other_head, host="beta.localhost")
    assert stranger.get(f"{REVIEW}{mine['id']}/").status_code == 404
    assert stranger.post(f"{REVIEW}{mine['id']}/apply/", {"key": "x"}).status_code == 404
    assert api(head).get(f"{REVIEW}{mine['id']}/").status_code == 404  # appel d'une autre personne
    # Un horaire d'une autre école n'est pas analysable.
    unknown = api(director(school)).post(
        REVIEW, {"request_id": str(uuid7()), "timetable": str(uuid7())}
    )
    assert unknown.status_code == 404

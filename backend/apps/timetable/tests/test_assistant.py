"""Consignes en phrases → règles (IA.2a) : droits et verrous de l'IA, isolation, schéma de chaque
règle proposée, enregistrement une seule fois avec journal. L'API de l'IA est simulée."""

import json

import pytest

from apps.academics.tests.test_courses import classes
from apps.accounts.models import Role
from apps.ai import client, services
from apps.ai.models import AiCall
from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.timetable import assistant
from apps.timetable.models import TimetableRule
from apps.timetable.tests.test_constraints import new
from apps.timetable.tests.test_timetable import log
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

ASK = "/api/timetable/constraints/assist/"


sent: list[str] = []  # ce que l'IA a reçu


@pytest.fixture
def reply(monkeypatch):
    """L'API simulée rend `items` ; la tâche de fond tourne tout de suite."""
    answer = {"items": []}
    sent.clear()

    def fake(**kwargs):
        sent.append(kwargs["messages"][0]["content"])
        return client.Reply(
            text=json.dumps(answer), stop_reason="end_turn", model=kwargs["model"], input_tokens=900
        )

    monkeypatch.setattr(client, "complete", fake)
    monkeypatch.setattr(
        services,
        "_enqueue",
        lambda call, payload: services.execute(str(call.pk), str(call.school_id), payload),
    )
    return answer


def item(sentence, kind, params, *, strength="hard", understood=True, reason=""):
    return {
        "sentence": sentence,
        "understood": understood,
        "kind": kind,
        "strength": strength,
        "params_json": json.dumps(params),
        "reason": reason,
    }


def director(school, permissions=("ai.use", "timetable.manage")):
    with use_school(school):
        role = Role.objects.create(name=f"Directeur IA {uuid7()}", permissions=list(permissions))
    return MembershipFactory(school=school, roles=[role]).user


def allow(school, platform_admin):
    services.set_allowance(
        school,
        actor=platform_admin,
        uses_=[assistant.USE],
        monthly_credits=100,
        paused=False,
    )


def ask(client_, text="Consignes"):
    return client_.post(ASK, {"request_id": str(uuid7()), "text": text})


def test_sentences_become_checked_rules_kept_once(
    api, school, head, other_school, other_head, platform_admin, reply
):
    allow(school, platform_admin)
    data = classes(school, head)
    theirs = classes(other_school, other_head)
    atelier = new(data["a"], "Atelier", 6)
    foreign = new(theirs["a"], "Théâtre", 6)
    user = director(school)
    client_ = api(user)
    mia = MembershipFactory(school=school, roles=["teacher"]).user
    code = assistant._ref("T", mia.pk)
    reply["items"] = [
        item("Mia ne vient pas le vendredi.", "teacher_free_day", {"teacher": code, "weekday": 5}),
        item(
            "Atelier le lundi.",
            "fixed_lesson",
            {"course": assistant._ref("C", atelier.pk), "weekday": 1, "first": 2, "last": 4},
        ),
        # Un cours d'une autre école, un code inventé, une consigne hors liste.
        item(
            "Atelier de l'autre école.",
            "fixed_lesson",
            {"course": assistant._ref("C", foreign.pk), "weekday": 1, "first": 1, "last": 2},
        ),
        item("Pas de cours en ville.", "none", {}, understood=False, reason="Hors liste."),
    ]

    asked = ask(client_, "Mia ne vient pas le vendredi. Atelier le lundi.")
    assert asked.status_code == 202, asked.json()
    state = client_.get(f"{ASK}{asked.json()['id']}/").json()
    assert state["state"] == "done"
    assert "Atelier" in sent[0] and "Théâtre" not in sent[0]  # seulement les noms de l'école
    ok, locked, theirs_row, unknown = state["proposals"]
    assert (ok["rule"]["kind"], ok["rule"]["params"]["teacher"]) == (
        "teacher_free_day",
        str(mia.pk),
    )
    assert locked["rule"]["params"]["course"] == str(atelier.pk)
    assert theirs_row["rule"] is None and theirs_row["reason"]  # refusée par le schéma
    assert unknown["rule"] is None and unknown["reason"] == "Hors liste."

    kept = client_.post(
        f"{ASK}{state['id']}/keep/",
        {"items": [{"sentence": row["sentence"], "rule": row["rule"]} for row in (ok, locked)]},
    )
    assert kept.status_code == 200, kept.json()
    with use_school(school):
        rules = list(TimetableRule.objects.order_by("created_at"))
        assert [(r.source, r.text) for r in rules] == [
            ("ai", "Mia ne vient pas le vendredi."),
            ("ai", "Atelier le lundi."),
        ]
        assert AiCall.objects.get(pk=state["id"]).state == "kept"
    assert len(log(school, Action.TIMETABLE_RULE_CHANGED)) == 2
    again = client_.post(
        f"{ASK}{state['id']}/keep/",
        {"items": [{"sentence": ok["sentence"], "rule": ok["rule"]}]},
    )
    assert again.status_code == 409
    assert client_.post(f"{ASK}{state['id']}/abandon/").status_code == 409


def test_rights_locks_and_other_schools(
    api, school, head, other_school, other_head, platform_admin, reply
):
    allow(school, platform_admin)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert ask(api(teacher)).status_code == 403
    no_ai = director(school, ("timetable.manage",))
    refusal = ask(api(no_ai))
    assert (refusal.status_code, refusal.json()["code"]) == (403, "ai_forbidden")
    # Une école que la plateforme n'a pas affectée à l'usage : refus, sans appel.
    refusal = ask(api(other_head, host="beta.localhost"))
    assert refusal.status_code == 403

    mine = ask(api(director(school))).json()
    stranger = api(other_head, host="beta.localhost")
    assert stranger.get(f"{ASK}{mine['id']}/").status_code == 404
    assert stranger.post(f"{ASK}{mine['id']}/abandon/").status_code == 404
    assert api(head).get(f"{ASK}{mine['id']}/").status_code == 404  # l'appel d'une autre personne

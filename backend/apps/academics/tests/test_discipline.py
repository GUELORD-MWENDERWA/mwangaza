"""Conduite (8.5.1a) : liste des infractions, seuils des cotes, incidents ; droits, points copiés,
annulation sans effacement, journal et isolation entre écoles."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.academics.models import DisciplineIncident
from apps.academics.tests.test_grades import setup
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import School, Term
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

RULES = "/api/discipline/rules/"
SCALE = "/api/discipline/scale/"
INCIDENTS = "/api/discipline/incidents/"


@pytest.fixture
def master(school):
    return MembershipFactory(school=school, roles=["discipline_master"]).user


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


@pytest.fixture
def data(school, head):
    return setup(school, head)


def add_rule(client, label="Retard", points=2) -> dict:
    response = client.post(RULES, {"label": label, "points": points})
    assert response.status_code == 201
    return response.json()


def incident(client, data, rule, **extra):
    body = {
        "enrollment": data["amani"],
        "rule": rule["id"],
        "occurred_on": str(timezone.localdate()),
        "term": str(data["p1"].pk),
        **extra,
    }
    return client.post(INCIDENTS, body)


def log(school, action) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action=action))


def test_rights_and_module(api, school, master, teacher, head, data):
    rule = add_rule(api(master))
    # L'enseignant attribue et lit la liste, mais ne la change pas.
    assert api(teacher).get(RULES).status_code == 200
    assert api(teacher).post(RULES, {"label": "X", "points": 1}).status_code == 403
    assert api(teacher).put(SCALE, {"scale": []}).status_code == 403
    assert incident(api(teacher), data, rule).status_code == 201
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    assert api(secretary).get(RULES).status_code == 403
    assert incident(api(secretary), data, rule).status_code == 403
    # Un enseignant ne peut pas annuler.
    created = incident(api(teacher), data, rule).json()
    assert (
        api(teacher).post(f"{INCIDENTS}{created['id']}/cancel/", {"reason": "x"}).status_code == 403
    )

    School.objects.filter(pk=school.pk).update(modules=["students"])
    assert api(master).get(RULES).json()["code"] == "module_missing"


def test_points_are_copied_and_a_cancelled_incident_stays_but_no_longer_counts(
    api, school, master, data
):
    client = api(master)
    rule = add_rule(client, points=4)
    first = incident(client, data, rule).json()
    incident(client, data, add_rule(client, "Bagarre", 10))
    # Changer le barème ne réécrit pas le passé.
    client.patch(f"{RULES}{rule['id']}/", {"points": 9})
    again = incident(client, data, rule).json()
    assert (first["points"], again["points"]) == (4, 9)

    url = f"/api/discipline/enrollments/{data['amani']}/"
    totals = client.get(url).json()["totals"]
    assert (totals[0]["points"], totals[0]["grade"]) == (23, "ME")

    cancelled = client.post(f"{INCIDENTS}{first['id']}/cancel/", {"reason": "Erreur d'élève"})
    assert cancelled.status_code == 200
    assert client.post(f"{INCIDENTS}{first['id']}/cancel/", {"reason": "bis"}).status_code == 409
    body = client.get(url).json()
    assert len(body["incidents"]) == 3
    assert body["totals"][0]["points"] == 19
    assert any(row["cancelled"] and row["cancel_reason"] for row in body["incidents"])
    with use_school(school):
        assert DisciplineIncident.objects.count() == 3
    assert len(log(school, "discipline.incident_recorded")) == 3
    assert len(log(school, "discipline.incident_cancelled")) == 1


def test_retired_offence_cannot_be_attributed_and_term_comes_from_the_date(
    api, school, master, data
):
    client = api(master)
    rule = add_rule(client)
    assert incident(client, data, rule, term=None).status_code == 400  # aucune période datée
    today = timezone.localdate()
    with use_school(school):
        Term.objects.filter(pk=data["p1"].pk).update(
            starts_on=today - timedelta(days=30), ends_on=today + timedelta(days=30)
        )
    assert incident(client, data, rule, term=None).status_code == 201
    future = str(today + timedelta(days=1))
    assert incident(client, data, rule, occurred_on=future).json()["code"] == "future_date"
    # Une période d'un autre genre (examens) est refusée.
    assert incident(client, data, rule, term=str(data["exam"].pk)).status_code == 400

    client.patch(f"{RULES}{rule['id']}/", {"is_active": False})
    assert incident(client, data, rule).json()["code"] == "rule_inactive"
    assert client.get(RULES).json() == []
    assert len(client.get(f"{RULES}?all=1").json()) == 1


def test_scale_defaults_and_validation(api, school, master):
    client = api(master)
    assert [row["min_points"] for row in client.get(SCALE).json()["scale"]] == [0, 5, 10, 15, 25]

    def rows(*minimums):
        grades = ["TB", "B", "AB", "ME", "MA"]
        return {
            "scale": [{"grade": g, "min_points": n} for g, n in zip(grades, minimums, strict=True)]
        }

    assert client.put(SCALE, rows(0, 3, 3, 8, 12)).json()["code"] == "bad_scale"
    assert client.put(SCALE, rows(1, 3, 6, 8, 12)).json()["code"] == "bad_scale"
    assert client.put(SCALE, rows(0, 3, 6, 8, 12)).status_code == 200
    assert [row["min_points"] for row in client.get(SCALE).json()["scale"]] == [0, 3, 6, 8, 12]
    assert len(log(school, "discipline.scale_changed")) == 1


def test_default_list_only_when_empty(api, school, master):
    client = api(master)
    assert client.post(f"{RULES}defaults/").status_code == 201
    assert len(client.get(RULES).json()) == 10
    assert client.post(f"{RULES}defaults/").status_code == 409


def test_another_school_sees_and_changes_nothing(
    api, school, other_school, master, data, other_head
):
    rule = add_rule(api(master))
    created = incident(api(master), data, rule).json()
    other_master = MembershipFactory(school=other_school, roles=["discipline_master"]).user
    beta = api(other_master, host="beta.localhost")
    assert beta.get(RULES).json() == []
    assert beta.patch(f"{RULES}{rule['id']}/", {"points": 1}).status_code == 404
    assert beta.get(f"/api/discipline/enrollments/{data['amani']}/").status_code == 404
    assert beta.post(f"{INCIDENTS}{created['id']}/cancel/", {"reason": "x"}).status_code == 404
    assert beta.get(f"/api/discipline/classes/{data['a'].pk}/students/").status_code == 404
    # Ni une inscription ni une infraction d'une autre école n'entrent dans un incident.
    sent = beta.post(
        INCIDENTS,
        {"enrollment": data["amani"], "rule": rule["id"], "occurred_on": "2026-09-10"},
    )
    assert sent.status_code == 400
    assert beta.get(SCALE).json()["scale"][1]["min_points"] == 5
    assert (
        api(master)
        .put(
            SCALE,
            {
                "scale": [
                    {"grade": g, "min_points": n}
                    for g, n in zip(["TB", "B", "AB", "ME", "MA"], [0, 2, 4, 6, 8], strict=True)
                ]
            },
        )
        .status_code
        == 200
    )
    assert beta.get(SCALE).json()["scale"][1]["min_points"] == 5


# Cote de conduite et correction (8.5.1b)


def grade_url(data) -> str:
    return f"/api/discipline/enrollments/{data['amani']}/grade/"


def test_override_needs_its_right_a_reason_and_is_logged_then_cleared(
    api, school, master, teacher, data
):
    client = api(master)
    incident(client, data, add_rule(client, points=12))
    body = {"term": str(data["p1"].pk), "grade": "B", "reason": "Délibération du conseil"}
    # L'enseignant attribue des fautes mais ne corrige pas la cote.
    assert api(teacher).put(grade_url(data), body).status_code == 403
    assert client.put(grade_url(data), {**body, "reason": " "}).status_code == 400
    assert client.put(grade_url(data), {**body, "grade": "ZZ"}).status_code == 400
    exam = {**body, "term": str(data["exam"].pk)}
    assert client.put(grade_url(data), exam).json()["code"] == "bad_term_grade"

    changed = client.put(grade_url(data), body).json()
    first = next(t for t in changed["totals"] if t["term"] == str(data["p1"].pk))
    assert (first["calculated"], first["grade"]) == ("AB", "B")
    assert first["override_reason"] == "Délibération du conseil"
    [entry] = log(school, "discipline.grade_overridden")
    assert (entry.before["grade"], entry.after["grade"]) == ("AB", "B")

    # Reprendre la cote rend celle des points.
    cleared = client.delete(f"{grade_url(data)}?term={data['p1'].pk}").json()
    assert next(t for t in cleared["totals"] if t["term"] == str(data["p1"].pk))["grade"] == "AB"
    assert len(log(school, "discipline.grade_overridden")) == 2


def test_the_report_card_shows_the_retained_conduct_grade_of_each_period(api, school, master, data):
    director = MembershipFactory(school=school, roles=["study_director"]).user
    client = api(master)
    incident(client, data, add_rule(client, points=12))
    client.put(grade_url(data), {"term": str(data["p1"].pk), "grade": "TB", "reason": "Conseil"})
    page = api(director).get(
        f"/api/class-groups/{data['a'].pk}/report-card/", enrollment=data["amani"], output="html"
    )
    amani = [c["grade"] for c in page.context["conduct"] if c["kind"] == "period"]
    other = api(director).get(
        f"/api/class-groups/{data['a'].pk}/report-card/", enrollment=data["josue"], output="html"
    )
    assert amani[0] == "TB" and amani[1:] == ["TB"] * (len(amani) - 1)
    assert {c["grade"] for c in other.context["conduct"] if c["kind"] == "period"} == {"TB"}
    assert all(c["grade"] == "" for c in page.context["conduct"] if c["kind"] != "period")


def test_another_school_cannot_read_or_correct_a_conduct_grade(api, other_school, data, master):
    other_master = MembershipFactory(school=other_school, roles=["discipline_master"]).user
    other = api(other_master, host="beta.localhost")
    body = {"term": str(data["p1"].pk), "grade": "B", "reason": "x"}
    assert other.put(grade_url(data), body).status_code == 404
    assert other.get(f"/api/discipline/enrollments/{data['amani']}/").status_code == 404

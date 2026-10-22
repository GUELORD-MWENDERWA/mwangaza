"""Calcul automatique de l'horaire (EDT.3a) sur un petit cas écrit à la main : 3 classes,
4 enseignants, grille proposée (7 heures du lundi au vendredi, récréations après la 3e et la 5e,
4 heures le samedi). Le juge est `checks.draft` : les mêmes contrôles qu'à la main."""

from collections import Counter

import pytest

from apps.academics.models import PRACTICAL
from apps.academics.tests.test_courses import classes
from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.timetable.models import Room, TeacherTimetableProfile, TimetableRun
from apps.timetable.tests.test_constraints import RULES, group, lock, new
from apps.timetable.tests.test_drafts import DRAFTS
from apps.timetable.tests.test_timetable import log, new_grid
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

RUNS = "/api/timetable/runs/"


def calculate(client, draft: dict, **extra):
    return client.post(
        RUNS, {"request_id": str(uuid7()), "timetable": draft["id"], "time_limit": 10, **extra}
    )


@pytest.fixture
def small(api, school, head):
    """Classe A : maths 5 h (au plus 2 h par jour), français 4 h, atelier de 6 h verrouillé le
    lundi de la 2e à la 7e heure. Classe B : maths, français, deux groupes en parallèle. Classe C :
    maths, anglais. Éducation physique de A et C ensemble (cours commun). M. Un n'est pas là le
    vendredi."""
    data = classes(school, head)
    with use_school(school):
        data["c"] = organisation.create_class_group(
            actor=head,
            academic_year=data["year"],
            level=data["a"].level,
            track=data["a"].track,
            section="C",
        )
        workshop_room = Room.objects.create(name="Atelier", kind="workshop")
    one, two, three, four = (
        MembershipFactory(school=school, roles=["teacher"]).user for _ in range(4)
    )
    with use_school(school):
        TeacherTimetableProfile.objects.create(teacher=one, unavailable=[{"weekday": 5}])
    client = api(head)
    new_grid(client)
    a, b, c = data["a"], data["b"], data["c"]
    courses = {
        "maths_a": new(a, "Mathématique", 5, teacher=one, max_per_day=2),
        "french_a": new(a, "Français", 4, teacher=two),
        "workshop": new(
            a,
            "Atelier",
            6,
            teacher=three,
            lesson_pattern="6",
            category=PRACTICAL,
            room_kind="workshop",
        ),
        "maths_b": new(b, "Mathématique", 5, teacher=one),
        "french_b": new(b, "Français", 4, teacher=two),
        "elec": new(b, "Électricité", 3, teacher=three),
        "electro": new(b, "Électronique", 3, teacher=four),
        "maths_c": new(c, "Mathématique", 4, teacher=one),
        "english_c": new(c, "Anglais", 3, teacher=four),
        "sport_a": new(a, "Éducation physique", 2, teacher=four),
        "sport_c": new(c, "Éducation physique", 2, teacher=four),
    }
    for body in (
        lock(courses["workshop"], 1, 2, 7, room=str(workshop_room.pk)),
        group("parallel_courses", courses["elec"], courses["electro"]),
        group("joint_courses", courses["sport_a"], courses["sport_c"]),
    ):
        assert client.post(RULES, body).status_code == 201
    draft = client.post(DRAFTS, {"name": "Brouillon"}).json()
    return {"client": client, "draft": draft, "teachers": (one, two, three, four), **courses}


def positions(state, course) -> list[tuple[int, int, int]]:
    return sorted(
        (entry["weekday"], entry["first"], entry["length"])
        for entry in state["entries"]
        if entry["course"] == str(course.pk)
    )


def test_calculation_places_everything_within_the_rules(small, school):
    client = small["client"]
    response = calculate(client, small["draft"])
    assert response.status_code == 202, response.json()
    run = response.json()
    assert run["status"] == "done" and run["blocking"] == [] and run["peak_mb"]
    state = client.get(f"{DRAFTS}{run['result']}/").json()
    # Aucun conflit (O1 à O7, maximum par jour, trous de classe), rien à placer.
    assert state["errors"] == 0 and state["left"] == [], state["issues"]
    assert not {issue["code"] for issue in state["issues"]} & {"class_gap", "room_missing"}
    # Le verrou n'a pas bougé ; 5 h de maths, jamais 3 le même jour ; M. Un jamais le vendredi.
    assert positions(state, small["workshop"]) == [(1, 2, 6)]
    per_day = Counter()
    for weekday, _first, length in positions(state, small["maths_a"]):
        per_day[weekday] += length
    assert sum(per_day.values()) == 5 and max(per_day.values()) <= 2
    one = [small[name] for name in ("maths_a", "maths_b", "maths_c")]
    assert all(weekday != 5 for course in one for weekday, _f, _l in positions(state, course))
    # Groupes en parallèle et cours commun : aux mêmes heures.
    assert positions(state, small["elec"]) == positions(state, small["electro"])
    assert positions(state, small["sport_a"]) == positions(state, small["sport_c"])
    # Le brouillon de départ ne change pas ; le nouveau est au journal.
    assert len(client.get(f"{DRAFTS}{small['draft']['id']}/").json()["entries"]) == 1
    [entry] = [e for e in log(school, Action.TIMETABLE_DRAFT_CREATED) if e.after.get("calculated")]
    assert entry.after["based_on"] == "Brouillon" and entry.after["lessons"] == len(
        state["entries"]
    )

    # Recalcul de la classe B seulement : A et C ne bougent pas, B reste complète.
    again = calculate(client, state, scope="class", target=str(small["maths_b"].class_group_id))
    assert again.status_code == 202 and again.json()["status"] == "done", again.json()
    second = client.get(f"{DRAFTS}{again.json()['result']}/").json()
    assert second["errors"] == 0 and second["left"] == []
    for name in ("maths_a", "french_a", "workshop", "maths_c", "english_c", "sport_a"):
        assert positions(second, small[name]) == positions(state, small[name])


def test_impossible_names_the_rule_that_blocks(small):
    client = small["client"]
    # Les maths seulement l'après-midi : 2 heures par jour du lundi au vendredi pour 14 h de M. Un.
    rule = client.post(
        RULES,
        {
            "kind": "course_part_of_day",
            "strength": "hard",
            "params": {"target": {"scope": "name", "value": "Mathématique"}, "part": "afternoon"},
        },
    ).json()
    run = calculate(client, small["draft"]).json()
    assert run["status"] == "infeasible" and run["result"] is None
    assert rule["id"] in {row.get("rule") for row in run["blocking"]}


def test_runs_rights_isolation_repeats_and_refusals(small, school, other_school, other_head, api):
    client, draft = small["client"], small["draft"]
    teacher = api(MembershipFactory(school=school, roles=["teacher"]).user)
    assert teacher.get(RUNS).status_code == 403
    assert calculate(teacher, draft).status_code == 403

    # La même demande renvoyée ne relance rien.
    body = {"request_id": str(uuid7()), "timetable": draft["id"], "time_limit": 10}
    first = client.post(RUNS, body)
    repeat = client.post(RUNS, body)
    assert (first.status_code, repeat.status_code) == (202, 200)
    assert repeat.json()["id"] == first.json()["id"]
    with use_school(school):
        assert TimetableRun.objects.count() == 1
    url = f"{RUNS}{first.json()['id']}/"
    assert client.post(f"{url}cancel/").json()["code"] == "run_finished"

    # L'école B ne voit, n'annule ni ne calcule rien de A.
    beta = api(other_head, host="beta.localhost")
    classes(other_school, other_head)
    assert beta.get(RUNS).json() == []
    assert beta.get(url).status_code == 404
    assert beta.post(f"{url}cancel/").status_code == 404
    assert calculate(beta, draft).status_code == 400

    # Un calcul à la fois par école ; on peut l'annuler.
    with use_school(school):
        waiting = TimetableRun.objects.create(
            request_id=uuid7(), timetable_id=draft["id"], created_by=small["teachers"][0]
        )
    assert calculate(client, draft).json()["code"] == "run_in_progress"
    assert client.post(f"{RUNS}{waiting.pk}/cancel/").json()["status"] == "cancelled"
    # Classe ou enseignant d'ailleurs : refusé.
    other = calculate(client, draft, scope="teacher", target=str(other_head.pk))
    assert other.json()["code"] == "unknown_target"
    # Contrôles en rouge (classe au-delà de sa grille) : pas de calcul.
    new(small["maths_c"].class_group, "Dessin", 40)
    refused = calculate(client, draft)
    assert refused.status_code == 409 and refused.json()["code"] == "checks_failed"

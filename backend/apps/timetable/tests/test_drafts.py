"""Brouillons de l'horaire (EDT.2a) : droits, isolation, journal, gestes refusés, conflits
recalculés par le serveur et « Annuler », sur un cas écrit à la main (grille proposée : 7 heures du
lundi au vendredi, récréations après la 3e et la 5e, 4 heures le samedi)."""

import pytest

from apps.academics.models import PRACTICAL
from apps.academics.tests.test_courses import classes
from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.timetable.tests.test_constraints import RULES, lock, new
from apps.timetable.tests.test_timetable import log, new_grid
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

DRAFTS = "/api/timetable/drafts/"
COURSES = "/api/timetable/courses/"


def place(course, weekday, first, length) -> dict:
    return {"course": str(course.pk), "weekday": weekday, "first": first, "length": length}


def codes(state) -> set[str]:
    return {issue["code"] for issue in state["issues"]}


def left(state, course) -> list[int]:
    return next((row["lengths"] for row in state["left"] if row["course"] == str(course.pk)), [])


def test_drafts_rights_isolation_and_journal(api, school, head, other_school, other_head):
    data = classes(school, head)
    theirs = classes(other_school, other_head)
    client = api(head)
    beta = api(other_head, host="beta.localhost")
    new_grid(client)
    new_grid(beta, "Grille Beta")
    workshop = new(data["a"], "Atelier", 6, lesson_pattern="6", category=PRACTICAL)
    maths = new(data["a"], "Mathématique", 5)
    their_course = new(theirs["a"], "Théâtre", 2)
    assert client.post(RULES, lock(workshop, 1, 2, 7)).status_code == 201
    teacher = api(MembershipFactory(school=school, roles=["teacher"]).user)
    assert teacher.get(DRAFTS).status_code == 403
    assert teacher.get(COURSES).status_code == 403
    assert teacher.post(DRAFTS, {"name": "Essai"}).status_code == 403

    # Un nouveau brouillon part des heures verrouillées des règles.
    created = client.post(DRAFTS, {"name": "Brouillon 1"})
    assert created.status_code == 201, created.json()
    state = created.json()
    [fixed] = state["entries"]
    position = (fixed["weekday"], fixed["first"], fixed["length"], fixed["locked"])
    assert (fixed["course"], position) == (str(workshop.pk), (1, 2, 6, True))
    assert left(state, workshop) == [] and left(state, maths) == [2, 2, 1]
    assert state["errors"] == 0 and not state["can_undo"]
    [entry] = log(school, Action.TIMETABLE_DRAFT_CREATED)
    assert entry.after == {"name": "Brouillon 1", "based_on": None, "lessons": 1}
    url = f"{DRAFTS}{state['id']}/"
    fixed_url = f"{url}entries/{fixed['id']}/"

    # L'école B ne voit ni ne touche rien de A, et inversement.
    assert beta.get(DRAFTS).json() == []
    assert {course["id"] for course in beta.get(COURSES).json()} == {str(their_course.pk)}
    assert beta.get(url).status_code == 404
    assert beta.delete(url).status_code == 404
    assert beta.post(f"{url}entries/", place(maths, 2, 1, 2)).status_code == 404
    assert beta.patch(fixed_url, {"locked": False}).status_code == 404
    assert beta.delete(fixed_url).status_code == 404
    assert beta.post(f"{url}undo/").status_code == 404
    mine = beta.post(DRAFTS, {"name": "Beta"}).json()
    assert beta.post(f"{DRAFTS}{mine['id']}/entries/", place(maths, 2, 1, 2)).json()["code"] == (
        "unknown_course"
    )
    assert (
        beta.post(
            f"{DRAFTS}{mine['id']}/swap/", {"entry": fixed["id"], "other": fixed["id"]}
        ).status_code
        == 404
    )
    assert client.get(f"{DRAFTS}{mine['id']}/").status_code == 404
    assert client.post(f"{url}entries/", place(their_course, 2, 1, 2)).json()["code"] == (
        "unknown_course"
    )
    assert client.post(DRAFTS, {"name": "Copie", "based_on": mine["id"]}).status_code == 400
    assert [row["name"] for row in client.get(DRAFTS).json()] == ["Brouillon 1"]

    # Verrou : journal, rien si rien ne change ; déverrouillé et déplacé, la règle n'est plus tenue.
    assert client.patch(fixed_url, {"locked": False}).status_code == 200
    assert client.patch(fixed_url, {"locked": False}).status_code == 200
    [entry] = log(school, Action.TIMETABLE_LOCK_CHANGED)
    assert (entry.before, entry.after, entry.entity_label) == (
        {"locked": True},
        {"locked": False},
        f"Atelier · {data['a'].name}",
    )
    moved = client.patch(fixed_url, {"weekday": 2, "first": 2}).json()
    assert "lock_missing" in codes(moved)

    # Copie : mêmes séances ; suppression : journal.
    copy = client.post(DRAFTS, {"name": "Copie", "based_on": state["id"]}).json()
    assert [(row["weekday"], row["locked"]) for row in copy["entries"]] == [(2, False)]
    assert client.delete(url).status_code == 204
    [entry] = log(school, Action.TIMETABLE_DRAFT_DELETED)
    assert entry.before == {"name": "Brouillon 1", "lessons": 1}


def test_gestures_conflicts_and_undo(api, school, head, django_assert_max_num_queries):
    data = classes(school, head)
    client = api(head)
    new_grid(client)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    maths = new(data["a"], "Mathématique", 5, teacher=teacher)  # séances 2 + 2 + 1
    french = new(data["b"], "Français", 2, teacher=teacher)  # 1 + 1
    lab = new(data["a"], "Laboratoire", 2, lesson_pattern="2", room_kind="lab")
    url = f"{DRAFTS}{client.post(DRAFTS, {'name': 'Essai'}).json()['id']}/"

    # Ce qui ne peut pas exister est refusé, sans rien écrire.
    for body, code in (
        (place(maths, 1, 3, 2), "crosses_break"),
        (place(maths, 1, 7, 2), "outside_grid"),
        (place(maths, 6, 4, 2), "outside_grid"),
        (place(maths, 1, 1, 3), "not_due"),
    ):
        refused = client.post(f"{url}entries/", body)
        assert (refused.status_code, refused.json()["code"]) == (400, code)
    assert client.get(url).json()["entries"] == []

    # Placer : un geste = une écriture, nombre de requêtes borné.
    with django_assert_max_num_queries(30):
        state = client.post(f"{url}entries/", place(maths, 1, 1, 2)).json()
    [first] = state["entries"]
    assert left(state, maths) == [2, 1] and state["can_undo"]
    load = next(row for row in state["classes"] if row["class_group"] == str(data["a"].pk))
    assert (load["placed"], load["due"]) == (2, 7)

    # O2 : le même enseignant lundi à la 2e heure dans l'autre classe ; déplacé, plus de conflit.
    state = client.post(f"{url}entries/", place(french, 1, 2, 1)).json()
    assert "same_teacher" in codes(state)
    first_url = f"{url}entries/{first['id']}/"
    state = client.patch(first_url, {"weekday": 2, "first": 1}).json()
    assert "same_teacher" not in codes(state)
    [mine] = [row for row in state["teachers"] if row["teacher"] == str(teacher.pk)]
    assert (mine["placed"], mine["due"]) == (3, 7)

    # Au plus 2 h de maths par jour ; trou dans la journée ; salle à choisir ; absence (O7).
    state = client.post(f"{url}entries/", place(maths, 2, 4, 2)).json()
    assert {"course_day_over", "class_gap"} <= codes(state)
    state = client.post(f"{url}entries/", place(lab, 3, 1, 2)).json()
    assert "room_missing" in codes(state)
    absent = {"max_week_hours": None, "max_day_hours": None, "unavailable": [{"weekday": 2}]}
    assert client.put(f"/api/timetable/teachers/{teacher.pk}/", absent).status_code == 200
    assert "entry_on_absence" in codes(client.get(url).json())

    # Échanger deux séances de même longueur ; un seul geste par requête.
    [second] = [row for row in state["entries"] if (row["weekday"], row["first"]) == (2, 4)]
    [lab_entry] = [row for row in state["entries"] if row["course"] == str(lab.pk)]
    state = client.post(f"{url}swap/", {"entry": second["id"], "other": lab_entry["id"]}).json()
    swapped = {row["id"]: (row["weekday"], row["first"]) for row in state["entries"]}
    assert (swapped[second["id"]], swapped[lab_entry["id"]]) == ((3, 1), (2, 4))
    assert client.patch(first_url, {"weekday": 3, "locked": True}).status_code == 400

    # Verrouillée : ne bouge, ne change de salle ni ne part.
    assert client.patch(first_url, {"locked": True}).status_code == 200
    for response in (
        client.patch(first_url, {"weekday": 4, "first": 1}),
        client.patch(first_url, {"room": None}),
        client.delete(first_url),
    ):
        assert (response.status_code, response.json()["code"]) == (409, "entry_locked")

    # Annuler : le verrou (journal), puis l'échange.
    state = client.post(f"{url}undo/").json()
    assert not next(row for row in state["entries"] if row["id"] == first["id"])["locked"]
    assert len(log(school, Action.TIMETABLE_LOCK_CHANGED)) == 2
    state = client.post(f"{url}undo/").json()
    swapped = {row["id"]: (row["weekday"], row["first"]) for row in state["entries"]}
    assert (swapped[second["id"]], swapped[lab_entry["id"]]) == ((2, 4), (3, 1))

    # Retirer revient dans « À placer » ; annuler la remet, avec le même identifiant.
    state = client.delete(first_url).json()
    assert sorted(left(state, maths)) == [1, 2]
    state = client.post(f"{url}undo/").json()
    assert first["id"] in {row["id"] for row in state["entries"]}

    # O4 : les heures du cours changent après le placement.
    with use_school(school):
        maths.weekly_hours = 2
        maths.save(update_fields=["weekly_hours"])
    assert "sessions_changed" in codes(client.get(url).json())
    while client.get(url).json()["can_undo"]:
        assert client.post(f"{url}undo/").status_code == 200
    assert client.get(url).json()["entries"] == []
    assert client.post(f"{url}undo/").json()["code"] == "nothing_to_undo"

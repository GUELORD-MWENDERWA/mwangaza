"""Paramètres de l'emploi du temps (EDT.1a) : grilles, cases, salles, grille et salle des classes,
règles générales ; droits, module, isolation entre écoles et journal."""

import pytest

from apps.academics.models import Course
from apps.academics.tests.test_courses import classes
from apps.accounts.modules import resolve
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import ClassGroup, School
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

GRIDS = "/api/timetable/grids/"
CLASSES = "/api/timetable/classes/"
ROOMS = "/api/timetable/rooms/"
RULES = "/api/timetable/rules/"


def new_grid(client, name="Grille principale", **extra) -> dict:
    response = client.post(
        GRIDS, {"name": name, "lesson_minutes": 50, "start_time": "07:30", **extra}
    )
    assert response.status_code == 201, response.json()
    return response.json()


def body(grid: dict, slots: list[dict] | None = None, **extra) -> dict:
    fields = ("weekday", "index", "kind", "start", "end")
    rows = grid["slots"] if slots is None else slots
    return {
        "name": grid["name"],
        "lesson_minutes": grid["lesson_minutes"],
        "start_time": grid["start_time"],
        "is_default": grid["is_default"],
        "slots": [{key: slot[key] for key in fields} for slot in rows],
        **extra,
    }


def log(school, action) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action=action))


def test_rights_module_and_isolation(api, school, head, other_school, other_head):
    data = classes(school, head)
    theirs = classes(other_school, other_head)
    beta = api(other_head, host="beta.localhost")
    their_grid = new_grid(beta, "Grille Beta")
    their_room = beta.post(ROOMS, {"name": "Atelier Beta", "kind": "workshop"}).json()

    alpha = api(head)
    assert alpha.get(GRIDS).json() == []
    assert alpha.get(ROOMS).json() == []
    assert {row["id"] for row in alpha.get(CLASSES).json()} == {
        str(data["a"].pk),
        str(data["b"].pk),
    }
    # Rien d'une autre école ne se lit ni ne se change, ni ne s'attache à une classe.
    assert alpha.put(f"{GRIDS}{their_grid['id']}/", body(their_grid)).status_code == 404
    assert alpha.delete(f"{GRIDS}{their_grid['id']}/").status_code == 404
    assert alpha.patch(f"{ROOMS}{their_room['id']}/", {"name": "X"}).status_code == 404
    assert alpha.patch(f"{CLASSES}{theirs['a'].pk}/", {"time_grid": None}).status_code == 404
    mine = f"{CLASSES}{data['a'].pk}/"
    assert alpha.patch(mine, {"time_grid": their_grid["id"]}).json()["code"] == "unknown_grid"
    assert alpha.patch(mine, {"home_room": their_room["id"]}).json()["code"] == "unknown_room"
    assert beta.get(RULES).json()["max_same_course_per_day"] == 2

    # Sans `timetable.manage` (enseignant, caissier) : refusé ; sans le module : refusé.
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    for url in (GRIDS, CLASSES, ROOMS, RULES):
        assert api(teacher).get(url).status_code == 403
    assert api(teacher).post(GRIDS, {}).status_code == 403
    assert (
        api(MembershipFactory(school=school, roles=["study_director"]).user).get(GRIDS).status_code
        == 200
    )
    School.objects.filter(pk=school.pk).update(modules=["students", "academics"])
    assert alpha.get(GRIDS).json()["code"] == "module_missing"


def test_modules_follow_their_chain():
    assert resolve(["timetable"]) == ["students", "academics", "timetable"]
    with pytest.raises(ValueError):
        resolve(["students", "timetable"], current=["students", "academics", "timetable"])


def test_proposed_week_then_saving_keeps_each_lesson(api, school, head):
    client = api(head)
    grid = new_grid(client)
    # Q16 : 5 jours de 7 heures, samedi de 4, récréations après la 3e et la 5e heure.
    assert (grid["is_default"], grid["lesson_count"]) == (True, 39)
    monday = [s for s in grid["slots"] if s["weekday"] == 1]
    assert [(s["start"], s["end"]) for s in monday[3:5]] == [
        ("10:00:00", "10:15:00"),
        ("10:15:00", "11:05:00"),
    ]
    assert [s["kind"] for s in grid["slots"] if s["weekday"] == 6].count("break") == 1

    # Récréation du vendredi portée à 30 min : les heures suivantes se décalent ; le samedi perd
    # sa récréation et sa 4e heure.
    friday_fourth = next(s for s in grid["slots"] if (s["weekday"], s["index"]) == (5, 4))
    shift = {
        "10:15:00": "10:30:00",
        "11:05:00": "11:20:00",
        "11:55:00": "12:10:00",
        "12:05:00": "12:20:00",
        "12:55:00": "13:10:00",
        "13:45:00": "14:00:00",
    }
    slots = []
    for slot in grid["slots"]:
        if slot["weekday"] == 6 and slot["start"] >= "10:00:00":
            continue
        if slot["weekday"] == 5:
            slot = {
                **slot,
                "start": shift.get(slot["start"], slot["start"]),
                "end": shift.get(slot["end"], slot["end"]),
            }
        slots.append(slot)
    saved = client.put(f"{GRIDS}{grid['id']}/", body(grid, slots)).json()
    assert saved["lesson_count"] == 38
    again = next(s for s in saved["slots"] if (s["weekday"], s["index"]) == (5, 4))
    assert (again["id"], again["start"]) == (friday_fourth["id"], "10:30:00")
    [created, changed] = sorted(log(school, "timetable.grid_changed"), key=lambda e: e.created_at)
    assert created.after["day1"] == "07:30-13:45 (7) 10:00-10:15, 11:55-12:05"
    assert set(changed.after) == {"day5", "day6"}


@pytest.mark.parametrize(
    ("change", "code"),
    [
        # Deux heures qui se chevauchent.
        (lambda s: s[1].update(start="08:00:00"), "bad_slots"),
        # Récréation en fin de journée.
        (
            lambda s: s.append(
                {
                    "weekday": 1,
                    "index": None,
                    "kind": "break",
                    "start": "08:20:00",
                    "end": "08:30:00",
                }
            ),
            "bad_slots",
        ),
        # Heures mal numérotées.
        (lambda s: s[1].update(index=3), "bad_slots"),
        # Aucune heure de cours.
        (lambda s: s.clear(), "no_lesson"),
    ],
)
def test_a_week_that_does_not_hold_is_refused(api, head, change, code):
    client = api(head)
    grid = new_grid(client)
    slots = [
        {"weekday": 1, "index": 1, "kind": "lesson", "start": "07:30:00", "end": "08:20:00"},
    ]
    slots.append(
        {"weekday": 1, "index": 2, "kind": "lesson", "start": "08:20:00", "end": "09:10:00"}
    )
    change(slots)
    response = client.put(f"{GRIDS}{grid['id']}/", body(grid, slots))
    assert (response.status_code, response.json()["code"]) == (400, code)


def test_one_default_grid_and_deleting_another(api, school, head):
    data = classes(school, head)
    client = api(head)
    main = new_grid(client)
    afternoon = new_grid(client, "Après-midi", start_time="12:30", lesson_minutes=45)
    assert afternoon["is_default"] is False
    assert client.put(f"{GRIDS}{main['id']}/", body(main, is_default=False)).json()["code"] == (
        "default_grid"
    )
    assert client.delete(f"{GRIDS}{main['id']}/").json()["code"] == "default_grid"
    assert (
        client.post(
            GRIDS, {"name": "après-MIDI", "lesson_minutes": 50, "start_time": "13:00"}
        ).json()["code"]
        == "grid_exists"
    )

    client.patch(f"{CLASSES}{data['b'].pk}/", {"time_grid": afternoon["id"]})
    # Après-midi devient la grille par défaut : l'autre ne l'est plus.
    client.put(f"{GRIDS}{afternoon['id']}/", body(afternoon, is_default=True))
    assert [(g["name"], g["is_default"], g["class_count"]) for g in client.get(GRIDS).json()] == [
        ("Après-midi", True, 1),
        ("Grille principale", False, 0),
    ]
    assert client.delete(f"{GRIDS}{main['id']}/").status_code == 204
    assert len(log(school, "timetable.grid_deleted")) == 1


def test_each_class_compares_its_taught_hours_with_its_grid(api, school, head):
    data = classes(school, head)
    client = api(head)
    new_grid(client)
    afternoon = new_grid(client, "Après-midi", start_time="12:30")
    with use_school(school):
        new = Course.objects.create
        new(class_group=data["a"], name="Physique", period_max=20, weekly_hours=4)
        new(class_group=data["a"], name="Atelier", period_max=100, weekly_hours=6)
        new(class_group=data["a"], name="Dessin", period_max=20, weekly_hours=3, is_taught=False)
        new(class_group=data["a"], name="Français", period_max=20)
    # Après-midi : seulement 2 heures le lundi.
    lessons = [
        {"weekday": 1, "index": 1, "kind": "lesson", "start": "12:30:00", "end": "13:20:00"},
        {"weekday": 1, "index": 2, "kind": "lesson", "start": "13:20:00", "end": "14:10:00"},
    ]
    client.put(f"{GRIDS}{afternoon['id']}/", body(afternoon, lessons))
    row = client.patch(f"{CLASSES}{data['b'].pk}/", {"time_grid": afternoon["id"]}).json()
    assert (row["capacity"], row["course_hours"]) == (2, 0)
    a = next(r for r in client.get(CLASSES).json() if r["id"] == str(data["a"].pk))
    assert (a["course_hours"], a["missing_hours"], a["capacity"], a["time_grid"]) == (
        10,
        1,
        39,
        None,
    )
    [entry] = log(school, "timetable.class_changed")
    assert entry.after == {"time_grid_id": afternoon["id"]}


def test_rooms_are_retired_never_deleted(api, school, head):
    data = classes(school, head)
    client = api(head)
    room = client.post(ROOMS, {"name": "Salle 3", "kind": "classroom", "capacity": 60}).json()
    assert client.post(ROOMS, {"name": "salle 3", "kind": "lab"}).json()["code"] == "room_exists"
    client.patch(f"{CLASSES}{data['a'].pk}/", {"home_room": room["id"]})
    [listed] = client.get(ROOMS).json()
    assert listed["classes"] == [data["a"].name]

    retired = client.patch(f"{ROOMS}{room['id']}/", {"is_active": False}).json()
    assert retired["is_active"] is False
    # Une classe qui l'avait la garde ; une autre ne peut plus la choisir.
    response = client.patch(f"{CLASSES}{data['b'].pk}/", {"home_room": room["id"]})
    assert response.json()["code"] == "room_retired"
    with use_school(school):
        assert str(ClassGroup.objects.get(pk=data["a"].pk).home_room_id) == room["id"]
    assert len(log(school, "timetable.room_changed")) == 2


def test_general_rules(api, school, head):
    client = api(head)
    rules = client.get(RULES).json()
    assert rules == {
        "max_same_course_per_day": 2,
        "teacher_max_day_hours": 6,
        "no_gaps": True,
        "main_courses_early": True,
    }
    assert client.put(RULES, {**rules, "max_same_course_per_day": 9}).status_code == 400
    assert client.put(RULES, {**rules, "no_gaps": False}).json()["no_gaps"] is False
    [entry] = log(school, "timetable.rules_changed")
    assert (entry.before, entry.after) == ({"no_gaps": True}, {"no_gaps": False})

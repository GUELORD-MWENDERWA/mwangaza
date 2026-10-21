"""Règles de l'emploi du temps (EDT.1c) : droits, isolation, schéma par kind, journal, groupes
disjoints, et contrôles 6 et 7 sur un cas écrit à la main."""

import pytest

from apps.academics.models import Course
from apps.academics.tests.test_courses import classes
from apps.accounts.models import Membership
from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.timetable.models import Room
from apps.timetable.tests.test_timetable import log, new_grid
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

RULES = "/api/timetable/constraints/"
CHOICES = "/api/timetable/constraints/choices/"
CHECKS = "/api/timetable/checks/"
TEACHERS = "/api/timetable/teachers/"


def new(group, name, hours, **fields) -> Course:
    with use_school(group.school):
        return Course.objects.create(
            class_group=group, name=name, period_max=20, weekly_hours=hours, **fields
        )


def lock(course, weekday, first, last, **params) -> dict:
    return {
        "kind": "fixed_lesson",
        "params": {"course": str(course.pk), "weekday": weekday, "first": first, "last": last}
        | params,
    }


def group(kind, *courses) -> dict:
    return {"kind": kind, "params": {"courses": [str(course.pk) for course in courses]}}


def test_rules_rights_isolation_schema_and_journal(api, school, head, other_school, other_head):
    data = classes(school, head)
    theirs = classes(other_school, other_head)
    new(theirs["a"], "Théâtre", 2)
    workshop = new(data["a"], "Atelier", 6, lesson_pattern="6")
    client = api(head)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    for url in (RULES, CHOICES):
        assert api(teacher).get(url).status_code == 403
    assert api(teacher).post(RULES, lock(workshop, 1, 2, 7)).status_code == 403

    created = client.post(RULES, lock(workshop, 1, 2, 7))
    assert created.status_code == 201, created.json()
    rule = created.json()
    assert (rule["strength"], rule["active"], rule["source"]) == ("hard", True, "manual")
    assert rule["params"]["room"] is None
    [entry] = log(school, Action.TIMETABLE_RULE_CHANGED)
    assert entry.after["params"]["first"] == 2

    # Le schéma du kind décide : force permise, champs, cours de l'école et de l'année.
    def refused(body) -> dict:
        response = client.post(RULES, body)
        assert response.status_code == 400, response.json()
        return response.json()["fields"]

    assert "strength" in refused(lock(workshop, 1, 2, 7) | {"strength": "soft"})
    assert "params.last" in refused(lock(workshop, 1, 5, 3))
    assert "params.weekday" in refused(lock(workshop, 8, 1, 1))
    assert "kind" in refused({"kind": "teacher_mood", "params": {}})
    compact = {"kind": "teacher_compact", "params": {}, "strength": "hard"}
    assert "strength" in refused(compact)
    no_where = {"kind": "course_not_slot", "params": {"target": {"scope": "name", "value": "EPS"}}}
    assert "params.lessons" in refused(no_where)
    every = {
        "kind": "course_part_of_day",
        "params": {"target": {"scope": "all"}, "part": "morning"},
    }
    assert "params.target" in refused(every)
    wish = client.post(RULES, {**compact, "strength": "soft"}).json()
    assert (wish["strength"], wish["weight"]) == ("soft", 2)

    # Une autre école ne lit, ne change ni ne supprime rien, et ne vise pas nos cours.
    beta = api(other_head, host="beta.localhost")
    assert beta.get(RULES).json() == []
    assert [course["name"] for course in beta.get(CHOICES).json()["courses"]] == ["Théâtre"]
    url = f"{RULES}{rule['id']}/"
    assert beta.put(url, lock(workshop, 2, 1, 6)).status_code == 404
    assert beta.delete(url).status_code == 404
    assert "params.course" in beta.post(RULES, lock(workshop, 1, 2, 7)).json()["fields"]

    changed = client.put(url, lock(workshop, 1, 1, 6) | {"active": False})
    assert changed.json()["active"] is False
    [edit] = [item for item in log(school, Action.TIMETABLE_RULE_CHANGED) if item.before]
    assert edit.before == {"params": rule["params"], "active": True}
    assert client.delete(url).status_code == 204
    [deleted] = log(school, Action.TIMETABLE_RULE_DELETED)
    assert deleted.before["kind"] == "fixed_lesson"
    assert [item["id"] for item in client.get(RULES).json()] == [wish["id"]]
    assert log(other_school, Action.TIMETABLE_RULE_CHANGED) == []


def test_groups_hold_together_and_count_once(api, school, head):
    data = classes(school, head)
    a, b = data["a"], data["b"]
    client = api(head)
    new_grid(client)  # 39 places
    shared = MembershipFactory(school=school, roles=["teacher"]).user
    other = MembershipFactory(school=school, roles=["teacher"]).user
    client.put(
        f"{TEACHERS}{shared.pk}/", {"max_week_hours": 4, "max_day_hours": None, "unavailable": []}
    )
    mechanics = new(a, "Mécanique", 7)
    electricity = new(a, "Électricité", 7, teacher=other)
    new(a, "Cours généraux", 28)
    religion_a = new(a, "Religion", 3, teacher=shared)
    religion_b = new(b, "Religion", 3, teacher=shared)

    def codes() -> set[tuple[str, str]]:
        return {(item["code"], item["subject"]) for item in client.get(CHECKS).json()["issues"]}

    # Sans les groupes : 45 h pour 39 places, 6 h pour 4 au plus.
    assert {("class_overloaded", a.name), ("teacher_over_max", str(shared))} <= codes()
    refused = client.post(RULES, group("parallel_courses", mechanics, religion_b))
    assert "params.courses" in refused.json()["fields"]
    refused = client.post(RULES, group("joint_courses", religion_a, electricity))
    assert "params.courses" in refused.json()["fields"]
    assert client.post(RULES, group("parallel_courses", mechanics, electricity)).status_code == 201
    assert client.post(RULES, group("joint_courses", religion_a, religion_b)).status_code == 201
    taken = client.post(RULES, group("parallel_courses", religion_a, mechanics))
    assert (taken.status_code, taken.json()["code"]) == (409, "course_grouped")
    # Comptés une fois : 38 h, 3 h.
    found = codes()
    assert ("class_overloaded", a.name) not in found
    assert ("teacher_over_max", str(shared)) not in found
    assert client.get(CHECKS).json()["rules"] == 2

    # Après coup, les groupes ne tiennent plus : le contrôle 7 le dit.
    with use_school(school):
        Course.objects.filter(pk=mechanics.pk).update(teacher=other, weekly_hours=6)
        Course.objects.filter(pk=religion_b.pk).update(teacher=None)
    found = codes()
    assert {
        ("parallel_same_teacher", a.name),
        ("group_hours_differ", a.name),
        ("joint_teachers_differ", "Religion"),
    } <= found


def test_locks_in_conflict_and_rules_that_contradict(api, school, head):
    data = classes(school, head)
    a, b = data["a"], data["b"]
    client = api(head)
    new_grid(client)  # 5 jours de 7 heures, samedi de 4 ; récréations après la 3e et la 5e
    absent = MembershipFactory(school=school, roles=["teacher"]).user
    busy = MembershipFactory(school=school, roles=["teacher"]).user
    gone = MembershipFactory(school=school, roles=["teacher"]).user
    client.put(
        f"{TEACHERS}{absent.pk}/",
        {"max_week_hours": None, "max_day_hours": None, "unavailable": [{"weekday": 3}]},
    )
    with use_school(school):
        lab = Room.objects.create(name="Laboratoire", kind="lab")
    workshop = new(a, "Atelier", 6, lesson_pattern="6", category="practical")
    maths = new(a, "Maths", 4, lesson_pattern="2+2", teacher=absent)
    french = new(a, "Français", 2, teacher=busy)
    physics = new(b, "Physique", 2, teacher=busy)
    chemistry = new(b, "Chimie", 2, lesson_pattern="2", room=lab)
    rules = [
        lock(workshop, 1, 2, 7),  # passe les deux récréations : un atelier le peut
        lock(maths, 6, 3, 6),  # le samedi n'a que 4 heures
        lock(maths, 2, 3, 4),  # passe la récréation de 3e heure
        lock(maths, 3, 1, 3),  # 3 h : pas une séance de 2 + 2, et l'enseignant est absent
        lock(french, 1, 1, 2),  # même classe que l'atelier, le lundi
        lock(physics, 1, 1, 1),  # même enseignant que le français
        lock(chemistry, 4, 1, 2, room=str(lab.pk)),  # laboratoire fermé le jeudi
        {"kind": "room_unavailable", "params": {"room": str(lab.pk), "weekday": 4}},
        {
            "kind": "course_not_slot",
            "strength": "hard",
            "params": {"target": {"scope": "name", "value": "français"}, "lessons": [1]},
        },
        {
            "kind": "course_not_slot",
            "params": {"target": {"scope": "name", "value": "Latin"}, "weekday": 5},
        },
        {"kind": "teacher_free_day", "params": {"teacher": str(gone.pk), "weekday": 3}},
    ]
    ids = []
    for body in rules:
        response = client.post(RULES, body)
        assert response.status_code == 201, response.json()
        ids.append(response.json()["id"])
    Membership.objects.filter(user=gone, school=school).update(is_active=False)

    report = client.get(CHECKS).json()
    found = {(item["code"], item["rule"]): item for item in report["issues"]}

    def issue(code, position) -> dict:
        return found[(code, ids[position])]

    assert issue("lock_outside_grid", 1)["values"]["lessons"] == 4
    assert issue("lock_crosses_break", 2)["check"] == 7
    values = issue("lock_not_a_session", 3)["values"]
    assert (values["length"], values["sessions"]) == (3, "2+2")
    assert issue("lock_on_absence", 3)["values"]["teacher"] == str(absent)
    assert issue("locks_same_class", 4)["subject"] == a.name
    assert issue("locks_same_teacher", 5)["subject"] == str(busy)
    assert issue("lock_on_closed_room", 6)["values"]["room"] == "Laboratoire"
    assert issue("lock_against_rule", 4)["values"]["other"] == "course_not_slot"
    assert found[("rule_without_object", ids[9])]["level"] == "warning"
    assert found[("rule_without_object", ids[10])]["subject"] == "teacher_free_day"
    assert ("lock_outside_grid", ids[0]) not in found
    assert not any(key[1] == ids[0] for key in found)
    assert report["rules"] == len(rules)

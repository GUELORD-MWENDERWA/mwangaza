"""Placement des cours, disponibilités des enseignants et contrôles avant le calcul (EDT.1b) :
droits, module, isolation entre écoles, journal, et un cas pour chaque contrôle."""

import pytest

from apps.academics.models import Course
from apps.academics.tests.test_courses import classes
from apps.accounts.models import Membership
from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.timetable.models import Room
from apps.timetable.tests.test_timetable import ROOMS, log, new_grid
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

TEACHERS = "/api/timetable/teachers/"
CHECKS = "/api/timetable/checks/"


def courses_url(group) -> str:
    return f"/api/class-groups/{group.pk}/courses/"


def course(name, hours, **placement) -> dict:
    row = {"name": name, "period_max": 20, "weekly_hours": hours}
    if placement:
        row["placement"] = {"lesson_pattern": "", "room_id": None, **placement}
    return row


def test_placement_goes_with_the_grid_and_needs_the_timetable(api, school, head, other_head):
    data = classes(school, head)
    client = api(head)
    lab = client.post(ROOMS, {"name": "Laboratoire", "kind": "lab"}).json()
    beta = api(other_head, host="beta.localhost")
    theirs = beta.post(ROOMS, {"name": "Atelier Beta", "kind": "workshop"}).json()
    url = courses_url(data["a"])

    def put(*rows):
        return client.put(url, {"courses": list(rows)})

    # Les séances font les heures du cours ; une salle ou un type ; une salle de l'école.
    refused = {
        "pattern_hours": course("Maths", 5, lesson_pattern="2+2"),
        "bad_pattern": course("Maths", 5, lesson_pattern="2,3"),
        "below_longest_lesson": course("Maths", 5, lesson_pattern="3+2", max_per_day=2),
        "room_or_kind": course("Maths", 5, room_id=lab["id"], room_kind="lab"),
        "unknown_room": course("Maths", 5, room_id=theirs["id"]),
    }
    for code, row in refused.items():
        response = put(row)
        assert response.status_code == 400, code
        assert code in str(response.json()), code

    saved = put(
        course("Maths", 5, lesson_pattern="2 + 2 + 1", max_per_day=2, preferred_part="morning"),
        course("Chimie", 2, room_id=lab["id"]),
    ).json()
    assert saved[0]["placement"]["lesson_pattern"] == "2+2+1"
    assert saved[1]["placement"]["room"] == lab["id"]
    [entry] = log(school, "courses.changed")
    assert entry.after["courses"][0]["placement"] == {
        "lesson_pattern": "2+2+1",
        "max_per_day": 2,
        "preferred_part": "morning",
    }

    # Sans le module : le placement envoyé est refusé, la grille sans placement le garde ; des
    # heures changées font revenir des séances calculées.
    School.objects.filter(pk=school.pk).update(modules=["students", "academics"])
    assert put(course("Maths", 5, lesson_pattern="5")).json()["code"] == "placement_forbidden"
    kept = put(
        {**course("Maths", 4), "id": saved[0]["id"]},
        {**course("Chimie", 2), "id": saved[1]["id"]},
    ).json()
    assert kept[0]["placement"]["lesson_pattern"] == ""
    assert kept[0]["placement"]["max_per_day"] == 2
    assert kept[1]["placement"]["room"] == lab["id"]


def test_teacher_availability_rights_isolation_and_journal(
    api, school, head, other_school, other_head
):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    stranger = MembershipFactory(school=other_school, roles=["teacher"]).user
    client = api(head)
    body = {
        "max_week_hours": 24,
        "max_day_hours": None,
        "unavailable": [
            {"weekday": 2, "start": "07:30", "end": "10:00"},
            {"weekday": 5, "start": "07:30", "end": "08:20"},
            {"weekday": 5},
        ],
    }
    saved = client.put(f"{TEACHERS}{teacher.pk}/", body)
    assert saved.status_code == 200, saved.json()
    # La journée entière du vendredi couvre sa plage.
    assert saved.json()["unavailable"] == [
        {"weekday": 2, "start": "07:30", "end": "10:00"},
        {"weekday": 5},
    ]
    bad = {**body, "unavailable": [{"weekday": 1, "start": "10:00", "end": "09:00"}]}
    assert client.put(f"{TEACHERS}{teacher.pk}/", bad).status_code == 400

    # Jamais le personnel d'une autre école ; jamais sans `timetable.manage`.
    assert client.put(f"{TEACHERS}{stranger.pk}/", body).status_code == 404
    beta = api(other_head, host="beta.localhost")
    assert beta.get(TEACHERS).json() == []
    assert beta.put(f"{TEACHERS}{teacher.pk}/", body).status_code == 404
    assert api(teacher).get(TEACHERS).status_code == 403
    assert api(teacher).put(f"{TEACHERS}{teacher.pk}/", body).status_code == 403
    assert api(teacher).get(CHECKS).status_code == 403
    [entry] = log(school, "timetable.teacher_changed")
    assert entry.after["max_week_hours"] == 24


def test_each_check_names_what_how_much_and_where(api, school, head, other_head):
    data = classes(school, head)
    a, b = data["a"], data["b"]
    client = api(head)
    new_grid(client)  # 5 jours de 7 heures et le samedi de 4 : 39 places
    busy = MembershipFactory(school=school, roles=["teacher"]).user
    absent = MembershipFactory(school=school, roles=["teacher"]).user
    tired = MembershipFactory(school=school, roles=["teacher"]).user
    gone = MembershipFactory(school=school, roles=["teacher"]).user
    every_day = [{"weekday": day} for day in range(1, 6)]
    for user, profile in (
        (busy, {"max_week_hours": 2, "max_day_hours": None, "unavailable": []}),
        (absent, {"max_week_hours": None, "max_day_hours": None, "unavailable": every_day}),
        (tired, {"max_week_hours": None, "max_day_hours": 1, "unavailable": []}),
    ):
        client.put(f"{TEACHERS}{user.pk}/", profile)
    with use_school(school):
        workshop = Room.objects.create(name="Atelier", kind="workshop")
        old = Room.objects.create(name="Ancien magasin", is_active=False)
        new = Course.objects.create
        new(class_group=a, name="Atelier", period_max=100, weekly_hours=40, room=workshop)
        new(class_group=b, name="Maths", period_max=20, weekly_hours=3, teacher=busy)
        new(class_group=b, name="Français", period_max=20, weekly_hours=5, teacher=absent)
        new(class_group=b, name="Dessin", period_max=20, weekly_hours=7, teacher=tired)
        new(
            class_group=b,
            name="Physique",
            period_max=20,
            weekly_hours=7,
            lesson_pattern="1+1+1+1+1+1+1",
            max_per_day=1,
        )
        new(class_group=b, name="Électricité", period_max=20, weekly_hours=6, lesson_pattern="6")
        new(class_group=b, name="Chimie", period_max=20, weekly_hours=2, room_kind="lab")
        new(class_group=b, name="Techno", period_max=20, weekly_hours=1, room=old)
        new(class_group=b, name="Histoire", period_max=20, weekly_hours=2, teacher=gone)
        new(class_group=b, name="Religion", period_max=10)
    Membership.objects.filter(user=gone, school=school).update(is_active=False)

    report = client.get(CHECKS).json()
    found = {(issue["code"], issue["subject"]): issue for issue in report["issues"]}

    def values(code, subject):
        return found[(code, subject)]["values"]

    assert values("class_overloaded", a.name) == {"hours": 40, "capacity": 39}
    assert found[("class_overloaded", a.name)]["class_group"] == str(a.pk)
    assert values("teacher_over_max", str(busy)) == {"hours": 3, "max": 2}
    assert values("teacher_over_free", str(absent)) == {"hours": 5, "free": 4}
    assert values("teacher_over_days", str(tired)) == {"hours": 7, "possible": 6, "per_day": 1}
    assert values("course_spread", "Physique")["possible"] == 6
    # Récréations après la 3e et la 5e heure : 3 heures d'affilée au plus.
    assert values("lesson_too_long", "Électricité")["longest"] == 3
    assert values("room_overloaded", "Atelier") == {"hours": 40, "slots": 39}
    assert values("room_kind_missing", "lab") == {"hours": 2}
    assert values("room_retired", "Ancien magasin")["names"] == "Techno"
    assert values("teacher_left", str(gone))["hours"] == 2
    assert found[("no_hours", b.name)]["level"] == "warning"
    assert values("no_teacher", b.name)["count"] == 5
    assert report["issues"][0]["level"] == "error"
    assert report["issues"][-1]["level"] == "warning"
    assert (report["errors"], report["warnings"]) == (12, 3)

    # Une autre école ne voit rien de tout cela.
    beta = api(other_head, host="beta.localhost")
    assert beta.get(CHECKS).json()["issues"] == []

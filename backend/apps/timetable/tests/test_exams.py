"""Horaire des interrogations et des examens (EDT.5a) : droits, isolation, chaque contrôle,
publication refusée avec du rouge, horaire publié figé, journal."""

from datetime import date

import pytest

from apps.academics.tests.test_courses import classes
from apps.accounts.models import Role
from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.schools.models import Term
from apps.timetable.models import Room, TeacherTimetableProfile
from apps.timetable.tests.test_constraints import new
from apps.timetable.tests.test_timetable import log
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

EXAMS = "/api/timetable/exams/"


def period(school, year) -> Term:
    with use_school(school):
        term = Term.objects.filter(academic_year=year, kind=Term.Kind.PERIOD).first()
        term.starts_on, term.ends_on = date(2026, 9, 1), date(2026, 11, 6)
        term.save()
        return term


def sitting(course, day="2026-10-12", start="08:00", end="10:00", **extra) -> dict:
    return {
        "course": str(course.pk),
        "kind": "exam",
        "date": day,
        "start": start,
        "end": end,
    } | extra


def codes(state) -> list[str]:
    return [issue["code"] for issue in state["issues"]]


def test_rights_isolation_publication_and_journal(api, school, head, other_school, other_head):
    data = classes(school, head)
    theirs = classes(other_school, other_head)
    term, their_term = period(school, data["year"]), period(other_school, theirs["year"])
    maths = new(data["a"], "Mathématique", 4)
    client, beta = api(head), api(other_head, host="beta.localhost")
    url = f"{EXAMS}{term.pk}/"

    # Droits : un enseignant ne règle rien ; régler n'est pas publier.
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(teacher).get(url).status_code == 403
    with use_school(school):
        planner = Role.objects.create(name="Horaire", permissions=["timetable.manage"])
    manager = api(MembershipFactory(school=school, roles=[planner]).user)

    # L'école B ne lit, n'écrit ni ne publie rien de A ; ni ne place un cours de A dans sa période.
    assert beta.get(url).status_code == 404
    assert beta.post(url, sitting(maths)).status_code == 404
    assert beta.post(f"{EXAMS}{their_term.pk}/", sitting(maths)).status_code == 400

    # Vide : rien à publier. Un geste crée l'horaire en brouillon ; le journal garde l'avant/après.
    assert manager.post(f"{url}publish/").status_code == 403
    assert client.post(f"{url}publish/").json()["code"] == "exam_timetable_empty"
    created = manager.post(url, sitting(maths))
    assert created.status_code == 201, created.json()
    sitting_url = f"{EXAMS}sittings/{created.json()['id']}/"
    assert beta.patch(sitting_url, {"start": "09:00"}).status_code == 404
    assert beta.delete(sitting_url).status_code == 404
    assert manager.patch(sitting_url, {"start": "09:00"}).status_code == 200
    [first, second] = log(school, Action.EXAM_SITTING_CHANGED)
    assert (second.before or first.before)["start"] == "08:00"
    assert client.post(url, sitting(maths, end="07:00")).status_code == 400

    # Publié : figé, rouvrir demande le droit de publier et se retrouve au journal.
    published = client.post(f"{url}publish/")
    assert (published.status_code, published.json()["status"]) == (200, "published")
    assert (
        client.patch(sitting_url, {"start": "08:00"}).json()["code"] == "exam_timetable_published"
    )
    assert client.post(url, sitting(maths)).status_code == 409
    assert manager.delete(f"{url}publish/").status_code == 403
    assert client.delete(f"{url}publish/").json()["status"] == "draft"
    assert client.delete(sitting_url).status_code == 204
    assert len(log(school, Action.EXAM_TIMETABLE_PUBLISHED)) == 1
    assert len(log(school, Action.EXAM_TIMETABLE_REOPENED)) == 1
    assert len(log(school, Action.EXAM_SITTING_DELETED)) == 1


def test_each_check_and_publication_refused_with_red(api, school, head):
    data = classes(school, head)
    term = period(school, data["year"])
    maths = new(data["a"], "Mathématique", 4)
    french = new(data["a"], "Français", 4)
    physics = new(data["b"], "Physique", 4)
    client = api(head)
    url = f"{EXAMS}{term.pk}/"
    boss = MembershipFactory(school=school, roles=["teacher"]).user
    with use_school(school):
        room = Room.objects.create(name="Salle 1", kind="classroom")
        TeacherTimetableProfile.objects.create(
            teacher=boss,
            unavailable=[{"weekday": 1}],  # lundi 12 octobre 2026
        )

    # Une classe, deux épreuves qui se chevauchent ; mais bout à bout (11 h) : permis.
    client.post(url, sitting(maths))
    client.post(url, sitting(french, start="09:00", end="11:00"))
    client.post(url, sitting(french, start="11:00", end="12:00"))
    # Même surveillant et même salle pour deux classes à la même heure.
    body = {"room": str(room.pk), "invigilator": str(boss.pk)}
    client.post(url, sitting(physics, **body))
    state = client.post(url, sitting(physics, start="09:30", **body)).json()
    state = client.get(url).json()
    found = codes(state)
    assert found.count("class_overlap") == 2  # maths/français 9 h, physique/physique 9 h 30
    assert "invigilator_overlap" in found and "room_overlap" in found
    assert "invigilator_unavailable" in found  # le lundi est un jour d'absence
    assert all(i["level"] == "error" for i in state["issues"][: state["errors"]])

    # Hors de la période : rouge ; la publication reste refusée tant qu'il y a du rouge.
    client.post(url, sitting(maths, day="2026-12-01", start="14:00", end="15:00"))
    assert "outside_term" in codes(client.get(url).json())
    assert client.post(f"{url}publish/").json()["code"] == "publish_conflicts"
    assert not log(school, Action.EXAM_TIMETABLE_PUBLISHED)

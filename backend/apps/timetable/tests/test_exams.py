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


def test_published_exams_are_read_printed_and_announced(
    api, school, head, other_school, other_head
):
    """EDT.5b : rien avant la publication ; puis l'enseignant (ses cours), le surveillant, le
    titulaire et le parent (sans surveillant) lisent les épreuves ; une notification chacun ;
    impression par classe et générale, pour qui règle l'horaire de son école seulement."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.notifications.models import Notification
    from apps.portal.tests.test_access import activate, portal
    from apps.portal.tests.test_families import family_of
    from apps.schools.models import ClassGroup
    from apps.students.tests.conftest import enrolled

    data = classes(school, head)
    today = timezone.localdate()
    with use_school(school):
        term = Term.objects.filter(academic_year=data["year"], kind=Term.Kind.PERIOD).first()
        term.starts_on, term.ends_on = today, today + timedelta(days=30)
        term.save()
    day = (today + timedelta(days=7)).isoformat()
    teacher, watcher, titular = (
        MembershipFactory(school=school, roles=["teacher"]).user for _ in range(3)
    )
    with use_school(school):
        ClassGroup.objects.filter(pk=data["a"].pk).update(homeroom_teacher=titular)
    maths = new(data["a"], "Mathématique", 4, teacher=teacher)
    french = new(data["b"], "Français", 4)
    client, url = api(head), f"{EXAMS}{term.pk}/"
    client.post(url, sitting(maths, day=day, invigilator=str(watcher.pk)))
    client.post(url, sitting(french, day=day))
    child = enrolled(school, head, data["a"])
    with use_school(school):
        enrollment = child.enrollments.get()
    parent = portal()
    activate(parent, family_of(school, enrollment).code)
    child_url = f"/api/portal/children/{child.pk}/timetable/"

    # Brouillon : personne ne le voit.
    MINE = "/api/timetable/mine/"
    assert api(teacher).get(MINE).json()["exams"] == []
    assert parent.get(child_url).json()["exams"] == []

    assert client.post(f"{url}publish/").status_code == 200
    with use_school(school):
        told = sorted(
            (n.user_id, n.app)
            for n in Notification.objects.filter(kind=Notification.Kind.TIMETABLE_PUBLISHED)
        )
    # L'enseignant, le surveillant, le parent de la classe A ; pas l'auteur.
    assert [user for user, app in told if app == "gestion"] == sorted([teacher.pk, watcher.pk])
    assert [app for _user, app in told].count("portail") == 1

    def exams(rows) -> list[tuple]:
        return [(x["course"], x["class_group"], x["invigilating"]) for x in rows]

    assert exams(api(teacher).get(MINE).json()["exams"]) == [
        ("Mathématique", data["a"].name, False)
    ]
    assert exams(api(watcher).get(MINE).json()["exams"]) == [("Mathématique", data["a"].name, True)]
    homeroom = api(titular).get(MINE).json()["homeroom"]
    assert [x["course"] for x in homeroom["exams"]] == ["Mathématique"]
    seen = parent.get(child_url).json()["exams"]
    assert [(x["course"], x["invigilator"]) for x in seen] == [("Mathématique", "")]

    # Impression : par classe (une page chacune), générale ; droits et isolation.
    page = client.get(f"{url}print/?kind=class&output=html")
    assert page.status_code == 200
    html = page.content.decode()
    assert data["a"].name in html and data["b"].name in html and "Mathématique" in html
    general = client.get(f"{url}print/?kind=general&output=html&subject={data['a'].pk}")
    assert "Français" not in general.content.decode()
    assert api(teacher).get(f"{url}print/?output=html").status_code == 403
    assert api(other_head, host="beta.localhost").get(f"{url}print/").status_code == 404

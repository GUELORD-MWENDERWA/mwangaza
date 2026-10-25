"""Lecture de l'horaire publié (EDT.4b) : « Mon horaire » de l'enseignant, horaire de la classe
d'un enfant sur le Portail, notification de chaque personne touchée ; jamais un brouillon, jamais
l'horaire d'une autre école ni d'une autre famille."""

import pytest

from apps.academics.tests.test_courses import classes
from apps.core.tenancy import use_school
from apps.notifications.models import Notification
from apps.portal.tests.test_access import activate, new_family, portal
from apps.portal.tests.test_families import family_of
from apps.schools.models import ClassGroup, School
from apps.students import services as students
from apps.students.tests.conftest import enrolled
from apps.timetable.tests.test_constraints import new
from apps.timetable.tests.test_drafts import DRAFTS, place
from apps.timetable.tests.test_timetable import new_grid
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

MINE = "/api/timetable/mine/"


def publish(client, lessons, valid_from="2026-10-26", based_on=None) -> dict:
    """Un brouillon (copié de `based_on`), ses séances `(cours, jour, heure, longueur)` placées,
    puis publié."""
    body = {"name": f"Horaire du {valid_from}"} | ({"based_on": based_on} if based_on else {})
    draft = client.post(DRAFTS, body).json()
    url = f"{DRAFTS}{draft['id']}/"
    for course, weekday, first, length in lessons:
        placed = client.post(f"{url}entries/", place(course, weekday, first, length))
        assert placed.status_code == 201
    published = client.post(f"{url}publish/", {"valid_from": valid_from})
    assert published.status_code == 200, published.json()
    return published.json()


def rows(data) -> list[tuple]:
    return [(x["weekday"], x["start"], x["end"], x["course"], x["class_group"]) for x in data]


def test_my_timetable_and_the_childs_only_from_the_published_version(
    api, school, head, other_school, other_head
):
    data = classes(school, head)
    classes(other_school, other_head)
    client = api(head)
    beta = api(other_head, host="beta.localhost")
    new_grid(client)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    titular = MembershipFactory(school=school, roles=["teacher"]).user
    with use_school(school):
        ClassGroup.objects.filter(pk=data["a"].pk).update(homeroom_teacher=titular)
    maths = new(data["a"], "Mathématique", 4, teacher=teacher)  # séances 2 + 2
    french = new(data["b"], "Français", 1, teacher=teacher)
    english = new(data["a"], "Anglais", 1)
    mine = api(teacher)

    # Rien de publié : vide, même avec un brouillon.
    client.post(DRAFTS, {"name": "Brouillon"})
    assert mine.get(MINE).json() == {"timetable": None, "lessons": [], "homeroom": None}

    published = publish(client, [(maths, 1, 1, 2), (french, 2, 1, 1), (english, 1, 3, 1)])
    page = mine.get(MINE).json()
    assert page["timetable"]["valid_from"] == "2026-10-26"
    # Ses séances seulement, avec début et fin d'après la grille (heures de 50 min dès 7:30).
    assert rows(page["lessons"]) == [
        (1, "07:30", "09:10", "Mathématique", data["a"].name),
        (2, "07:30", "08:20", "Français", data["b"].name),
    ]
    assert page["homeroom"] is None
    # Le titulaire voit sa classe (tous ses cours), pas l'autre.
    homeroom = api(titular).get(MINE).json()["homeroom"]
    assert homeroom["class_group"] == data["a"].name
    assert [x["course"] for x in homeroom["lessons"]] == ["Mathématique", "Anglais"]
    assert homeroom["lessons"][0]["teacher"] == teacher.get_full_name()

    # Un nouveau brouillon qui déplace l'heure ne change rien tant qu'il n'est pas publié.
    later = client.post(DRAFTS, {"name": "Suite", "based_on": published["id"]}).json()
    entry = next(e for e in later["entries"] if e["course"] == str(french.pk))
    client.patch(f"{DRAFTS}{later['id']}/entries/{entry['id']}/", {"weekday": 3})
    assert rows(mine.get(MINE).json()["lessons"])[1][0] == 2

    # L'école B ne voit rien de A ; un compte de A n'entre pas dans B ; module coupé : 403.
    assert beta.get(MINE).json() == {"timetable": None, "lessons": [], "homeroom": None}
    assert api(teacher, host="beta.localhost").get(MINE).status_code == 403
    modules = school.modules
    School.objects.filter(pk=school.pk).update(modules=["students", "academics"])
    assert mine.get(MINE).json()["code"] == "module_missing"
    School.objects.filter(pk=school.pk).update(modules=modules)

    # Portail : la classe de l'enfant seulement ; un autre parent (autre école) : 404.
    child = enrolled(school, head, data["a"])
    with use_school(school):
        enrollment = child.enrollments.get()
    parent = portal()
    activate(parent, family_of(school, enrollment).code)
    url = f"/api/portal/children/{child.pk}/timetable/"
    page = parent.get(url).json()
    assert page["class_group"] == data["a"].name
    assert [(x["course"], x["start"]) for x in page["lessons"]] == [
        ("Mathématique", "07:30"),
        ("Anglais", page["lessons"][1]["start"]),
    ]
    stranger = portal()
    code = new_family(other_school, other_head, phone="+243990000001").code
    activate(stranger, code, phone="0990000001")
    assert stranger.get(url).status_code == 404


def test_publishing_tells_each_touched_person_once(api, school, head):
    data = classes(school, head)
    client = api(head)
    new_grid(client)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    other = MembershipFactory(school=school, roles=["teacher"]).user
    maths = new(data["a"], "Mathématique", 4, teacher=teacher)  # séances 2 + 2
    french = new(data["b"], "Français", 1, teacher=teacher)
    english = new(data["a"], "Anglais", 1, teacher=other)
    # Une famille avec un enfant dans chaque classe, une autre avec un enfant en A seulement.
    first = enrolled(school, head, data["a"], first_name="Amani")
    second = enrolled(school, head, data["a"], first_name="Josué")
    with use_school(school):
        sibling, _ = students.create_student(
            actor=head, family=first.family, last_name="Kasereka", first_name="Bahati", sex="F"
        )
        students.enroll(sibling, actor=head, class_group=data["b"])
    both, single = UserFactory(), UserFactory()
    with use_school(school):
        for user, student in ((both, first), (single, second)):
            family = student.family
            family.primary_user = user
            family.save(update_fields=["primary_user"])

    def sent() -> list[tuple]:
        with use_school(school):
            found = Notification.objects.filter(kind=Notification.Kind.TIMETABLE_PUBLISHED)
            rows = sorted((n.user_id, n.app, n.url, n.body) for n in found)
            found.delete()
        return rows

    publish(client, [(maths, 1, 1, 2), (french, 2, 1, 1), (english, 1, 3, 1)])
    notices = sent()
    # Une seule par personne : deux enseignants, deux parents (celui de deux enfants : l'accueil).
    assert sorted((user, app, url) for user, app, url, _body in notices) == sorted(
        [
            (teacher.pk, "gestion", "/my-timetable"),
            (other.pk, "gestion", "/my-timetable"),
            (both.pk, "portail", "/"),
            (single.pk, "portail", f"/children/{second.pk}"),
        ]
    )
    assert any("Amani, Bahati" in body or "Bahati, Amani" in body for *_rest, body in notices)

    # Seul le français (classe B) change : son enseignant et la famille qui a un enfant en B.
    publish(client, [(maths, 1, 1, 2), (french, 3, 1, 1), (english, 1, 3, 1)], "2026-11-02")
    assert sorted(user for user, *_rest in sent()) == sorted([teacher.pk, both.pk])

    # Même horaire publié de nouveau : personne.
    publish(client, [(maths, 1, 1, 2), (french, 3, 1, 1), (english, 1, 3, 1)], "2026-11-09")
    assert sent() == []

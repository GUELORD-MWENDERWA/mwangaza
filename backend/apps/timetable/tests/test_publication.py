"""Publication de l'horaire (EDT.4a) : droit dédié, isolation, refus tant qu'il y a du rouge,
version publiée immuable, l'ancienne archivée, date d'effet, journal."""

import pytest

from apps.academics.tests.test_courses import classes
from apps.accounts.models import Role
from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.timetable.models import Timetable
from apps.timetable.tests.test_constraints import new
from apps.timetable.tests.test_drafts import DRAFTS, codes, place
from apps.timetable.tests.test_timetable import log, new_grid
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

VERSIONS = "/api/timetable/versions/"


def test_publish_rights_isolation_and_conflicts(api, school, head, other_school, other_head):
    data = classes(school, head)
    classes(other_school, other_head)
    client = api(head)
    beta = api(other_head, host="beta.localhost")
    new_grid(client)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    maths = new(data["a"], "Mathématique", 5, teacher=teacher)  # séances 2 + 2 + 1
    french = new(data["b"], "Français", 2, teacher=teacher)  # 1 + 1
    draft = client.post(DRAFTS, {"name": "Brouillon 1"}).json()
    url = f"{DRAFTS}{draft['id']}/"
    client.post(f"{url}entries/", place(maths, 1, 1, 2))
    state = client.post(f"{url}entries/", place(french, 1, 2, 1)).json()
    assert "same_teacher" in codes(state)
    body = {"valid_from": "2026-10-26"}

    # Droit dédié : régler l'horaire ne suffit pas pour le publier.
    with use_school(school):
        planner = Role.objects.create(name="Horaire", permissions=["timetable.manage"])
    manager = api(MembershipFactory(school=school, roles=[planner]).user)
    assert manager.get(url).status_code == 200
    assert manager.post(f"{url}publish/", body).status_code == 403
    assert api(teacher).post(f"{url}publish/", body).status_code == 403
    # L'école B ne publie ni ne voit rien de A.
    assert beta.post(f"{url}publish/", body).status_code == 404
    assert beta.get(VERSIONS).json() == []

    # Du rouge : refusé, rien n'a changé ; hors de l'année : refusé.
    refused = client.post(f"{url}publish/", body)
    assert (refused.status_code, refused.json()["code"]) == (409, "publish_conflicts")
    assert client.post(f"{url}publish/", {"valid_from": "2027-08-01"}).json()["code"] == (
        "valid_from_outside_year"
    )
    assert client.get(VERSIONS).json() == []
    assert not log(school, Action.TIMETABLE_PUBLISHED)

    # Conflit corrigé : publié, même avec des heures restant à placer.
    entry = next(row for row in state["entries"] if row["course"] == str(french.pk))
    client.patch(f"{url}entries/{entry['id']}/", {"weekday": 2, "first": 1})
    published = client.post(f"{url}publish/", body)
    assert published.status_code == 200, published.json()
    state = published.json()
    assert (state["status"], state["valid_from"], state["can_undo"]) == (
        "published",
        "2026-10-26",
        False,
    )
    assert state["published_by"] == str(head)
    [entry] = log(school, Action.TIMETABLE_PUBLISHED)
    assert entry.after == {
        "name": "Brouillon 1",
        "valid_from": "2026-10-26",
        "lessons": 2,
        "hours": 3,
        "left_hours": 4,
        "warnings": state["warnings"],
        "replaced": None,
    }
    assert beta.get(url).status_code == 404


def test_published_is_frozen_and_replaced(api, school, head):
    data = classes(school, head)
    client = api(head)
    new_grid(client)
    maths = new(data["a"], "Mathématique", 2)
    first = client.post(DRAFTS, {"name": "Rentrée"}).json()
    url = f"{DRAFTS}{first['id']}/"
    state = client.post(f"{url}entries/", place(maths, 1, 1, 1)).json()
    [lesson] = state["entries"]
    assert client.post(f"{url}publish/", {"valid_from": "2026-09-01"}).status_code == 200

    # Publiée : plus aucun geste, ni suppression, ni nouvelle publication, ni calcul.
    for refused in (
        client.patch(f"{url}entries/{lesson['id']}/", {"weekday": 2, "first": 1}),
        client.post(f"{url}entries/", place(maths, 2, 1, 1)),
        client.delete(f"{url}entries/{lesson['id']}/"),
        client.post(f"{url}undo/"),
        client.delete(url),
        client.post(f"{url}publish/", {"valid_from": "2026-09-01"}),
    ):
        assert (refused.status_code, refused.json()["code"]) == (409, "not_a_draft")
    calc = {"request_id": str(uuid7()), "timetable": first["id"]}
    assert client.post("/api/timetable/runs/", calc).status_code == 400
    assert [row["name"] for row in client.get(DRAFTS).json()] == []

    # Copie de la publiée, modifiée, publiée plus tard : l'ancienne est archivée.
    second = client.post(DRAFTS, {"name": "Après Toussaint", "based_on": first["id"]}).json()
    assert [(row["weekday"], row["first"]) for row in second["entries"]] == [(1, 1)]
    url2 = f"{DRAFTS}{second['id']}/"
    client.post(f"{url2}entries/", place(maths, 3, 1, 1))
    early = client.post(f"{url2}publish/", {"valid_from": "2026-08-31"})
    assert early.json()["code"] == "valid_from_outside_year"
    assert client.post(f"{url2}publish/", {"valid_from": "2026-11-02"}).status_code == 200
    third = client.post(DRAFTS, {"name": "Trop tôt", "based_on": second["id"]}).json()
    before = client.post(f"{DRAFTS}{third['id']}/publish/", {"valid_from": "2026-10-01"})
    assert before.json()["code"] == "valid_from_before_current"
    with use_school(school):
        assert dict(Timetable.objects.values_list("name", "status")) == {
            "Rentrée": "archived",
            "Après Toussaint": "published",
            "Trop tôt": "draft",
        }
    listed = client.get(VERSIONS).json()
    assert [(row["name"], row["status"], row["hours"]) for row in listed] == [
        ("Après Toussaint", "published", 2),
        ("Rentrée", "archived", 1),
    ]
    assert listed[0]["published_by"] == str(head)
    published = log(school, Action.TIMETABLE_PUBLISHED)
    assert {row.after["replaced"] for row in published} == {None, "Rentrée"}
    # Une version archivée se relit, mais ne bouge plus.
    assert client.get(url).json()["status"] == "archived"

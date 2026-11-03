# ruff: noqa: F811, F401
"""Fil parent ↔ école (8.8) : le parent écrit, le personnel qui communique avec les familles lit et
répond, chacun est prévenu une fois ; droit dédié, limite horaire, isolation entre familles et
entre écoles."""

import pytest

from apps.academics.tests.test_resits import data, physics_teacher
from apps.core.tenancy import use_school
from apps.notifications.models import Notification
from apps.portal.tests.test_access import activate, new_family, portal
from apps.portal.tests.test_results import parent_of, student_of
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

THREADS = "/api/parent-threads/"


def thread_url(data, key="amani") -> str:
    return f"/api/portal/children/{student_of(data, key)}/thread/"


def post(client, url, **body):
    return client.post(url, body, content_type="application/json")


def kinds(school, user) -> list[str]:
    with use_school(school):
        return sorted(Notification.objects.filter(user=user).values_list("kind", flat=True))


def test_a_parent_writes_the_school_answers_and_each_is_told_once(api, school, head, cashier, data):
    parent = parent_of(data)
    assert parent.get(thread_url(data)).json() == {
        "id": str(student_of(data, "amani")),
        "messages": [],
        "unread": False,
    }

    sent = post(parent, thread_url(data), body="Pouvez-vous accorder un délai ?", topic="waiver")
    assert sent.status_code == 200 and sent.json()["messages"][0]["topic"] == "waiver"
    assert post(parent, thread_url(data), body="  ").status_code == 400

    # Le préfet le voit non lu, l'ouvre (lu), répond ; la caissière n'a pas ce droit.
    assert api(cashier).get(THREADS).status_code == 403
    listed = api(head).get(THREADS).json()["results"]
    assert [(t["student_name"], t["unread"]) for t in listed] == [("Bahati X", True)]
    opened = api(head).get(f"{THREADS}{listed[0]['id']}/").json()
    assert [m["from_school"] for m in opened["messages"]] == [False]
    assert api(head).get(THREADS).json()["results"][0]["unread"] is False
    assert (
        api(cashier).post(f"{THREADS}{listed[0]['id']}/reply/", {"body": "Oui"}).status_code == 403
    )
    answer = api(head).post(f"{THREADS}{listed[0]['id']}/reply/", {"body": "Accordé jusqu'au 30."})
    assert answer.status_code == 201

    body = parent.get(thread_url(data)).json()
    assert ([m["from_school"] for m in body["messages"]], body["unread"]) == ([False, True], True)
    assert parent.post(f"{thread_url(data)}read/").status_code == 204
    assert parent.get(thread_url(data)).json()["unread"] is False
    # Un message pour le personnel qui répond (pas celui qui a écrit), un pour le parent.
    assert kinds(school, head) == ["parent_message"]
    assert "parent_message" not in kinds(school, cashier)


def test_a_parent_cannot_flood_the_school_and_the_thread_stays_in_its_family_and_school(
    api, other_school, other_head, school, head, data
):
    parent = parent_of(data)
    codes = [post(parent, thread_url(data), body=f"Message {n}").status_code for n in range(6)]
    assert codes == [200] * 5 + [429]

    # Autre famille de l'école, famille d'une autre école : ni lire ni écrire, 404.
    neighbour = portal()
    activate(neighbour, new_family(school, head, phone="+243970000002").code, phone="0970000002")
    stranger = portal()
    activate(
        stranger,
        new_family(other_school, other_head, phone="+243990000001").code,
        phone="0990000001",
    )
    for who in (neighbour, stranger):
        assert who.get(thread_url(data)).status_code == 404
        assert post(who, thread_url(data), body="Coucou").status_code == 404
        assert who.post(f"{thread_url(data)}read/").status_code == 404

    # Le personnel d'une autre école ne voit pas le fil et ne peut pas y répondre.
    foreign = api(other_head, host="beta.localhost")
    assert foreign.get(THREADS).json()["results"] == []
    thread = api(head).get(THREADS).json()["results"][0]["id"]
    assert foreign.get(f"{THREADS}{thread}/").status_code == 404
    assert foreign.post(f"{THREADS}{thread}/reply/", {"body": "Piraterie"}).status_code == 404

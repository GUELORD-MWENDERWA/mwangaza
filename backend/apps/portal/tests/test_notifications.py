"""Notifications du parent sur le portail (5.5.2) : son centre de notifications, toutes écoles
mêlées, ne montre que les siennes, celles du Portail et des écoles où une de ses familles a encore
accès ; l'abonnement de son navigateur n'a pas d'école et ne reçoit que le Portail."""

from unittest import mock

import pytest
from django.utils import timezone

from apps.core.tenancy import use_all_schools
from apps.notifications import push
from apps.notifications.models import Notification, NotificationPreference, PushSubscription
from apps.portal.tests.test_access import activate, new_family, portal, post, reloaded
from apps.portal.tests.test_families import link
from apps.students.models import Family

pytestmark = pytest.mark.django_db

NOTIFICATIONS = "/api/portal/notifications/"
App, Kind = Notification.App, Notification.Kind


@pytest.fixture(autouse=True)
def _vapid(settings):
    settings.WEBPUSH_VAPID_PUBLIC_KEY = "public-key"
    settings.WEBPUSH_VAPID_PRIVATE_KEY = "private-key"


@pytest.fixture
def sent():
    """Envois Web Push, sans réseau : `sent.call_args_list`."""
    with mock.patch("apps.notifications.push.webpush") as webpush:
        yield webpush


def note(school, user, title, app=App.PORTAIL):
    [notification] = push.notify([user], school=school, app=app, kind=Kind.TEST, title=title)
    return notification


def titles(client, **params) -> list[str]:
    return [n["title"] for n in client.get(NOTIFICATIONS, params).json()["results"]]


def test_a_parent_reads_and_marks_only_their_portal_notifications_of_schools_open_to_them(
    school, other_school, head, other_head
):
    family = new_family(school, head)
    client = portal()
    activate(client, family.code)
    parent = reloaded(family).primary_user
    # Le même tuteur a une famille dans l'autre école, reliée par son code.
    other_family = new_family(other_school, other_head)
    link(client, other_family.code)
    stranger_family = new_family(school, head, phone="+243971234568")
    stranger = portal()
    activate(stranger, stranger_family.code, phone="0971234568")

    mine = note(school, parent, "Alpha")
    note(other_school, parent, "Beta")
    note(school, parent, "Gestion", app=App.GESTION)
    theirs = note(school, reloaded(stranger_family).primary_user, "Autre parent")

    listed = client.get(NOTIFICATIONS).json()["results"]
    assert [(n["title"], n["school_name"]) for n in listed] == [
        ("Beta", other_school.name),
        ("Alpha", school.name),
    ]
    assert titles(stranger) == ["Autre parent"]

    # « Lue » : celle d'un autre compte est ignorée.
    read = post(client, "notifications/read/", ids=[str(mine.pk), str(theirs.pk)])
    assert read.status_code == 204
    assert titles(client, unread="true") == ["Beta"]
    assert titles(stranger, unread="true") == ["Autre parent"]

    # L'autre école coupe l'accès de la famille : ses notifications ne se lisent ni ne se notent.
    with use_all_schools():
        Family.all_schools.filter(pk=other_family.pk).update(portal_suspended_at=timezone.now())
    assert titles(client) == ["Alpha"]
    post(client, "notifications/read/")
    with use_all_schools():
        assert Notification.all_schools.get(title="Beta").read_at is None

    # Plus aucune école ouverte au compte : pas de notification d'essai.
    with use_all_schools():
        Family.all_schools.filter(pk=family.pk).update(portal_suspended_at=timezone.now())
    assert post(client, "notifications/test/").status_code == 409
    with use_all_schools():
        assert Notification.all_schools.filter(user=parent, app=App.PORTAIL).count() == 2


def test_notifications_need_a_session_at_the_portal_address(api, school, head):
    assert portal().get(NOTIFICATIONS).status_code == 403
    at_school = api(head)
    assert at_school.get(NOTIFICATIONS).status_code == 404
    assert at_school.post(f"{NOTIFICATIONS}subscribe/", {}).status_code == 404


def test_the_browser_subscribes_without_a_school_and_alone_gets_the_portal(
    school, head, sent, django_capture_on_commit_callbacks
):
    family = new_family(school, head)
    client = portal()
    activate(client, family.code)
    parent = reloaded(family).primary_user
    preferences = client.get(f"{NOTIFICATIONS}preferences/").json()
    assert preferences == {
        "vapid_public_key": "public-key",
        "kinds": [
            "payment_received",
            "announcement",
            "summons",
            "discipline_incident",
            "place_offered",
            "payment_due",
            "payment_overdue",
        ],
        "muted": [],
    }
    # Le même compte travaille aussi à l'école : ce qu'il a coupé dans la Gestion ne se règle
    # pas depuis le portail, et y enregistrer ses préférences n'y touche pas.
    push.set_muted_kinds(parent, push.offered_kinds(App.GESTION), [Kind.PLATFORM_NEWS])
    saved = client.put(
        f"{NOTIFICATIONS}preferences/",
        {"muted": ["platform_news", "announcement"]},
        content_type="application/json",
    )
    assert saved.json()["muted"] == ["announcement"]
    assert NotificationPreference.objects.get(user=parent).muted == [
        "announcement",
        "platform_news",
    ]

    phone = {"endpoint": "https://push.example/telephone", "keys": {"p256dh": "k", "auth": "a"}}
    assert post(client, "notifications/subscribe/", **phone).status_code == 204
    subscription = PushSubscription.objects.get()
    assert (subscription.user, subscription.app, subscription.school) == (parent, App.PORTAIL, None)
    # Le même compte travaille aussi à l'école : son navigateur de la Gestion ne reçoit rien.
    PushSubscription.objects.create(
        user=parent,
        app=App.GESTION,
        school=school,
        endpoint="https://push.example/bureau",
        p256dh="k",
        auth="a",
    )

    with django_capture_on_commit_callbacks(execute=True):
        test = post(client, "notifications/test/")
    assert test.status_code == 201
    assert [c.kwargs["subscription_info"]["endpoint"] for c in sent.call_args_list] == [
        phone["endpoint"]
    ]
    assert titles(client) == [test.json()["title"]]

    # Un autre compte ne désabonne pas ce navigateur ; le sien, oui.
    other_family = new_family(school, head, phone="+243971234568")
    stranger = portal()
    activate(stranger, other_family.code, phone="0971234568")
    post(stranger, "notifications/unsubscribe/", endpoint=phone["endpoint"])
    assert PushSubscription.objects.filter(app=App.PORTAIL).count() == 1
    assert post(client, "notifications/unsubscribe/", endpoint=phone["endpoint"]).status_code == 204
    assert not PushSubscription.objects.filter(app=App.PORTAIL).exists()

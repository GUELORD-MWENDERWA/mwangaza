"""Notifications sur l'écran (5.5) : centre de notifications de la Gestion, abonnement des
navigateurs, préférences, envoi Web Push par Celery. Une notification d'une école ne se lit, ne se
note et ne s'envoie que dans cette école ; un abonnement ne reçoit que son école et son
application. Alertes du super-admin (S.3.2) : abonnement dans la console seulement, une alerte par
usage d'un compte super-admin et par session support ouverte."""

import json
from unittest import mock

import pytest
from django.utils import translation
from pywebpush import WebPushException

from apps.accounts.models import User
from apps.audit.actions import PlatformAction
from apps.core.tenancy import use_school
from apps.notifications import platform, push
from apps.notifications.models import Notification, PushSubscription
from tests.factories import MembershipFactory, UserFactory, enable_totp, totp_code

pytestmark = pytest.mark.django_db

NOTIFICATIONS = "/api/notifications/"
ALERTS = "/api/console/alerts/"
CONSOLE = "admin.localhost"
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


def endpoints(sent) -> list[str]:
    return [call.kwargs["subscription_info"]["endpoint"] for call in sent.call_args_list]


def subscribe(user, endpoint, *, app=App.GESTION, school=None):
    return PushSubscription.objects.create(
        user=user, app=app, school=school, endpoint=endpoint, p256dh="k", auth="a"
    )


def news(school, user, title="Maintenance samedi"):
    [notification] = push.notify(
        [user], school=school, app=App.GESTION, kind=Kind.PLATFORM_NEWS, title=title
    )
    return notification


def test_center_is_per_school_and_per_account(api, school, other_school, head, cashier):
    MembershipFactory(user=head, school=other_school, roles=["teacher"])
    mine = news(school, head)
    news(school, cashier)
    at_beta = api(head, host="beta.localhost")
    assert at_beta.get(NOTIFICATIONS).json()["count"] == 0
    # Noter depuis l'autre école, même avec l'identifiant : rien ne change.
    assert at_beta.post(NOTIFICATIONS + "read/", {"ids": [str(mine.pk)]}).status_code == 204
    alpha = api(head)
    assert [n["id"] for n in alpha.get(NOTIFICATIONS + "?unread=true").json()["results"]] == [
        str(mine.pk)
    ]
    assert alpha.post(NOTIFICATIONS + "read/", {}).status_code == 204
    assert alpha.get(NOTIFICATIONS + "?unread=true").json()["count"] == 0
    with use_school(school):
        # La notification de la caissière n'a pas été touchée.
        assert Notification.objects.filter(read_at__isnull=True).count() == 1


def test_only_school_staff_and_never_during_support(api, school, platform_admin):
    parent = UserFactory()
    for client in (api(), api(parent)):
        assert client.get(NOTIFICATIONS).status_code == 403
        assert client.post(NOTIFICATIONS + "test/").status_code == 403
    support = api(platform_admin)
    assert support.post("/api/support/", {"reason": "Essai des notifications"}).status_code == 201
    assert support.get(NOTIFICATIONS).json()["count"] == 0
    browser = {"endpoint": "https://push.example/1", "keys": {"p256dh": "k", "auth": "a"}}
    for path, data in (("test/", {}), ("subscribe/", browser)):
        response = support.post(NOTIFICATIONS + path, data)
        assert response.status_code == 403
        assert response.json()["code"] == "support_session"
    assert support.put(NOTIFICATIONS + "preferences/", {"muted": []}).status_code == 403
    assert not PushSubscription.objects.exists()


def test_subscription_belongs_to_the_school_address(api, school, other_school, head, cashier):
    MembershipFactory(user=head, school=other_school, roles=["teacher"])
    data = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}
    assert api(head).post(NOTIFICATIONS + "subscribe/", data).status_code == 204
    subscription = PushSubscription.objects.get()
    assert (subscription.user, subscription.app, subscription.school) == (head, "gestion", school)
    # Depuis l'autre école, le même navigateur n'est pas désabonné.
    gone = {"endpoint": data["endpoint"]}
    api(head, host="beta.localhost").post(NOTIFICATIONS + "unsubscribe/", gone)
    assert PushSubscription.objects.exists()
    # Ordinateur partagé : la caissière reprend le navigateur, le directeur n'y reçoit plus rien.
    assert api(cashier).post(NOTIFICATIONS + "subscribe/", data).status_code == 204
    assert PushSubscription.objects.get().user == cashier
    api(cashier).post(NOTIFICATIONS + "unsubscribe/", gone)
    assert not PushSubscription.objects.exists()


def test_delivery_reaches_only_the_right_browsers(
    school, other_school, head, sent, django_capture_on_commit_callbacks
):
    MembershipFactory(user=head, school=other_school, roles=["teacher"])
    subscribe(head, "https://push.example/alpha", school=school)
    subscribe(head, "https://push.example/beta", school=other_school)
    subscribe(head, "https://push.example/portail", app=App.PORTAIL)
    with django_capture_on_commit_callbacks(execute=True):
        notification = news(school, head)
    assert endpoints(sent) == ["https://push.example/alpha"]
    payload = sent.call_args.kwargs["data"]
    assert str(notification.pk) in payload and "Maintenance samedi" in payload


def test_muted_kind_stays_in_the_center_and_expired_browser_is_dropped(
    api, school, head, sent, django_capture_on_commit_callbacks
):
    subscribe(head, "https://push.example/alpha", school=school)
    client = api(head)
    response = client.put(NOTIFICATIONS + "preferences/", {"muted": ["platform_news", "test"]})
    # La notification d'essai ne se coupe pas.
    assert response.json() == {
        "vapid_public_key": "public-key",
        "kinds": [
            "platform_news",
            "staff_announcement",
            "cancellation_request",
            "cash_difference",
            "register_open",
        ],
        "muted": ["platform_news"],
    }
    with django_capture_on_commit_callbacks(execute=True):
        news(school, head)
    assert not sent.called
    assert client.get(NOTIFICATIONS).json()["count"] == 1
    sent.side_effect = WebPushException("Gone", response=mock.Mock(status_code=410))
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(NOTIFICATIONS + "test/").status_code == 201
    assert sent.call_count == 1
    assert not PushSubscription.objects.exists()


def test_platform_news_notifies_active_staff_of_targeted_schools(
    school, other_school, head, other_head, platform_admin, sent
):
    left = MembershipFactory(school=school, roles=["teacher"], is_active=False).user
    platform.publish(
        actor=platform_admin,
        title="Maintenance samedi",
        body="Coupure de 22 h à minuit.",
        audience="schools",
        schools=[school],
    )
    recipients = set(Notification.all_schools.values_list("user", "school", "url"))
    assert recipients == {(head.pk, school.pk, "/platform-news")}
    assert left.pk not in {user for user, _, _ in recipients}
    assert other_head.pk not in {user for user, _, _ in recipients}


def test_only_a_platform_admin_subscribes_to_alerts_and_only_in_the_console(
    api, platform_admin, head
):
    data = {"endpoint": "https://push.example/console", "keys": {"p256dh": "k", "auth": "a"}}
    # Personnel d'une école : refusé ; à l'adresse d'une école, ce point d'API n'existe pas ;
    # sans double authentification : refusé.
    assert api(head, host=CONSOLE).post(ALERTS + "subscribe/", data).status_code == 403
    assert api(platform_admin).post(ALERTS + "subscribe/", data).status_code == 404
    assert api(platform_admin, host=CONSOLE, mfa=False).get(ALERTS).status_code == 403
    assert not PushSubscription.objects.exists()

    console = api(platform_admin, host=CONSOLE)
    assert console.get(ALERTS).json() == {"vapid_public_key": "public-key"}
    assert console.post(ALERTS + "subscribe/", data).status_code == 204
    subscription = PushSubscription.objects.get()
    assert (subscription.user, subscription.app, subscription.school) == (
        platform_admin,
        "console",
        None,
    )
    # Le serveur n'écrit qu'à une adresse https : jamais à un service interne.
    internal = {**data, "endpoint": "http://redis:6379/"}
    assert console.post(ALERTS + "subscribe/", internal).status_code == 400
    gone = {"endpoint": data["endpoint"]}
    assert console.post(ALERTS + "unsubscribe/", gone).status_code == 204
    assert not PushSubscription.objects.exists()


def test_each_use_of_a_platform_account_alerts_the_console_browsers_only(
    api, school, platform_admin, sent, django_capture_on_commit_callbacks
):
    second = User.objects.create_superuser("0000000009", "secret-123", language="en")
    former = UserFactory()
    subscribe(platform_admin, "https://push.example/console", app="console")
    subscribe(second, "https://push.example/second", app="console")
    # Plus super-admin : son navigateur ne reçoit plus rien. Même compte abonné dans une école ou
    # au Portail : les alertes de la plateforme n'y arrivent pas.
    subscribe(former, "https://push.example/former", app="console")
    subscribe(platform_admin, "https://push.example/gestion", school=school)
    subscribe(platform_admin, "https://push.example/portail", app=App.PORTAIL)
    secret = enable_totp(platform_admin)
    console = api(host=CONSOLE)
    login, code = "/api/auth/login/", "/api/auth/login/totp/"

    with django_capture_on_commit_callbacks(execute=True):
        console.post(login, {"phone": platform_admin.phone, "password": "secret-123"})
        wrong = "000000" if totp_code(secret) != "000000" else "111111"
        console.post(code, {"code": wrong})
    # Celui dont le compte sert est prévenu lui aussi : son mot de passe a pu être volé.
    assert sorted(endpoints(sent)) == [
        "https://push.example/console",
        "https://push.example/second",
    ]
    payloads = {
        call.kwargs["subscription_info"]["endpoint"]: json.loads(call.kwargs["data"])
        for call in sent.call_args_list
    }
    with translation.override("fr"):
        french = str(PlatformAction.ACCESS_CODE_REFUSED.label)
    assert payloads["https://push.example/console"] == {
        "id": mock.ANY,
        "title": french,
        "body": f"{platform_admin} · 127.0.0.1 · {CONSOLE}",
        "url": "/journal",
    }
    assert payloads["https://push.example/second"]["title"] == (
        "Two-factor code refused on a platform account"
    )

    sent.reset_mock()
    with django_capture_on_commit_callbacks(execute=True):
        console.post(code, {"code": totp_code(secret)})
    assert len(endpoints(sent)) == 2
    assert json.loads(sent.call_args.kwargs["data"])["url"] == "/journal"


def test_a_support_session_alerts_the_console_and_an_expired_browser_is_dropped(
    api, school, platform_admin, sent, django_capture_on_commit_callbacks
):
    subscribe(platform_admin, "https://push.example/console", app="console")
    client = api(platform_admin)
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post("/api/support/", {"reason": "Aide à la clôture"}).status_code == 201
    payload = json.loads(sent.call_args.kwargs["data"])
    assert payload["url"] == "/journal/support"
    assert payload["body"] == f"{platform_admin} · {school.name} · Aide à la clôture"

    sent.side_effect = WebPushException("Gone", response=mock.Mock(status_code=410))
    with django_capture_on_commit_callbacks(execute=True):
        client.post("/api/support/", {"reason": "Suite"})
    assert not PushSubscription.objects.exists()

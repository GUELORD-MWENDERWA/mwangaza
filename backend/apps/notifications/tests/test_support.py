"""Demandes d'aide à la plateforme (SUP.1) : chacun ne voit que ses demandes, aucune école ne lit
celles d'une autre, la console demande son droit et respecte son mode, réponse → notification."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.core.tenancy import use_all_schools, use_school
from apps.notifications.models import Notification, SupportRequest
from apps.schools.models import School
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db
CONSOLE = "admin.localhost"
DEMO = {"HTTP_X_CONSOLE_MODE": "demo"}
MESSAGE = {"subject": "Le reçu ne s'imprime plus", "body": "Rien ne sort.", "screen": "/app/cash"}


def team(role: str):
    return UserFactory(is_platform_admin=True, platform_roles=[role])


def ask(api, user, host="alpha.localhost", **extra):
    reply = api(user, host=host).post("/api/help/requests/", {**MESSAGE, **extra})
    assert reply.status_code == 201, reply.content
    return reply.json()


def rows(response):
    data = response.json()
    return data["results"] if isinstance(data, dict) else data


def test_each_member_sees_only_their_own_requests(api, school, head, cashier, other_head):
    mine = ask(api, cashier)
    assert [r["id"] for r in rows(api(cashier).get("/api/help/requests/"))] == [mine["id"]]
    for stranger, host in ((head, "alpha.localhost"), (other_head, "beta.localhost")):
        client = api(stranger, host=host)
        assert rows(client.get("/api/help/requests/")) == []
        url = f"/api/help/requests/{mine['id']}/"
        assert client.get(url).status_code == 404
        assert client.post(url + "reply/", {"body": "intrus"}).status_code == 404
        assert client.post(url + "close/").status_code == 404
    # Les messages sont sans HTML interprété et l'écran est joint d'office.
    detail = api(cashier).get(f"/api/help/requests/{mine['id']}/").json()
    assert detail["screen"] == "/app/cash" and detail["status"] == "open"
    assert [r["from_platform"] for r in detail["replies"]] == [False]


def test_ten_requests_a_day_per_account(api, cashier, head):
    for _ in range(10):
        ask(api, cashier)
    over = api(cashier).post("/api/help/requests/", MESSAGE)
    assert over.status_code == 429 and over.json()["code"] == "support_limit"
    ask(api, head)  # la limite est par compte


def test_numbers_are_global_across_schools(api, cashier, other_head):
    first = ask(api, cashier)
    second = ask(api, other_head, host="beta.localhost")
    assert second["number"] == first["number"] + 1


def test_console_needs_the_right_and_follows_its_mode(
    api, school, other_school, cashier, other_head
):
    ask(api, cashier)
    with use_all_schools():
        School.objects.filter(pk=other_school.pk).update(environment=School.Environment.DEMO)
    ask(api, other_head, host="beta.localhost")
    for role in ("finance", "communication"):
        assert api(team(role), host=CONSOLE).get("/api/console/support/").status_code == 403
    assert (
        api(cashier).get("/api/console/support/").status_code == 404
    )  # pas à l'adresse d'une école
    support = api(team("support"), host=CONSOLE)
    assert [r["school"] for r in rows(support.get("/api/console/support/"))] == ["alpha"]
    demo = api(team("support"), host=CONSOLE, headers=DEMO)
    assert [r["school"] for r in rows(demo.get("/api/console/support/"))] == ["beta"]
    # Une demande de l'autre mode n'est ni lisible ni modifiable.
    with use_all_schools():
        beta = SupportRequest.all_schools.get(school=other_school)
    assert support.get(f"/api/console/support/{beta.pk}/").status_code == 404
    assert support.post(f"/api/console/support/{beta.pk}/close/").status_code == 404


def test_platform_reply_notifies_the_author_and_school_reply_reopens(api, school, cashier):
    created = ask(api, cashier)
    owner = team("owner")
    console = api(owner, host=CONSOLE)
    url = f"/api/console/support/{created['id']}/"
    assert console.post(url + "reply/", {"body": "Choisissez Thermique 80 mm."}).status_code == 201
    with use_school(school):
        note = Notification.objects.get(user=cashier, kind="support_reply")
        assert note.url == f"/help/requests/{created['id']}"
    mine = api(cashier).get(f"/api/help/requests/{created['id']}/").json()
    assert mine["status"] == "answered"
    assert [r["from_platform"] for r in mine["replies"]] == [False, True]
    assert PlatformAuditLog.objects.filter(action=PlatformAction.SUPPORT_REPLIED).count() == 1
    # L'école répond : la demande redevient « à traiter » ; elle la ferme ; puis la rouvre.
    mine_url = f"/api/help/requests/{created['id']}/"
    assert api(cashier).post(mine_url + "reply/", {"body": "Toujours rien"}).status_code == 201
    assert console.get(url).json()["status"] == "open"
    assert api(cashier).post(mine_url + "close/").json()["status"] == "closed"
    assert api(cashier).post(mine_url + "reply/", {"body": "Ça recommence"}).status_code == 201
    assert console.get(url).json()["status"] == "open"


def test_a_request_closed_for_a_month_stays_closed(api, school, cashier):
    created = ask(api, cashier)
    api(cashier).post(f"/api/help/requests/{created['id']}/close/")
    with use_all_schools():
        SupportRequest.all_schools.update(closed_at=timezone.now() - timedelta(days=31))
    late = api(cashier).post(f"/api/help/requests/{created['id']}/reply/", {"body": "Encore"})
    assert late.status_code == 409 and late.json()["code"] == "support_closed"


def test_only_support_staff_can_be_assigned(api, cashier):
    created = ask(api, cashier)
    console = api(team("owner"), host=CONSOLE)
    url = f"/api/console/support/{created['id']}/assign/"
    helper = team("support")
    assert console.post(url, {"assignee": str(helper.pk)}).json()["assignee"] == str(helper.pk)
    assert console.post(url, {"assignee": str(team("communication").pk)}).status_code == 400
    assert console.post(url, {"assignee": None}).json()["assignee"] is None
    assert PlatformAuditLog.objects.filter(action=PlatformAction.SUPPORT_ASSIGNED).count() == 2


def test_new_request_is_emailed_to_the_support_address(api, cashier, settings, mailoutbox):
    from apps.core.models import PlatformSettings
    from apps.notifications import support

    settings.EMAIL_HOST = "smtp.example.test"
    PlatformSettings.objects.update_or_create(pk=1, defaults={"support_email": "aide@example.com"})
    created = ask(api, cashier)
    support.send_email(created["id"])
    assert mailoutbox[0].to == ["aide@example.com"]
    assert "Rien ne sort." in mailoutbox[0].body and "/support" in mailoutbox[0].body

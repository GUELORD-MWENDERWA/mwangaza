"""Console réelle ou démonstration (lot 5, ②bis) : un mode ne voit ni ne touche les données de
l'autre ; sans en-tête, c'est toujours le mode réel."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.console_mode import HEADER
from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.core.models import DemoRequest
from apps.notifications import platform
from apps.schools.models import School
from tests.factories import SchoolFactory, UserFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"


@pytest.fixture
def spaces():
    return {
        "live": SchoolFactory(code="reelle", environment=School.Environment.LIVE),
        "trial": SchoolFactory(code="essai", environment=School.Environment.TEST),
        "demo": SchoolFactory(code="demo-x", environment=School.Environment.DEMO),
    }


@pytest.fixture
def get(api, platform_admin):
    def call(path, mode=None, **params):
        extra = {"HTTP_X_CONSOLE_MODE": mode} if mode else {}
        client = api(platform_admin, host=CONSOLE).client
        return client.get(path, params, HTTP_HOST=CONSOLE, **extra)

    return call


def codes(response) -> set[str]:
    return {row["code"] for row in response.json()["results"]}


def test_schools_are_split_by_mode_and_default_to_real(get, spaces):
    assert HEADER == "X-Console-Mode"
    assert {"reelle", "essai"} <= codes(get("/api/console/schools/"))
    assert "demo-x" not in codes(get("/api/console/schools/"))
    assert "demo-x" not in codes(get("/api/console/schools/", mode="inconnu"))
    in_demo = codes(get("/api/console/schools/", mode="demo"))
    assert in_demo == {"demo-x"}
    # Une fiche de l'autre mode n'existe pas.
    assert get(f"/api/console/schools/{spaces['demo'].pk}/").status_code == 404
    assert get(f"/api/console/schools/{spaces['live'].pk}/", mode="demo").status_code == 404
    assert get(f"/api/console/schools/{spaces['demo'].pk}/", mode="demo").status_code == 200


def test_prospects_log_and_announcements_never_cross_modes(get, platform_admin, spaces):
    DemoRequest.objects.create(name="Vrai", phone="+243971234567", school_name="A")
    DemoRequest.objects.create(name="Faux", phone="+243000300001", school_name="B", is_demo=True)
    audit.record_platform(PlatformAction.SCHOOL_UPDATED, spaces["live"], actor=platform_admin)
    audit.record_platform(PlatformAction.SCHOOL_UPDATED, spaces["demo"], actor=platform_admin)
    real = platform.publish(actor=platform_admin, title="Réelle", body="x", audience="all_schools")
    fake = platform.publish(
        actor=platform_admin, title="Fictive", body="x", audience="all_schools", is_demo=True
    )

    def names(path, mode=None, key="name"):
        return {row[key] for row in get(path, mode=mode).json()["results"]}

    assert names("/api/console/demo-requests/") == {"Vrai"}
    assert names("/api/console/demo-requests/", "demo") == {"Faux"}
    assert names("/api/console/announcements/", key="title") == {"Réelle"}
    assert names("/api/console/announcements/", "demo", key="title") == {"Fictive"}
    live_log = get("/api/console/audit/").json()["results"]
    demo_log = get("/api/console/audit/", mode="demo").json()["results"]
    live_labels = {row["entity_label"] for row in live_log}
    demo_labels = {row["entity_label"] for row in demo_log}
    assert str(spaces["live"]) in live_labels and str(spaces["demo"]) not in live_labels
    assert str(spaces["demo"]) in demo_labels and str(spaces["live"]) not in demo_labels
    # L'annonce fictive est au journal fictif, l'annonce réelle au journal réel.
    assert "Réelle" in live_labels and "Fictive" in demo_labels
    assert "Fictive" not in live_labels and "Réelle" not in demo_labels
    assert PlatformAuditLog.objects.filter(is_demo=True).count() == 2
    # Dans la Gestion : une école de démonstration ne lit que les annonces fictives.
    user = UserFactory()
    seen = {a.pk for a in platform.for_school(spaces["demo"], user)}
    assert seen == {fake.pk}
    assert {a.pk for a in platform.for_school(spaces["live"], user)} == {real.pk}


def test_what_only_exists_for_real_answers_404_in_demonstration(get, spaces):
    for path in (
        "/api/console/business/",
        "/api/console/billing/plans/",
        "/api/console/billing/invoices/",
        "/api/console/site/entries/",
        "/api/console/platform/",
    ):
        assert get(path, mode="demo").status_code == 404, path
        assert get(path).status_code == 200, path


def test_dashboard_todo_follows_the_mode_and_the_rights(api, get, spaces):
    cache.clear()
    today = timezone.localdate()
    for key, days in (("live", 3), ("demo", 2)):
        School.objects.filter(pk=spaces[key].pk).update(
            status=School.Status.TRIAL, trial_ends_on=today + timedelta(days=days)
        )
    prospect = {"phone": "+243971234567", "school_name": "X"}
    DemoRequest.objects.create(name="Due", follow_up_on=today, status="contacted", **prospect)
    DemoRequest.objects.create(name="Tard", follow_up_on=today + timedelta(days=1), **prospect)
    DemoRequest.objects.create(name="Perdu", follow_up_on=today, status="lost", **prospect)
    DemoRequest.objects.create(name="Fictif", follow_up_on=today, is_demo=True, **prospect)

    live = get("/api/console/dashboard/").json()["todo"]
    assert [row["code"] for row in live["trials_ending"]] == ["reelle"]
    assert live["follow_ups"] == 1 and live["overdue"] == []
    demo = get("/api/console/dashboard/", mode="demo").json()["todo"]
    assert [row["code"] for row in demo["trials_ending"]] == ["demo-x"]
    assert demo["follow_ups"] == 1 and demo["overdue"] is None  # factures : réel seulement

    technical = UserFactory(is_platform_admin=True, platform_roles=["technical"])
    todo = api(technical, host=CONSOLE).get("/api/console/dashboard/").json()["todo"]
    assert todo["follow_ups"] is None and todo["overdue"] is None


def test_dashboard_recent_activity_stays_in_its_mode(api, get, platform_admin, spaces):
    audit.record_platform(PlatformAction.SCHOOL_UPDATED, spaces["live"], actor=platform_admin)
    audit.record_platform(PlatformAction.SCHOOL_UPDATED, spaces["demo"], actor=platform_admin)
    labels = lambda mode=None: {  # noqa: E731
        row["entity_label"] for row in get("/api/console/dashboard/", mode=mode).json()["recent"]
    }
    assert labels() == {str(spaces["live"])}
    assert labels("demo") == {str(spaces["demo"])}
    finance = UserFactory(is_platform_admin=True, platform_roles=["finance"])
    assert api(finance, host=CONSOLE).get("/api/console/dashboard/").json()["recent"] is None

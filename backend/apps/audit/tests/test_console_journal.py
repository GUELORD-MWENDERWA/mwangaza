"""Journal de la plateforme dans la console (5.4.2) : super-admin seulement, filtres par type
d'action, période et nom de l'objet."""

from datetime import timedelta
from unittest import mock
from urllib.parse import urlencode

import pytest
from django.utils import timezone

from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.core.models import PlatformSettings

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
JOURNAL = "/api/console/audit/"


def test_only_the_platform_admin_reads_the_platform_journal(api, platform_admin, head):
    assert api(head, host=CONSOLE).get(JOURNAL).status_code == 403
    assert api(platform_admin, host=CONSOLE, mfa=False).get(JOURNAL).status_code == 403
    assert api(platform_admin).get(JOURNAL).status_code == 404
    assert api(head).get(JOURNAL).status_code == 404


def test_filters_by_kind_period_and_object(
    api, platform_admin, school, other_school, head, django_assert_max_num_queries
):
    platform = PlatformSettings.load()
    last_week = timezone.now() - timedelta(days=7)
    with mock.patch("django.utils.timezone.now", return_value=last_week):
        audit.record_platform(PlatformAction.PLATFORM_UPDATED, platform, actor=platform_admin)
    audit.record_platform(PlatformAction.SCHOOL_SUSPENDED, school, actor=platform_admin)
    audit.record_platform(PlatformAction.SCHOOL_UPDATED, other_school, actor=platform_admin)
    audit.record_platform(PlatformAction.ACCOUNT_DEACTIVATED, head, actor=platform_admin)
    console = api(platform_admin, host=CONSOLE)

    def actions(**params) -> list[str]:
        return [
            row["action"] for row in console.get(f"{JOURNAL}?{urlencode(params)}").json()["results"]
        ]

    with django_assert_max_num_queries(5):
        everything = console.get(JOURNAL).json()
    assert everything["count"] == 4
    first = everything["results"][0]  # le plus récent d'abord
    assert first["entity_type"] == "accounts.user"
    assert (first["entity_id"], first["actor"]["id"]) == (str(head.pk), str(platform_admin.pk))
    assert actions(domain="school") == ["school.updated", "school.suspended"]
    assert actions(search=school.name) == ["school.suspended"]
    today = timezone.localdate().isoformat()
    assert "platform.updated" not in actions(since=today)
    assert actions(until=(timezone.localdate() - timedelta(days=1)).isoformat()) == [
        "platform.updated"
    ]
    assert (
        console.get(f"{JOURNAL}?{urlencode({'since': today, 'until': '2020-01-01'})}").status_code
        == 400
    )

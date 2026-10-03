"""Annonces de la plateforme aux écoles (5.4.3) : rédigées par le super-admin dans la console
(journal de la plateforme), lues par le personnel dans la Gestion. Une école ne voit que les
annonces qui la visent ; « lue » est noté par compte."""

from datetime import timedelta

import pytest

from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.notifications.models import PlatformAnnouncement, PlatformAnnouncementRead

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
ANNOUNCEMENTS = "/api/console/announcements/"
NEWS = "/api/platform-announcements/"


def publish(client, *, title="Maintenance samedi", audience="all_schools", schools=()):
    data = {"title": title, "body": "Coupure de 22 h à minuit.", "audience": audience}
    response = client.post(ANNOUNCEMENTS, {**data, "schools": [str(s.pk) for s in schools]})
    assert response.status_code == 201, response.content
    return response.json()


def test_console_api_only_for_the_platform_admin(api, platform_admin, head):
    for client in (api(head, host=CONSOLE), api(platform_admin, host=CONSOLE, mfa=False)):
        assert client.get(ANNOUNCEMENTS).status_code == 403
        assert client.post(ANNOUNCEMENTS, {"title": "x", "body": "y"}).status_code == 403
    # À l'adresse d'une école, la console n'existe pas.
    assert api(platform_admin).get(ANNOUNCEMENTS).status_code == 404
    assert not PlatformAnnouncement.objects.exists()


def test_publish_and_archive_go_to_the_platform_journal(api, platform_admin, other_school):
    console = api(platform_admin, host=CONSOLE)
    refused = console.post(ANNOUNCEMENTS, {"title": "x", "body": "y", "audience": "schools"})
    assert refused.status_code == 400
    assert refused.json()["fields"]["schools"]

    announcement = publish(console, audience="schools", schools=[other_school])
    archive = f"{ANNOUNCEMENTS}{announcement['id']}/archive/"
    assert console.post(archive).json()["archived_at"]
    assert console.post(archive).status_code == 200  # déjà archivée : rien ne change

    logs = PlatformAuditLog.objects.order_by("created_at")
    assert [log.action for log in logs] == [
        PlatformAction.ANNOUNCEMENT_PUBLISHED,
        PlatformAction.ANNOUNCEMENT_ARCHIVED,
    ]
    assert logs[0].after == {
        "title": "Maintenance samedi",
        "audience": "schools",
        "schools": [other_school.name],
    }
    assert all(log.actor == platform_admin for log in logs)


def test_each_school_reads_only_what_targets_it_and_read_is_per_account(
    api, platform_admin, other_school, head, cashier, other_head, django_assert_max_num_queries
):
    console = api(platform_admin, host=CONSOLE)
    everyone = publish(console, title="Nouvelle version")
    beta_only = publish(
        console, title="Abonnement Beta", audience="schools", schools=[other_school]
    )
    archived = publish(console, title="Ancienne")
    console.post(f"{ANNOUNCEMENTS}{archived['id']}/archive/")

    alpha, beta = api(head), api(other_head, host="beta.localhost")
    # Sans droits dans l'école de l'adresse : refusé.
    assert api(other_head).get(NEWS).status_code == 403
    assert api(other_head).post(f"{NEWS}read/", {"ids": [everyone["id"]]}).status_code == 403
    assert [a["title"] for a in alpha.get(NEWS).json()["results"]] == ["Nouvelle version"]
    assert [a["title"] for a in beta.get(NEWS).json()["results"]] == [
        "Abonnement Beta",
        "Nouvelle version",
    ]

    # L'annonce de Beta ne peut pas être marquée lue depuis Alpha ; la sienne, si.
    response = alpha.post(f"{NEWS}read/", {"ids": [beta_only["id"], everyone["id"]]})
    assert response.status_code == 204
    reads = PlatformAnnouncementRead.objects.values_list("announcement_id", "user_id")
    assert [(str(a), u) for a, u in reads] == [(everyone["id"], head.pk)]
    assert alpha.get(f"{NEWS}?unread=true").json()["count"] == 0
    assert api(cashier).get(f"{NEWS}?unread=true").json()["count"] == 1
    assert beta.get(f"{NEWS}?unread=true").json()["count"] == 2

    with django_assert_max_num_queries(8):
        listed = console.get(ANNOUNCEMENTS).json()["results"]
    read_by = {a["title"]: a["read_by"] for a in listed}
    assert read_by == {"Ancienne": 0, "Abonnement Beta": 0, "Nouvelle version": 1}


def test_announcement_older_than_the_school_is_not_shown(api, platform_admin, school, head):
    announcement = publish(api(platform_admin, host=CONSOLE))
    PlatformAnnouncement.objects.filter(pk=announcement["id"]).update(
        published_at=school.created_at - timedelta(minutes=1)
    )
    assert api(head).get(NEWS).json()["count"] == 0

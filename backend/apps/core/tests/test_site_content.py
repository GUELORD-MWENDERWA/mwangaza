"""Contenus du site tenus dans la console (SITE.1a) : questions, « Prochainement » et bandeau,
saisis par la communication, au journal, montrés par le site (brouillons cachés, anglais vide :
le français, texte échappé) dès que le cache est vidé. Droits : `test_console_team.py`."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.core.models import SiteEntry
from apps.core.tests.test_site import structured_data
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
ENTRIES = "/api/console/site/entries/"
BANNER = "/api/console/site/banner/"


@pytest.fixture(autouse=True)
def fresh_cache():
    """Le contenu du site est gardé en cache : rien ne passe d'un test à l'autre."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def console(api):
    return api(UserFactory(is_platform_admin=True, platform_roles=["communication"]), host=CONSOLE)


def test_communication_keeps_the_questions_each_change_in_the_journal(
    console, client, django_capture_on_commit_callbacks
):
    # La migration a repris le site d'avant, avec le nom de la plateforme.
    entries = console.get(ENTRIES).json()
    kinds = [entry["kind"] for entry in entries]
    assert [kinds.count(kind) for kind in SiteEntry.Kind.values] == [7, 4, 6]
    assert not any("{name}" in entry["title_fr"] + entry["text_en"] for entry in entries)
    assert len(structured_data(client.get("/").content.decode())["FAQPage"]["mainEntity"]) == 7

    # Le site lit le cache : une ligne écrite hors de la console n'y paraît pas encore.
    SiteEntry.objects.create(kind="home_question", title_fr="Q", text_fr="R", published=True)
    assert len(structured_data(client.get("/").content.decode())["FAQPage"]["mainEntity"]) == 7

    question = {"kind": "home_question", "title_fr": "Combien coûte <b>X</b> ?"}
    with django_capture_on_commit_callbacks(execute=True):
        created = console.post(
            ENTRIES, {**question, "text_fr": "Un an.\nPar élève.", "published": True}
        )
    assert created.status_code == 201, created.json()
    new = created.json()
    assert new["position"] == 8
    french = client.get("/").content.decode()
    # Texte simple : échappé, retours à la ligne gardés ; aussi dans les données structurées.
    assert "Combien coûte &lt;b&gt;X&lt;/b&gt; ?" in french and "Un an.<br>Par élève." in french
    assert len(structured_data(french)["FAQPage"]["mainEntity"]) == 9  # cache vidé
    assert "Combien coûte &lt;b&gt;X&lt;/b&gt; ?" in client.get("/en/").content.decode()

    item = f"{ENTRIES}{new['id']}/"
    with django_capture_on_commit_callbacks(execute=True):
        console.post(f"{item}move/", {"direction": "up"})
        moved = console.post(f"{item}move/", {"direction": "up"}).json()
        console.patch(item, {"title_en": "How much is X?"})
    home = [entry["title_fr"] for entry in moved if entry["kind"] == "home_question"]
    assert home.index(question["title_fr"]) == 6
    english = client.get("/en/").content.decode()
    assert english.index("How much is X?") < english.index("Is my school")
    assert console.patch(item, {"kind": "upcoming"}).status_code == 400

    with django_capture_on_commit_callbacks(execute=True):
        console.patch(item, {"published": False})  # brouillon : sur la console seulement
    assert "How much is X?" not in client.get("/en/").content.decode()
    with django_capture_on_commit_callbacks(execute=True):
        assert console.delete(item).status_code == 204

    journal = PlatformAuditLog.objects.filter(entity_id=new["id"]).order_by("created_at")
    assert [(entry.action, entry.actor.platform_roles) for entry in journal] == [
        (PlatformAction.SITE_ENTRY_CREATED, ["communication"]),
        (PlatformAction.SITE_ENTRY_MOVED, ["communication"]),
        (PlatformAction.SITE_ENTRY_MOVED, ["communication"]),
        (PlatformAction.SITE_ENTRY_UPDATED, ["communication"]),
        (PlatformAction.SITE_ENTRY_UPDATED, ["communication"]),
        (PlatformAction.SITE_ENTRY_DELETED, ["communication"]),
    ]
    assert journal.last().before["title_fr"] == question["title_fr"]


def test_a_list_holds_twenty_entries_at_most(console):
    for n in range(20 - 6):
        SiteEntry.objects.create(kind="upcoming", title_fr=f"F{n}", text_fr="…", position=7 + n)
    refused = console.post(ENTRIES, {"kind": "upcoming", "title_fr": "Une de plus", "text_fr": "…"})
    assert refused.status_code == 400 and "kind" in refused.json()["fields"]


def test_banner_shows_between_its_dates_with_a_safe_link(
    console, client, django_capture_on_commit_callbacks
):
    for refused in (
        {"link": "javascript:alert(1)"},
        {"link": "//autre-site.example/"},
        {"link": "http://autre-site.example/"},
        {"active": True},  # sans texte
        {"starts_on": "2026-11-02", "ends_on": "2026-11-01"},
    ):
        assert console.patch(BANNER, refused).status_code == 400, refused
    today = timezone.localdate()
    banner = {"text_fr": "Inscriptions <ouvertes>", "link": "/demonstration/", "active": True}
    with django_capture_on_commit_callbacks(execute=True):
        saved = console.patch(BANNER, {**banner, "starts_on": str(today + timedelta(days=1))})
    assert saved.json()["state"] == "scheduled"
    assert 'class="sbanner"' not in client.get("/").content.decode()

    with django_capture_on_commit_callbacks(execute=True):
        assert console.patch(BANNER, {"starts_on": str(today)}).json()["state"] == "shown"
    french = client.get("/modules/").content.decode()
    assert "Inscriptions &lt;ouvertes&gt;" in french and 'href="/demonstration/">' in french
    # Anglais vide : le français ; le lien d'une page du site mène à sa version anglaise.
    english = client.get("/en/").content.decode()
    assert "Inscriptions &lt;ouvertes&gt;" in english and 'href="/en/demo/">' in english

    with django_capture_on_commit_callbacks(execute=True):
        ended = console.patch(BANNER, {"starts_on": None, "ends_on": str(today - timedelta(1))})
    assert ended.json()["state"] == "ended"
    assert 'class="sbanner"' not in client.get("/").content.decode()
    assert PlatformAuditLog.objects.filter(action=PlatformAction.SITE_BANNER_UPDATED).count() == 3

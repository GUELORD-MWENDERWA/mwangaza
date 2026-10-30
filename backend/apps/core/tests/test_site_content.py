"""Contenus du site tenus dans la console (SITE.1a, SITE.1b, SITE.5) : questions,
« Prochainement », bandeau, témoignages, écoles de référence, titres de recherche, réseaux,
saisis par la communication, au journal, montrés par le site (brouillons cachés, anglais vide :
le français, texte échappé) dès que le cache est vidé. Droits : `test_console_team.py`."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.core import site_content
from apps.core.models import (
    PlatformSettings,
    ReferenceSchool,
    SiteEntry,
    SitePage,
    SitePhoto,
)
from apps.core.models import Testimonial as SiteTestimonial  # « Test… » : pytest le collecterait
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


TESTIMONIALS = "/api/console/site/testimonials/"
REFERENCES = "/api/console/site/references/"
PAGES = "/api/console/site/pages/"
SOCIAL = "/api/console/site/social/"
LETTER = b"%PDF-1.4 accord signe"


def multipart(console, url: str, data: dict):
    return console.client.post(url, data, HTTP_HOST=console.host)


def test_a_testimonial_is_published_only_with_the_written_consent_filed(
    console, django_capture_on_commit_callbacks
):
    words = {
        "name": "Esther Kavira",
        "role": "Préfète des études",
        "school_name": "Institut Les Volcans",
        "town": "Goma",
        "quote_fr": "Je vois les recettes du jour avant de rentrer.",
    }
    refused = console.post(TESTIMONIALS, {**words, "published": True})
    assert refused.status_code == 400 and "published" in refused.json()["fields"]
    wrong = multipart(
        console, TESTIMONIALS, {**words, "consent": SimpleUploadedFile("a.pdf", b"<html>")}
    )
    assert wrong.status_code == 400  # reconnu à ses premiers octets, pas à son nom

    with django_capture_on_commit_callbacks(execute=True):
        created = multipart(
            console,
            TESTIMONIALS,
            {**words, "published": "true", "consent": SimpleUploadedFile("scan.pdf", LETTER)},
        )
    assert created.status_code == 201, created.json()
    testimonial = created.json()
    assert testimonial["has_consent"] and "consent" not in testimonial
    shown = site_content.testimonials("en")
    assert [(row["name"], row["quote"]) for row in shown] == [
        ("Esther Kavira", words["quote_fr"])  # anglais vide : le français
    ]
    # L'accord reste privé : téléchargé à la console seulement, jamais affiché.
    download = console.client.get(
        f"{TESTIMONIALS}{testimonial['id']}/consent/", HTTP_HOST=console.host
    )
    assert download["Content-Disposition"].startswith("attachment")
    assert b"".join(download.streaming_content) == LETTER
    assert SiteTestimonial.objects.get().consent.name.startswith("site/consents/")

    # Même la base refuse un témoignage publié sans accord.
    with pytest.raises(IntegrityError), transaction.atomic():
        SiteTestimonial.objects.filter(pk=testimonial["id"]).update(consent="")

    journal = PlatformAuditLog.objects.get(action=PlatformAction.SITE_TESTIMONIAL_CREATED)
    assert journal.after["consent"] is True and journal.after["published"] is True


def test_reference_schools_need_the_school_consent_and_a_secure_link(console):
    school = {"name": "Institut Les Volcans", "town": "Goma", "pupils": 812, "published": True}
    assert console.post(REFERENCES, school).status_code == 400  # sans la date de l'accord
    insecure = console.post(
        REFERENCES, {**school, "consent_on": "2026-10-20", "link": "http://x.cd"}
    )
    assert insecure.status_code == 400
    created = console.post(REFERENCES, {**school, "consent_on": "2026-10-20"})
    assert created.status_code == 201, created.json()
    console.post(REFERENCES, {**school, "name": "Mont Goma", "published": False})
    assert [row["name"] for row in site_content.reference_schools("fr")] == [school["name"]]
    for _ in range(ReferenceSchool.MAX - 2):
        console.post(REFERENCES, {**school, "published": False})
    assert console.post(REFERENCES, {**school, "published": False}).status_code == 400


def test_search_titles_and_page_photos_change_from_the_console(console):
    pages = console.get(PAGES).json()
    assert [page["key"] for page in pages] == SitePage.Key.values
    assert [page["has_photo_slot"] for page in pages] == [True, True, True, False, False]

    changed = console.patch(f"{PAGES}schools/", {"title_fr": "Logiciel scolaire à Goma"})
    assert changed.status_code == 200, changed.json()
    assert site_content.page_meta("schools", "fr") == ("Logiciel scolaire à Goma", "")
    assert site_content.page_meta("schools", "en") == ("", "")
    assert console.patch(f"{PAGES}schools/", {"title_fr": "x" * 61}).status_code == 400

    small = SitePhoto.objects.create(
        width=800, height=600, alt_fr="a", alt_en="a", credit="c", license="cc0"
    )
    assert console.patch(f"{PAGES}home/", {"photo": str(small.pk)}).status_code == 400
    assert console.patch(f"{PAGES}news/", {"photo": str(small.pk)}).status_code == 400
    journal = PlatformAuditLog.objects.get(action=PlatformAction.SITE_PAGE_UPDATED)
    assert journal.after == {"title_fr": "Logiciel scolaire à Goma"}


def test_communication_keeps_the_social_links_of_the_platform(console):
    wrong = console.patch(SOCIAL, {"facebook_url": "https://faceb00k.example/mwangaza"})
    assert wrong.status_code == 400
    link = "https://www.facebook.com/mwangazaschool"
    assert console.patch(SOCIAL, {"facebook_url": link}).json()["facebook_url"] == link
    assert PlatformSettings.load().facebook_url == link
    journal = PlatformAuditLog.objects.get(action=PlatformAction.PLATFORM_UPDATED)
    assert journal.after == {"facebook_url": link}

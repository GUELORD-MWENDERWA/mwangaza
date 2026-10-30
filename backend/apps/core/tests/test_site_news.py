"""Actualités et photothèque du site (SITE.2, SITE.3) : un article programmé reste caché jusqu'à
sa date puis paraît seul ; son adresse naît à la publication et ne change plus ; le texte est un
petit Markdown sans HTML de l'auteur ; une photo envoyée est ré-encodée sans métadonnées, gardée
avec l'accord quand un élève est reconnaissable, et ne se supprime pas tant qu'elle est montrée.
Droits : `test_console_team.py`."""

import io
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.core import markdown, site_content
from apps.core.models import Article, SitePhoto
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

ARTICLES = "/api/console/site/articles/"
PHOTOS = "/api/console/site/photos/"


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def console(api):
    member = UserFactory(is_platform_admin=True, platform_roles=["communication"])
    return api(member, host="admin.localhost")


def article(**fields) -> dict:
    return {
        "language": "fr",
        "title": "Les bulletins arrivent chez les parents",
        "summary": "Chaque parent voit le bulletin dans son espace.",
        "body": "La première période se termine.",
        **fields,
    }


def test_a_scheduled_article_appears_by_itself_at_its_date(
    console, django_capture_on_commit_callbacks
):
    soon = timezone.now() + timedelta(hours=2)
    with django_capture_on_commit_callbacks(execute=True):
        draft = console.post(ARTICLES, article()).json()
        scheduled = console.post(
            ARTICLES, article(status="published", published_at=soon.isoformat())
        ).json()
    assert draft["state"] == "draft" and draft["url"] is None
    assert scheduled["state"] == "scheduled"
    assert scheduled["url"] == "/actualites/les-bulletins-arrivent-chez-les-parents/"
    assert site_content.news("fr") == []
    assert site_content.article("fr", scheduled["slug"]) is None
    assert console.get(ARTICLES, state="scheduled").json()["count"] == 1
    assert console.get(f"{ARTICLES}counts/").json() == {
        "all": 2,
        "draft": 1,
        "scheduled": 1,
        "published": 0,
    }

    # Deux heures plus tard : la liste gardée en cache le montre, sans tâche ni cache vidé.
    later = soon + timedelta(minutes=1)
    assert [row["slug"] for row in site_content.news("fr", later)] == [scheduled["slug"]]

    # Publié maintenant (sans date) : même titre, adresse suivante ; la première ne bouge plus.
    item = f"{ARTICLES}{draft['id']}/"
    with django_capture_on_commit_callbacks(execute=True):
        published = console.patch(item, {"status": "published"}).json()
        console.patch(f"{ARTICLES}{scheduled['id']}/", {"title": "Autre titre"})
    assert published["state"] == "published"
    assert published["slug"] == "les-bulletins-arrivent-chez-les-parents-2"
    assert Article.objects.get(pk=scheduled["id"]).slug == scheduled["slug"]
    assert console.patch(item, {"language": "en"}).status_code == 400  # adresse figée
    found = site_content.article("fr", published["slug"])
    assert found["html"] == "<p>La première période se termine.</p>" and found["minutes"] == 1
    assert site_content.news_page("fr", 9) == (site_content.news("fr"), 1)

    with django_capture_on_commit_callbacks(execute=True):
        assert console.delete(item).status_code == 204
    assert site_content.article("fr", published["slug"]) is None
    actions = PlatformAuditLog.objects.filter(entity_id=draft["id"]).values_list(
        "action", flat=True
    )
    assert list(actions.order_by("created_at")) == [
        PlatformAction.SITE_ARTICLE_CREATED,
        PlatformAction.SITE_ARTICLE_PUBLISHED,
        PlatformAction.SITE_ARTICLE_DELETED,
    ]


def test_the_article_text_never_lets_html_or_scripts_through(console):
    text = (
        "Bonjour <script>alert(1)</script> **les parents**\n"
        "deuxième ligne\n\n"
        "## Ce que voit le <b>parent</b>\n"
        "- le [guide](https://mwangazaschool.com/aide/?a=1&b=2)\n"
        '- un [piège](javascript:alert(1)) et [un autre](https://x.cd/"onmouseover="a)\n'
        "- une [page](/ecoles/) et [ailleurs](//pirate.example/)"
    )
    assert markdown.render(text) == (
        "<p>Bonjour &lt;script&gt;alert(1)&lt;/script&gt; <strong>les parents</strong><br>"
        "deuxième ligne</p>\n"
        "<h2>Ce que voit le &lt;b&gt;parent&lt;/b&gt;</h2>\n"
        '<ul><li>le <a href="https://mwangazaschool.com/aide/?a=1&amp;b=2" rel="noopener">'
        "guide</a></li>"
        "<li>un [piège](javascript:alert(1)) et "
        '<a href="https://x.cd/&quot;onmouseover=&quot;a" rel="noopener">un autre</a></li>'
        '<li>une <a href="/ecoles/">page</a> et [ailleurs](//pirate.example/)</li></ul>'
    )
    # L'aperçu de la console passe par le même code.
    preview = console.post(f"{ARTICLES}preview/", {"body": "<i>x</i>"}).json()
    assert preview["html"] == "<p>&lt;i&gt;x&lt;/i&gt;</p>" and preview["minutes"] == 1


def jpeg(width: int, height: int) -> SimpleUploadedFile:
    """Photo d'appareil avec ses métadonnées (modèle, auteur, position GPS)."""
    exif = Image.Exif()
    exif[0x0110] = "Appareil"
    exif[0x013B] = "Photographe"
    exif.get_ifd(0x8825)[2] = (1.0, 40.0, 0.0)  # latitude
    output = io.BytesIO()
    Image.new("RGB", (width, height), "#1f4e9c").save(output, "JPEG", exif=exif)
    return SimpleUploadedFile("IMG_2041.jpg", output.getvalue(), content_type="image/jpeg")


PHOTO = {
    "alt_fr": "Élèves en uniforme dans la cour",
    "alt_en": "Pupils in uniform in the schoolyard",
    "credit": "Institut Les Volcans",
    "license": "cc_by_sa",
}


def send(console, data: dict):
    return console.client.post(PHOTOS, data, HTTP_HOST=console.host)


def test_a_photo_is_cleaned_kept_with_its_consent_and_protected_while_shown(
    console, client, django_capture_on_commit_callbacks
):
    assert send(console, {**PHOTO, "image": jpeg(500, 400)}).status_code == 400  # trop petite
    fake = SimpleUploadedFile("x.jpg", b"<svg onload=alert(1)>")
    assert send(console, {**PHOTO, "image": fake}).status_code == 400
    pupils = {**PHOTO, "recognizable": "true", "image": jpeg(2400, 1600)}
    refused = send(console, pupils)
    assert refused.status_code == 400 and "consent" in refused.json()["fields"]
    assert not SitePhoto.objects.exists()

    letter = SimpleUploadedFile("accord.pdf", b"%PDF-1.4 accord")
    created = send(console, {**pupils, "image": jpeg(2400, 1600), "consent": letter})
    assert created.status_code == 201, created.json()
    photo = created.json()
    assert (photo["width"], photo["height"], photo["uses"]) == (1600, 1067, 0)

    for url, width in ((photo["url"], 1600), (photo["small_url"], 600)):
        response = client.get(url)
        assert response["Content-Type"] == "image/webp"
        with Image.open(io.BytesIO(b"".join(response.streaming_content))) as image:
            assert image.format == "WEBP" and image.width == width
            assert not image.getexif() and "exif" not in image.info and "xmp" not in image.info

    with django_capture_on_commit_callbacks(execute=True):
        console.post(ARTICLES, article(photo=photo["id"]))
    assert console.get(PHOTOS).json()["results"][0]["uses"] == 1
    item = f"{PHOTOS}{photo['id']}/"
    assert console.delete(item).status_code == 400  # montrée par un article

    Article.objects.all().delete()
    files = [SitePhoto.objects.get().large.path, SitePhoto.objects.get().consent.path]
    with django_capture_on_commit_callbacks(execute=True):
        assert console.delete(item).status_code == 204
    assert client.get(photo["url"]).status_code == 404
    assert not any(Path(path).exists() for path in files)
    assert (
        PlatformAuditLog.objects.filter(
            action__in=[PlatformAction.SITE_PHOTO_ADDED, PlatformAction.SITE_PHOTO_DELETED]
        ).count()
        == 2
    )


def test_public_news_pages_show_only_published_articles_in_their_language(client):
    now = timezone.now()
    base = {"summary": "Résumé", "body": "Un texte.", "status": Article.Status.PUBLISHED}
    Article.objects.create(
        language="fr", title="Paru", slug="paru", published_at=now - timedelta(days=1), **base
    )
    Article.objects.create(
        language="fr", title="Bientôt", slug="bientot", published_at=now + timedelta(days=2), **base
    )
    Article.objects.create(language="en", title="Out", slug="out", published_at=now, **base)
    Article.objects.create(
        language="fr", title="Brouillon", slug="brouillon", summary="r", body="t"
    )

    listing = client.get("/actualites/").content.decode()
    assert "Paru" in listing and "Bientôt" not in listing and "Out" not in listing
    assert client.get("/actualites/paru/").status_code == 200
    # Programmé, brouillon, autre langue : introuvable.
    for path in ("/actualites/bientot/", "/actualites/brouillon/", "/actualites/out/"):
        assert client.get(path).status_code == 404
    # L'article n'existe que dans sa langue : pas de lien alterné vers une page absente.
    page = client.get("/actualites/paru/").content.decode()
    assert 'hreflang="en" href' not in page.replace('hreflang="en" lang="en"', "")
    sitemap = client.get("/sitemap.xml").content.decode()
    assert "/actualites/paru/" in sitemap and "bientot" not in sitemap

"""Contenus du site public qui changent plus souvent que la mise en page (WEB.1b).

Tenus dans la console par la communication (SITE.1a à SITE.3) : questions fréquentes,
« Prochainement », bandeau, témoignages, écoles de référence, titres de recherche et photos des
pages, actualités. Le site lit tout le contenu publié en une seule fois, gardé dans le cache et
vidé à chaque changement (`clear`, après la transaction) : une page publique ne fait aucune
requête de plus. La liste des actualités est gardée de même, une par langue, articles programmés
compris : la date de publication est comparée à chaque lecture, un article paraît donc à son heure
sans tâche de fond. Reste ici, relu dans une PR : ce que fait chaque module (il décrit le
logiciel)."""

from datetime import date, datetime

from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core import markdown
from apps.core.models import (
    Article,
    Partner,
    ReferenceSchool,
    SiteBanner,
    SiteEntry,
    SitePage,
    SitePhoto,
    SitePlan,
    Testimonial,
)

CACHE_KEY = "site:content"
NEWS_KEY = "site:news:{lang}"
CACHE_TIMEOUT = 24 * 3600  # vidé à chaque changement ; la durée ne sert qu'à libérer la mémoire
ENTRY_FIELDS = ("kind", "title_fr", "title_en", "text_fr", "text_en")
BANNER_FIELDS = ("text_fr", "text_en", "link", "starts_on", "ends_on")
TESTIMONIAL_FIELDS = (
    "name",
    "role",
    "school_name",
    "town",
    "quote_fr",
    "quote_en",
    "logo_id",
    "is_example",
)
REFERENCE_FIELDS = ("name", "town", "pupils", "link", "logo_id", "is_example")
PLAN_FIELDS = (
    "name_fr",
    "name_en",
    "tagline_fr",
    "tagline_en",
    "price",
    "currency",
    "period",
    "features_fr",
    "features_en",
    "highlighted",
)
PARTNER_FIELDS = ("name", "link", "logo_id")
PAGE_FIELDS = ("key", "title_fr", "title_en", "description_fr", "description_en", "photo_id")
PHOTO_FIELDS = ("id", "width", "height", "alt_fr", "alt_en")
ARTICLE_FIELDS = (
    "slug",
    "title",
    "summary",
    "published_at",
    "updated_at",
    "author_name",
    "photo_id",
)
NEWS_PER_PAGE = 10
NEWS_PATHS = {"fr": "/actualites/", "en": "/en/news/"}


def article_path(lang: str, slug: str) -> str:
    return f"{NEWS_PATHS[lang]}{slug}/"


def photo_url(photo_id, width: int = 1600) -> str:
    """Adresse d'une photo de la photothèque (`views.site_photo`), sans requête : sous `/api/`,
    elle répond aussi bien au site qu'à la console."""
    return f"/api/platform/photos/{photo_id}-{width}.webp"


def _photos(ids) -> dict:
    ids = {pk for pk in ids if pk}
    if not ids:
        return {}
    return {row["id"]: row for row in SitePhoto.objects.filter(pk__in=ids).values(*PHOTO_FIELDS)}


def _load() -> dict:
    entries: dict[str, list[dict]] = {kind: [] for kind in SiteEntry.Kind.values}
    for entry in SiteEntry.objects.filter(published=True).values(*ENTRY_FIELDS):
        entries[entry["kind"]].append(entry)
    banner = SiteBanner.objects.filter(pk=1, active=True).exclude(text_fr="")
    testimonials = list(Testimonial.objects.filter(published=True).values(*TESTIMONIAL_FIELDS))
    references = list(ReferenceSchool.objects.filter(published=True).values(*REFERENCE_FIELDS))
    plans = list(SitePlan.objects.filter(published=True).values(*PLAN_FIELDS))
    partners = list(Partner.objects.filter(published=True).values(*PARTNER_FIELDS))
    pages = {row["key"]: row for row in SitePage.objects.values(*PAGE_FIELDS)}
    used = [row["logo_id"] for row in testimonials + references + partners]
    return {
        "entries": entries,
        "banner": banner.values(*BANNER_FIELDS).first(),
        "testimonials": testimonials,
        "references": references,
        "plans": plans,
        "partners": partners,
        "pages": pages,
        "photos": _photos(used + [row["photo_id"] for row in pages.values()]),
    }


def published() -> dict:
    """Tout le contenu publié : `entries` par sorte (dans l'ordre), `banner` (ou `None`)."""
    content = cache.get(CACHE_KEY)
    if content is None:
        content = _load()
        cache.set(CACHE_KEY, content, CACHE_TIMEOUT)
    return content


def clear() -> None:
    cache.delete_many([CACHE_KEY, *(NEWS_KEY.format(lang=lang) for lang in Article.Language)])


def _in(row: dict, field: str, lang: str) -> str:
    """Le texte dans la langue de la page ; l'anglais vide : le français."""
    return row.get(f"{field}_{lang}") or row[f"{field}_fr"]


def entries(kind: str, lang: str) -> list[tuple[str, str]]:
    """(Titre, texte) publiés d'une sorte, dans la langue de la page."""
    return [
        (_in(row, "title", lang), _in(row, "text", lang)) for row in published()["entries"][kind]
    ]


def banner(lang: str, today: date) -> dict | None:
    """Le bandeau à montrer aujourd'hui (texte et lien), ou `None`."""
    row = published()["banner"]
    if row is None or (row["starts_on"] and today < row["starts_on"]):
        return None
    if row["ends_on"] and today > row["ends_on"]:
        return None
    return {"text": _in(row, "text", lang), "link": row["link"]}


def _photo(photo_id, lang: str) -> dict | None:
    row = published()["photos"].get(photo_id)
    if row is None:
        return None
    return {
        "url": photo_url(row["id"]),
        "small": photo_url(row["id"], 600),
        "alt": _in(row, "alt", lang),
        "width": row["width"],
        "height": row["height"],
    }


def testimonials(lang: str) -> list[dict]:
    """Témoignages publiés (accord déposé), dans l'ordre ; vide : la section est cachée."""
    return [
        {**row, "quote": _in(row, "quote", lang), "logo": _photo(row["logo_id"], lang)}
        for row in published()["testimonials"]
    ]


def reference_schools(lang: str) -> list[dict]:
    """Écoles de référence publiées (accord de l'école daté) ; vide : la section est cachée."""
    return [{**row, "logo": _photo(row["logo_id"], lang)} for row in published()["references"]]


def plans(lang: str) -> list[dict]:
    """Formules publiées, dans l'ordre ; le prix reste en centimes (le site le formate)."""
    return [
        {
            **row,
            "name": _in(row, "name", lang),
            "tagline": _in(row, "tagline", lang),
            "features": [
                line.strip() for line in _in(row, "features", lang).splitlines() if line.strip()
            ],
        }
        for row in published()["plans"]
    ]


def partners(lang: str) -> list[dict]:
    """Partenaires publiés (bande qui défile) ; vide : la section est cachée."""
    return [{**row, "logo": _photo(row["logo_id"], lang)} for row in published()["partners"]]


def figures() -> list[tuple[int, str]]:
    """Chiffres des écoles de référence publiées : (valeur, clé) pour `schools`, `pupils` et
    `towns`, ou rien sans école. Les noms ne sont jamais montrés par cette bande."""
    rows = published()["references"]
    if not rows:
        return []
    return [
        (len(rows), "schools"),
        (sum(row["pupils"] for row in rows), "pupils"),
        (len({row["town"].casefold() for row in rows}), "towns"),
    ]


def page_meta(key: str, lang: str) -> tuple[str, str]:
    """Titre et description de recherche réglés dans la console ; `""` : le texte du logiciel."""
    row = published()["pages"].get(key)
    if row is None:
        return "", ""
    return row[f"title_{lang}"], row[f"description_{lang}"]


def page_photo(key: str, lang: str) -> dict | None:
    """Photo du haut de la page choisie dans la photothèque ; `None` : celle du site."""
    row = published()["pages"].get(key)
    return _photo(row["photo_id"], lang) if row else None


def _news(lang: str) -> list[dict]:
    key = NEWS_KEY.format(lang=lang)
    rows = cache.get(key)
    if rows is None:
        articles = Article.objects.filter(language=lang, status=Article.Status.PUBLISHED)
        rows = list(
            articles.order_by("-published_at").values(
                *ARTICLE_FIELDS, "photo__alt_fr", "photo__alt_en", "photo__width", "photo__height"
            )
        )
        cache.set(key, rows, CACHE_TIMEOUT)
    return rows


def news_photo(photo_id, alt: dict, width: int, height: int, lang: str) -> dict | None:
    """Photo d'un article (dans la photothèque), sans requête de plus."""
    if not photo_id:
        return None
    return {
        "url": photo_url(photo_id),
        "small": photo_url(photo_id, 600),
        "alt": alt.get(lang) or alt["fr"],
        "width": width,
        "height": height,
    }


def news(lang: str, now: datetime | None = None) -> list[dict]:
    """Articles parus dans cette langue (date de publication passée), les plus récents d'abord,
    avec leur adresse et leur photo ; pour la liste paginée, l'accueil et le `sitemap.xml`."""
    now = now or timezone.now()
    return [
        {
            **row,
            "path": article_path(lang, row["slug"]),
            "photo": news_photo(
                row["photo_id"],
                {"fr": row["photo__alt_fr"], "en": row["photo__alt_en"]},
                row["photo__width"],
                row["photo__height"],
                lang,
            ),
        }
        for row in _news(lang)
        if row["published_at"] <= now
    ]


def news_page(lang: str, number: int) -> tuple[list[dict], int]:
    """Une page de la liste (10 articles) et le nombre de pages ; un numéro hors liste : la
    dernière page."""
    rows = news(lang)
    pages = max(1, -(-len(rows) // NEWS_PER_PAGE))
    number = min(max(number, 1), pages)
    start = (number - 1) * NEWS_PER_PAGE
    return rows[start : start + NEWS_PER_PAGE], pages


def article(lang: str, slug: str) -> dict | None:
    """Un article paru, texte mis en forme ; `None` : absent, brouillon ou pas encore paru."""
    found = (
        Article.objects.filter(
            language=lang,
            slug=slug,
            status=Article.Status.PUBLISHED,
            published_at__lte=timezone.now(),
        )
        .select_related("photo")
        .first()
    )
    if found is None:
        return None
    return {
        "slug": found.slug,
        "title": found.title,
        "summary": found.summary,
        "published_at": found.published_at,
        "updated_at": found.updated_at,
        "author_name": found.author_name,
        "html": markdown.render(found.body),
        "minutes": markdown.reading_minutes(found.body),
        "photo": news_photo(
            found.photo_id,
            {"fr": found.photo.alt_fr, "en": found.photo.alt_en},
            found.photo.width,
            found.photo.height,
            lang,
        )
        if found.photo_id
        else None,
    }


# Ce que fait chaque module de `accounts/modules.py` (même clé). Un module ajouté au catalogue
# apparaît seul sur la page Modules, avec son nom ; ses points s'ajoutent ici.
MODULE_ICONS = {
    "students": "students",
    "finance": "cash",
    "academics": "book",
    "timetable": "calendar",
    "portal": "users",
    "communication": "megaphone",
    "notifications": "bell",
    "offline": "wifioff",
}
MODULE_FEATURES = {
    "students": (
        _("Excel import with an error report"),
        _("Families, siblings and family code"),
        _("Registration forms and class lists"),
    ),
    "finance": (
        _("Fee scales in USD and FC, instalments, discounts"),
        _("Cash desk, 58 / 80 mm or A4 receipts, cash counts"),
        _("Unpaid fees, statements, approved cancellations"),
    ),
    "academics": (
        _("Courses, maximum marks and marks by term"),
        _("Conduct, deliberation, resits"),
        _("Report cards with an authenticity QR code, mark sheets, summaries"),
    ),
    "timetable": (
        _("Time grid with breaks, short days and two shifts"),
        _("Rooms, workshops and laboratories"),
        _("Hours of each class compared with its week"),
    ),
    "portal": (
        _("Payments, receipts and due dates"),
        _("Notices, calendar, summons"),
        _("Several children, several schools"),
    ),
    "communication": (
        _("To families or to staff"),
        _("Printable circular"),
        _("School calendar"),
    ),
    "notifications": (
        _("Payment received alert on the phone"),
        _("Due date reminder to parents, if the school wants it"),
        _("Cash desks left open"),
    ),
    "offline": (
        _("Cash desk and student search offline"),
        _("Sent automatically, never twice"),
        _("PIN code on known devices"),
    ),
}

# Écoles présentées sur l'accueil (faits publics, logo et photo avec l'accord de l'école).
# `quote` : les vrais mots d'une personne de l'école, avec son nom, sa fonction et l'accord écrit
# de l'école ; jamais inventés. Vide : la carte s'affiche sans citation.
REFERENCES = (
    {
        "name": "ITIG Don Bosco Goma",
        "kind": _("Industrial technical institute · Goma, North Kivu"),
        "logo": "core/site/photos/itig-logo.webp",
        "photo": "itig-cour",
        "photo_alt": _(
            "ITIG Don Bosco Goma students gathered in the courtyard, in front of the flag"
        ),
        "facts": (
            (_("1,000+"), _("students")),
            ("4", _("technical options")),
            ("1981", _("founded")),
        ),
        "quote": "",
        "quote_by": "",
    },
)

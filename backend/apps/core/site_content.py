"""Contenus du site public qui changent plus souvent que la mise en page (WEB.1b).

Tenus dans la console par la communication (SITE.1a) : questions fréquentes, « Prochainement »,
bandeau (`SiteEntry`, `SiteBanner`). Le site lit tout le contenu publié en une seule fois, gardé
dans le cache et vidé à chaque changement (`clear`, après la transaction) : une page publique ne
fait aucune requête de plus. Restent ici, relus dans une PR : ce que fait chaque module (il décrit
le logiciel) et les écoles de référence (console en SITE.1b)."""

from datetime import date

from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from apps.core.models import SiteBanner, SiteEntry

CACHE_KEY = "site:content"
CACHE_TIMEOUT = 24 * 3600  # vidé à chaque changement ; la durée ne sert qu'à libérer la mémoire
ENTRY_FIELDS = ("kind", "title_fr", "title_en", "text_fr", "text_en")
BANNER_FIELDS = ("text_fr", "text_en", "link", "starts_on", "ends_on")


def _load() -> dict:
    entries: dict[str, list[dict]] = {kind: [] for kind in SiteEntry.Kind.values}
    for entry in SiteEntry.objects.filter(published=True).values(*ENTRY_FIELDS):
        entries[entry["kind"]].append(entry)
    banner = SiteBanner.objects.filter(pk=1, active=True).exclude(text_fr="")
    return {"entries": entries, "banner": banner.values(*BANNER_FIELDS).first()}


def published() -> dict:
    """Tout le contenu publié : `entries` par sorte (dans l'ordre), `banner` (ou `None`)."""
    content = cache.get(CACHE_KEY)
    if content is None:
        content = _load()
        cache.set(CACHE_KEY, content, CACHE_TIMEOUT)
    return content


def clear() -> None:
    cache.delete(CACHE_KEY)


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

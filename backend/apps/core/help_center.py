"""Centre d'aide (AIDE.1) : articles courts, écran par écran, écrits en Markdown dans le dépôt
(`help/<langue>/<application>/<clé>.md`), et « Quoi de neuf » (`help/<langue>/whats-new/<date>.md`).
Les mêmes textes servent au site (`/aide/`, `help_views.py`), au panneau « Aide » des applications
(API `/api/help/`) et aux guides PDF (commande `help_guides`). Lus une fois par processus : ni
table, ni écriture ; la recherche se fait en mémoire, sans accents ni majuscules.

Un article : un en-tête `nom: valeur` jusqu'à la première ligne vide — `title`, `summary` et
`groups` (rubriques, la première est la sienne) obligatoires ; `slug` (adresse dans cette langue,
sinon la clé), `roles` (rôles de départ, `accounts/roles.py`), `order` (place dans la rubrique) et
`updated` (AAAA-MM-JJ) facultatifs — puis le texte (`markdown.py`). Une ligne `---` met à part les
questions fréquentes, absentes des guides PDF. La clé (nom du fichier, en anglais) est la même
dans les deux langues : liens `aide:<clé>`, table écran → article des applications.

« Quoi de neuf » : une phrase de résumé, puis une section par application (`[gestion]`,
`[portail]`) en liste. Mode d'emploi pour qui écrit : `help/README.md`."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from PIL import Image

from apps.accounts.roles import STARTER_ROLES
from apps.core import markdown

HELP_DIR = Path(__file__).parent / "help"
CAPTURES_DIR = Path(__file__).parent / "static" / "core" / "aide"
LANGS = ("fr", "en")
APPS = {
    "gestion": pgettext_lazy("application", "Management"),
    "portail": _("Parent space"),
    "console": _("Platform console"),
}
# Sur le site et dans le sitemap : la console garde ses articles pour l'équipe de la plateforme.
PUBLIC_APPS = ("gestion", "portail")
# Rubriques, dans leur ordre : nom et une ligne pour qui elles sont.
GROUPS = {
    "start": (_("First steps"), _("Signing in, choosing your school, working offline.")),
    "direction": (_("Management"), _("Head of studies, director of studies, promoter.")),
    "secretariat": (_("Secretariat"), _("Students, families, enrolments and documents.")),
    "cash": (_("Cash desk and accounting"), _("Collecting, closing, following what is owed.")),
    "teachers": (_("Teachers"), _("Timetable, marks, mark sheets.")),
    "parents": (_("Parents"), _("The parent space on the phone.")),
    "console": (_("Platform console"), _("Schools, billing, site and support.")),
}
# « Souvent cherché » de l'accueil du centre d'aide : une liste choisie, aucune mesure de lecture.
POPULAR = ("take-payment", "print-class-report-cards", "forgot-password", "activate-parent-account")
HOME = {"fr": "/aide/", "en": "/en/help/"}
SEARCH = {"fr": "/aide/recherche/", "en": "/en/help/search/"}
NEWS = {"fr": "/aide/nouveautes/", "en": "/en/help/whats-new/"}
RESERVED = {"recherche", "search", "nouveautes", "whats-new"}
WHATS_NEW = "whats-new"
HEADER = {"title", "slug", "summary", "groups", "roles", "order", "updated"}
REQUIRED = {"title", "summary", "groups"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECTION = re.compile(r"^\[([a-z]+)\]$")
QUESTIONS = re.compile(r"^---\s*$", re.MULTILINE)
MARKS = re.compile(r"^(?:#{2,3}|[-*]|\d{1,2}\.|>) *")
MAX_RESULTS = 20
MIN_WORD = 2
EXCERPT = 160


def fold(text: str) -> str:
    """Le texte sans accents ni majuscules, pour comparer (« Reçu » → « recu »)."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def site_url() -> str:
    """Adresse du site public de la plateforme (`SITE_URL`)."""
    return settings.SITE_URL.rstrip("/")


@dataclass(frozen=True)
class Article:
    key: str
    lang: str
    app: str
    slug: str
    title: str
    summary: str
    groups: tuple[str, ...]
    roles: tuple[str, ...]
    order: int
    updated: date | None
    body: str
    questions: str
    # Titre, résumé et texte sans balises, repliés (`fold`) : la recherche.
    plain: str = field(repr=False)
    folded: tuple[str, str, str] = field(repr=False)

    @property
    def group(self) -> str:
        return self.groups[0]

    @property
    def public(self) -> bool:
        return self.app in PUBLIC_APPS

    @property
    def path(self) -> str:
        """Adresse sur le site (articles de la Gestion et du Portail)."""
        return f"{HOME[self.lang]}{self.slug}/"

    @property
    def minutes(self) -> int:
        return markdown.reading_minutes(f"{self.body}\n{self.questions}")

    @property
    def app_label(self) -> str:
        return str(APPS[self.app])

    @property
    def group_label(self) -> str:
        return group_label(self.group)

    @property
    def audience(self) -> str:
        """Pour qui, sous les « Premiers pas » : son autre rubrique, sinon tout le monde."""
        return group_label(self.groups[1]) if len(self.groups) > 1 else str(_("Everyone"))

    def role_labels(self) -> list[str]:
        return [str(STARTER_ROLES[role].label) for role in self.roles]


@dataclass(frozen=True)
class Entry:
    """Une mise en ligne de « Quoi de neuf » : un résumé, une liste par application."""

    day: date
    lang: str
    summary: str
    sections: dict[str, str]

    def html(self, app: str) -> SafeString:
        return markdown.render(self.sections.get(app, ""))


@dataclass(frozen=True)
class Library:
    articles: dict[str, dict[str, Article]]  # langue → clé → article
    slugs: dict[str, dict[str, Article]]  # langue → adresse → article
    entries: dict[str, list[Entry]]  # langue → mises en ligne, la plus récente d'abord


def _items(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _plain(text: str) -> str:
    """Le texte lu par la recherche et les extraits : sans captures, marques ni adresses."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if markdown.PHOTO.match(line) or markdown.CAPTURE.match(line):
            continue
        line = markdown.LINK.sub(r"\1", MARKS.sub("", line)).replace("**", "")
        if line:
            lines.append(line)
    return " ".join(lines)


def _header(file: Path, head: str) -> dict[str, str]:
    meta = {}
    for line in head.splitlines():
        name, sep, value = line.partition(":")
        if not sep or name.strip() not in HEADER:
            raise ValueError(f"{file} : en-tête inconnu ou mal écrit : {line!r}")
        meta[name.strip()] = value.strip()
    missing = REQUIRED - {name for name, value in meta.items() if value}
    if missing:
        raise ValueError(f"{file} : en-tête incomplet ({', '.join(sorted(missing))})")
    return meta


def _article(file: Path, lang: str, app: str) -> Article:
    head, _sep, text = file.read_text(encoding="utf-8").partition("\n\n")
    meta = _header(file, head)
    groups, roles = _items(meta["groups"]), _items(meta.get("roles", ""))
    slug = meta.get("slug") or file.stem
    if not SLUG.match(file.stem) or not SLUG.match(slug) or slug in RESERVED:
        raise ValueError(f"{file} : clé ou adresse refusée ({file.stem}, {slug})")
    if not groups or set(groups) - set(GROUPS) or set(roles) - set(STARTER_ROLES):
        raise ValueError(f"{file} : rubrique ou rôle inconnu ({meta['groups']} ; {roles})")
    body, questions = (*QUESTIONS.split(text, maxsplit=1), "")[:2]
    plain = _plain(f"{body}\n{questions}")
    return Article(
        key=file.stem,
        lang=lang,
        app=app,
        slug=slug,
        title=meta["title"],
        summary=meta["summary"],
        groups=groups,
        roles=roles,
        order=int(meta.get("order") or 100),
        updated=date.fromisoformat(meta["updated"]) if meta.get("updated") else None,
        body=body.strip(),
        questions=questions.strip(),
        plain=plain,
        folded=(fold(meta["title"]), fold(meta["summary"]), fold(plain)),
    )


def _entry(file: Path, lang: str) -> Entry:
    summary: list[str] = []
    sections: dict[str, list[str]] = {}
    current = None
    for raw in file.read_text(encoding="utf-8").splitlines():
        section = SECTION.match(raw.strip())
        if section:
            current = section.group(1)
            if current not in APPS:
                raise ValueError(f"{file} : application inconnue [{current}]")
            sections[current] = []
        elif current:
            sections[current].append(raw)
        elif raw.strip():
            summary.append(raw.strip())
    return Entry(
        day=date.fromisoformat(file.stem),
        lang=lang,
        summary=" ".join(summary),
        sections={app: "\n".join(lines).strip() for app, lines in sections.items()},
    )


@cache
def _load(root: Path) -> Library:
    articles: dict[str, dict[str, Article]] = {}
    slugs: dict[str, dict[str, Article]] = {}
    entries: dict[str, list[Entry]] = {}
    for lang in LANGS:
        found = [
            _article(file, lang, app)
            for app in APPS
            for file in sorted((root / lang / app).glob("*.md"))
        ]
        articles[lang] = {}
        slugs[lang] = {}
        for article in sorted(found, key=lambda a: (a.order, a.title)):
            if article.key in articles[lang] or article.slug in slugs[lang]:
                raise ValueError(f"{lang}/{article.app}/{article.key} : clé ou adresse en double")
            articles[lang][article.key] = article
            slugs[lang][article.slug] = article
        news = (root / lang / WHATS_NEW).glob("*.md")
        entries[lang] = sorted((_entry(file, lang) for file in news), key=lambda e: e.day)[::-1]
    return Library(articles=articles, slugs=slugs, entries=entries)


def library() -> Library:
    """Tous les textes, lus au premier appel du processus (le serveur de développement se relance
    quand un fichier change : `apps.py`)."""
    return _load(HELP_DIR)


def article(lang: str, key: str) -> Article | None:
    return library().articles[lang].get(key)


def by_slug(lang: str, slug: str) -> Article | None:
    """L'article du site à cette adresse (la console n'y est pas)."""
    found = library().slugs[lang].get(slug)
    return found if found and found.public else None


def articles(lang: str, apps=PUBLIC_APPS) -> list[Article]:
    return [a for a in library().articles[lang].values() if a.app in apps]


def counterpart(found: Article) -> Article | None:
    """Le même article dans l'autre langue."""
    return article("en" if found.lang == "fr" else "fr", found.key)


@cache
def _sizes(root: Path, lang: str) -> dict[str, tuple[int, int]]:
    sizes = {}
    for file in sorted((root / lang).glob("*.webp")):
        with Image.open(file) as image:
            sizes[file.stem] = image.size
    return sizes


def captures(lang: str) -> dict[str, dict]:
    """Les captures de l'aide (`static/core/aide/<langue>/<nom>.webp`, `make captures-aide`) :
    adresse et taille, pour `markdown.render`."""
    return {
        name: {"url": static(f"core/aide/{lang}/{name}.webp"), "width": w, "height": h}
        for name, (w, h) in _sizes(CAPTURES_DIR, lang).items()
    }


def site_links(lang: str, absolute: bool = False) -> dict[str, str]:
    """Adresse de chaque article du site ; `absolute` : depuis une application."""
    base = site_url() if absolute else ""
    return {a.key: base + a.path for a in articles(lang)}


def render(found: Article, links: dict[str, str], shots: dict | None = None, questions=True):
    """Le texte de l'article en HTML sûr (`markdown.render`) ; sans les questions fréquentes pour
    les guides PDF."""
    shots = captures(found.lang) if shots is None else shots
    html = markdown.render(found.body, captures=shots, links=links)
    if questions and found.questions:
        html += markdown.render(found.questions, captures=shots, links=links)
    return html


def group_label(key: str) -> str:
    return str(GROUPS[key][0])


def groups(lang: str, apps=PUBLIC_APPS) -> list[dict]:
    """Les rubriques qui ont des articles, dans leur ordre ; un article peut être dans plusieurs."""
    rows = articles(lang, apps)
    found = []
    for key, (label, text) in GROUPS.items():
        members = [a for a in rows if key in a.groups]
        if members:
            found.append({"key": key, "label": label, "text": text, "articles": members})
    return found


def popular(lang: str) -> list[Article]:
    return [a for key in POPULAR if (a := article(lang, key)) and a.public]


def entries(lang: str, app: str | None = None) -> list[Entry]:
    """Les mises en ligne, la plus récente d'abord ; `app` : celles qui ont sa section."""
    rows = library().entries[lang]
    return [e for e in rows if app in e.sections] if app else rows


# Recherche : mots de deux lettres au moins, tous présents (titre, résumé ou texte), le titre
# d'abord ; même fonction pour le site et le panneau « Aide ».


def words(query: str) -> list[str]:
    return list(dict.fromkeys(w for w in re.findall(r"\w+", fold(query)) if len(w) >= MIN_WORD))[:8]


def _pattern(terms: list[str]) -> re.Pattern:
    alternatives = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternatives})\w*")


def _folded(text: str) -> tuple[str, list[int]]:
    """Le texte replié, et pour chaque signe replié, sa place dans le texte d'origine."""
    chars, where = [], []
    for index, char in enumerate(text):
        for folded in fold(char):
            chars.append(folded)
            where.append(index)
    return "".join(chars), where


def highlight(text: str, terms: list[str]) -> SafeString:
    """Le texte échappé, les mots trouvés dans `<mark>`."""
    folded, where = _folded(text)
    pieces, last = [], 0
    for match in _pattern(terms).finditer(folded) if terms else ():
        start, end = where[match.start()], where[match.end() - 1] + 1
        pieces += [escape(text[last:start]), f"<mark>{escape(text[start:end])}</mark>"]
        last = end
    pieces.append(escape(text[last:]))
    # Sûr : tout le texte passe par `escape`.
    return mark_safe(markdown.french_spaces("".join(pieces)))


def _excerpt(found: Article, terms: list[str]) -> str:
    """Le résumé s'il contient un mot cherché, sinon un passage du texte autour du premier mot."""
    pattern = _pattern(terms)
    if pattern.search(found.folded[1]) or not pattern.search(found.folded[2]):
        return found.summary
    folded, where = _folded(found.plain)
    start = where[pattern.search(folded).start()]
    begin = found.plain.rfind(" ", 0, max(start - EXCERPT // 3, 0)) + 1
    end = found.plain.find(" ", begin + EXCERPT)
    end = len(found.plain) if end == -1 else end
    return (
        ("… " if begin else "") + found.plain[begin:end] + (" …" if end < len(found.plain) else "")
    )


def search(lang: str, query: str, apps=PUBLIC_APPS) -> list[dict]:
    """Les articles qui contiennent tous les mots, 20 au plus : article, titre et extrait
    surlignés."""
    terms = words(query)
    if not terms:
        return []
    scored = []
    for found in articles(lang, apps):
        title, summary, plain = found.folded
        score = 0
        for term in terms:
            word = re.compile(rf"\b{re.escape(term)}")
            weight = next(
                (w for w, t in ((100, title), (10, summary), (1, plain)) if word.search(t)), 0
            )
            if not weight:
                break
            score += weight
        else:
            scored.append((-score, found.order, found.title, found))
    return [
        {
            "article": found,
            "title": highlight(found.title, terms),
            "excerpt": highlight(_excerpt(found, terms), terms),
        }
        for *_rank, found in sorted(scored, key=lambda row: row[:3])[:MAX_RESULTS]
    ]

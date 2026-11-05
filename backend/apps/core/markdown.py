"""Petit Markdown des actualités du site (SITE.2) et du centre d'aide (AIDE.1), sans dépendance :
paragraphes (une ligne vide les sépare, un retour à la ligne est gardé), intertitres (`## `,
`### `), listes (`- `) et listes numérotées (`1. `), encadré (lignes qui commencent par `> `), gras
(`**…**`), photos de la photothèque (`![légende](photo:<id>)`) et captures de l'aide
(`![légende](capture:<nom>)`), seules sur leur ligne, et liens (`[texte](https://…)`, une page du
site `/…`, un article de l'aide `aide:<clé>`). Tout le texte est **échappé d'abord** : aucun HTML
de l'auteur n'arrive dans la page ; seules les balises d'ici sont écrites. Le site, l'aperçu de la
console, le panneau « Aide » et les guides PDF passent par la même fonction."""

import math
import re

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

HEADINGS = {"## ": "h2", "### ": "h3"}
BULLET = re.compile(r"^[-*] +")
NUMBERED = re.compile(r"^\d{1,2}\. +")
TIP = re.compile(r"^> ?")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
# Après échappement : les guillemets sont devenus `&quot;`, une adresse ne peut pas sortir de
# l'attribut ; espaces et parenthèses refusés dans l'adresse.
LINK = re.compile(r"\[([^\]\n]+)\]\(([^()\s]+)\)")
WORDS_PER_MINUTE = 200
# Une photo de la photothèque, seule sur sa ligne ; la légende est facultative. L'adresse vient de
# la photothèque (`photos`), jamais du texte : une photo inconnue ne laisse rien.
PHOTO = re.compile(r"^!\[([^\]\n]*)\]\(photo:([0-9a-f-]{36})\)$")
# Une capture de l'aide (`help_center.py`) : même règle, une capture inconnue ne laisse rien.
CAPTURE = re.compile(r"^!\[([^\]\n]*)\]\(capture:([a-z0-9-]{1,60})\)$")
HELP_LINK = "aide:"
# Typographie française : jamais de retour à la ligne entre « et le mot, ni avant : ; ? ! ».
FRENCH_SPACE = re.compile(r" ([:;?!»])|(«) ")


def french_spaces(text: str) -> str:
    return FRENCH_SPACE.sub(
        lambda match: f"\u00a0{match.group(1)}" if match.group(1) else f"{match.group(2)}\u00a0",
        text,
    )


def _safe_target(url: str) -> bool:
    """Une adresse `https://` ou une page du site (`/…`, jamais `//autre-site`)."""
    return url.startswith("https://") or (url.startswith("/") and not url.startswith("//"))


def _link(match: re.Match, links: dict[str, str] | None) -> str:
    text, url = match.group(1), match.group(2)
    if url.startswith(HELP_LINK):
        # Article de l'aide : son adresse vient de `links` (clé → adresse) ; absent (autre
        # application, article retiré), le texte reste sans lien. `data-help` : le panneau
        # « Aide » des applications ouvre l'article chez lui.
        key = url[len(HELP_LINK) :]
        if not links or key not in links:
            return text
        return f'<a href="{escape(links[key])}" data-help="{key}">{text}</a>'
    if not _safe_target(url):
        return match.group(0)
    external = ' rel="noopener"' if url.startswith("https://") else ""
    return f'<a href="{url}"{external}>{text}</a>'


def _inline(line: str, links: dict[str, str] | None = None) -> str:
    bold = BOLD.sub(r"<strong>\1</strong>", french_spaces(escape(line)))
    return LINK.sub(lambda match: _link(match, links), bold)


def photo_ids(text: str) -> list[str]:
    """Les photos citées dans le texte, pour les chercher d'un coup."""
    found = (PHOTO.match(line.strip()) for line in text.splitlines())
    return list(dict.fromkeys(match.group(2) for match in found if match))


def _figure(caption: str, photo: dict) -> str:
    """`photo` : `url`, `small`, `alt`, `width`, `height` (`site_content.news_photo`)."""
    img = (
        f'<img src="{escape(photo["url"])}" srcset="{escape(photo["small"])} 600w, '
        f'{escape(photo["url"])} {int(photo["width"])}w" sizes="(min-width: 800px) 760px, 100vw" '
        f'alt="{escape(photo["alt"])}" width="{int(photo["width"])}" '
        f'height="{int(photo["height"])}" loading="lazy" decoding="async">'
    )
    text = f"<figcaption>{_inline(caption)}</figcaption>" if caption else ""
    return f"<figure>{img}{text}</figure>"


def _capture(caption: str, capture: dict) -> str:
    """`capture` : `url`, `width`, `height` (`help_center.captures`) ; la légende sert de texte
    de remplacement."""
    img = (
        f'<img src="{escape(capture["url"])}" alt="{escape(caption)}" '
        f'width="{int(capture["width"])}" height="{int(capture["height"])}" loading="lazy" '
        'decoding="async">'
    )
    text = f"<figcaption>{_inline(caption)}</figcaption>" if caption else ""
    return f'<figure class="hshot">{img}{text}</figure>'


def render(
    text: str,
    photos: dict[str, dict] | None = None,
    captures: dict[str, dict] | None = None,
    links: dict[str, str] | None = None,
) -> SafeString:
    """Le texte en HTML sûr ; `photos` : les photos citées, par identifiant ; `captures` : les
    captures de l'aide, par nom ; `links` : l'adresse de chaque article de l'aide, par clé."""
    html: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []
    tip: list[str] = []
    kind = "ul"

    def close() -> None:
        if paragraph:
            html.append(f"<p>{'<br>'.join(paragraph)}</p>")
            paragraph.clear()
        if items:
            html.append(f"<{kind}>" + "".join(f"<li>{item}</li>" for item in items) + f"</{kind}>")
            items.clear()
        if tip:
            html.append(f'<div class="tip">{"<br>".join(tip)}</div>')
            tip.clear()

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        heading = next((tag for mark, tag in HEADINGS.items() if line.startswith(mark)), None)
        bullet = BULLET.match(line) or NUMBERED.match(line)
        figure = PHOTO.match(line)
        shot = CAPTURE.match(line)
        if figure or shot:
            close()
            if figure and photos and figure.group(2) in photos:
                html.append(_figure(figure.group(1).strip(), photos[figure.group(2)]))
            if shot and captures and shot.group(2) in captures:
                html.append(_capture(shot.group(1).strip(), captures[shot.group(2)]))
        elif not line:
            close()
        elif heading:
            close()
            title = _inline(line.split(" ", 1)[1].strip(), links)
            html.append(f"<{heading}>{title}</{heading}>")
        elif TIP.match(line):
            if paragraph or items:
                close()
            tip.append(_inline(line[TIP.match(line).end() :], links))
        elif bullet:
            tag = "ol" if NUMBERED.match(line) else "ul"
            if paragraph or tip or (items and tag != kind):
                close()
            kind = tag
            items.append(_inline(line[bullet.end() :], links))
        else:
            if items or tip:
                close()
            paragraph.append(_inline(line, links))
    close()
    # Sûr : tout le texte de l'auteur est passé par `escape` (`_inline`).
    return mark_safe("\n".join(html))


def reading_minutes(text: str) -> int:
    """Durée de lecture affichée sous le titre, une minute au moins."""
    return max(1, math.ceil(len(text.split()) / WORDS_PER_MINUTE))

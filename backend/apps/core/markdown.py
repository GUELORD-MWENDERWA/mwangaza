"""Petit Markdown des actualités du site (SITE.2), sans dépendance : paragraphes (une ligne vide
les sépare, un retour à la ligne est gardé), intertitres (`## `, `### `), listes (`- `), gras
(`**…**`) et liens (`[texte](https://…)` ou une page du site `/…`). Tout le texte est **échappé
d'abord** : aucun HTML de l'auteur n'arrive dans la page ; seules les balises d'ici sont écrites.
Le site et l'aperçu de la console passent par la même fonction."""

import math
import re

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

HEADINGS = {"## ": "h2", "### ": "h3"}
BULLET = re.compile(r"^[-*] +")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
# Après échappement : les guillemets sont devenus `&quot;`, une adresse ne peut pas sortir de
# l'attribut ; espaces et parenthèses refusés dans l'adresse.
LINK = re.compile(r"\[([^\]\n]+)\]\(([^()\s]+)\)")
WORDS_PER_MINUTE = 200


def _safe_target(url: str) -> bool:
    """Une adresse `https://` ou une page du site (`/…`, jamais `//autre-site`)."""
    return url.startswith("https://") or (url.startswith("/") and not url.startswith("//"))


def _link(match: re.Match) -> str:
    text, url = match.group(1), match.group(2)
    if not _safe_target(url):
        return match.group(0)
    external = ' rel="noopener"' if url.startswith("https://") else ""
    return f'<a href="{url}"{external}>{text}</a>'


def _inline(line: str) -> str:
    return LINK.sub(_link, BOLD.sub(r"<strong>\1</strong>", escape(line)))


def render(text: str) -> SafeString:
    """Le texte en HTML sûr."""
    html: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []

    def close() -> None:
        if paragraph:
            html.append(f"<p>{'<br>'.join(paragraph)}</p>")
            paragraph.clear()
        if items:
            html.append("<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>")
            items.clear()

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        heading = next((tag for mark, tag in HEADINGS.items() if line.startswith(mark)), None)
        bullet = BULLET.match(line)
        if not line:
            close()
        elif heading:
            close()
            html.append(f"<{heading}>{_inline(line.split(' ', 1)[1].strip())}</{heading}>")
        elif bullet:
            if paragraph:
                close()
            items.append(_inline(line[bullet.end() :]))
        else:
            if items:
                close()
            paragraph.append(_inline(line))
    close()
    # Sûr : tout le texte de l'auteur est passé par `escape` (`_inline`).
    return mark_safe("\n".join(html))


def reading_minutes(text: str) -> int:
    """Durée de lecture affichée sous le titre, une minute au moins."""
    return max(1, math.ceil(len(text.split()) / WORDS_PER_MINUTE))

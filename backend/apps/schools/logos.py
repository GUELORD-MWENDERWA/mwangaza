"""Logo de l'école : PNG, JPEG ou SVG, 1 Mo au plus (maquette M5), reconnu à ses premiers octets
et non à son nom. Pas de dépendance (Pillow n'est pas installé) : le logo n'est ni redimensionné
ni converti.

Un SVG peut contenir du code : il est refusé s'il porte un script, un gestionnaire d'événement ou
une entité XML, et servi avec une politique qui empêche tout script (`views.school_logo`).
"""

import re
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.ids import uuid7

LOGO_MAX_SIZE = 1024 * 1024
CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "svg": "image/svg+xml"}

_SVG_ROOT = re.compile(rb"<svg[\s>]", re.IGNORECASE)
_SVG_DANGER = re.compile(rb"<!entity|<script|javascript:|\son[a-z]+\s*=", re.IGNORECASE)


def _read(file) -> bytes:
    file.seek(0)
    content = file.read(LOGO_MAX_SIZE + 1)
    file.seek(0)
    return content


def logo_kind(file) -> str | None:
    """`png`, `jpg` ou `svg` d'après le contenu ; None pour tout autre fichier."""
    content = _read(file)
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if _SVG_ROOT.search(content[:4096]) and not _SVG_DANGER.search(content):
        return "svg"
    return None


def validate_logo(file) -> None:
    # Un logo déjà enregistré n'est pas relu à chaque enregistrement de l'école.
    if getattr(file, "_committed", False):
        return
    if file.size > LOGO_MAX_SIZE:
        raise ValidationError(_("The logo must not exceed 1 MB."), code="logo_too_large")
    if logo_kind(file) is None:
        raise ValidationError(
            _("The logo must be a PNG, JPEG or SVG image (SVG without scripts)."),
            code="logo_type",
        )


# Début du nom des fichiers : `logo-…` ou `logo-bw-…` (noir et blanc).
FILE_PREFIXES = {"logo": "logo-", "logo_monochrome": "logo-bw-"}


def _path(school, field: str, filename: str) -> str:
    """Nom choisi par le serveur : un nouveau nom à chaque logo (les navigateurs ne gardent pas
    l'ancien en cache), extension d'après le contenu."""
    try:
        kind = logo_kind(getattr(school, field))
    except ValueError:  # `logo.save(nom, contenu)` dans le code : pas encore de fichier lié
        kind = None
    kind = kind or Path(filename).suffix.removeprefix(".").lower() or "bin"
    return f"schools/{school.pk}/{FILE_PREFIXES[field]}{uuid7().hex[-12:]}.{kind}"


def logo_path(school, filename: str) -> str:
    return _path(school, "logo", filename)


def monochrome_logo_path(school, filename: str) -> str:
    return _path(school, "logo_monochrome", filename)

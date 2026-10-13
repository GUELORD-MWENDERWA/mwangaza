"""Logo de l'école : PNG ou JPEG, 1 Mo et 2 048 pixels de côté au plus, ré-encodé à l'envoi
(`core.images`, S.4). Le SVG n'est plus accepté pour une école : un fichier qui peut porter du
code ne se filtre pas par une liste de ce qui est interdit. Ceux enregistrés avant restent lus
(`logo_kind`) et servis avec une politique qui empêche tout script (`core.http.serve_image`) ; le
SVG reste permis pour le logo de la plateforme, envoyé par le super-admin (`core.platform`).
"""

import re
from pathlib import Path

from apps.core.ids import uuid7
from apps.core.images import MAX_SIZE, clean_image

CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "svg": "image/svg+xml"}

_SVG_ROOT = re.compile(rb"<svg[\s>]", re.IGNORECASE)
_SVG_DANGER = re.compile(rb"<!entity|<script|javascript:|\son[a-z]+\s*=", re.IGNORECASE)


def _read(file) -> bytes:
    file.seek(0)
    content = file.read(MAX_SIZE + 1)
    file.seek(0)
    return content


def logo_kind(file) -> str | None:
    """`png`, `jpg` ou `svg` (sans script) d'après le contenu ; None pour tout autre fichier."""
    content = _read(file)
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if _SVG_ROOT.search(content[:4096]) and not _SVG_DANGER.search(content):
        return "svg"
    return None


def validate_logo(file) -> None:
    """Administration Django (dépannage) : mêmes refus qu'à l'API, qui, elle, enregistre l'image
    ré-encodée (`serializers.LogoUploadSerializer`). Un logo déjà enregistré n'est pas relu."""
    if not getattr(file, "_committed", False):
        clean_image(file)


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

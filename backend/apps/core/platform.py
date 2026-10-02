"""Identité de la plateforme (5.1) : contrôles de ses fichiers et de ses couleurs, adresses.

Le logo suit les règles du logo d'une école (`schools.logos`). L'icône des applications
(écran d'accueil, onglet) est un PNG carré d'au moins 512 px, lu à ses premiers octets : pas de
dépendance (Pillow n'est pas installé), elle n'est donc ni redimensionnée ni convertie.

Les couleurs remplacent celles de l'interface (`lake`, `lamp` du design) : la couleur principale
porte du texte blanc (boutons) et s'écrit sur fond clair (liens), l'accent se pose sur le fond
sombre du menu (basalte). Une couleur illisible est refusée.
"""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.ids import uuid7
from apps.schools.colors import contrast, normalize
from apps.schools.logos import logo_kind

ICON_MAX_SIZE = 1024 * 1024
ICON_MIN_SIDE = 512
BASALT = "#2B2724"  # fond du menu (design), sous l'accent
MIN_CONTRAST = 4.5
# Adresses publiques (sans école) ; `?v=` change avec chaque fichier (cache des navigateurs).
ADDRESSES = {"logo": "/api/platform/logo/", "icon": "/api/platform/icon/"}


def png_size(file) -> tuple[int, int] | None:
    """Largeur et hauteur d'un PNG (bloc IHDR) ; None pour tout autre fichier."""
    file.seek(0)
    head = file.read(24)
    file.seek(0)
    if not head.startswith(b"\x89PNG\r\n\x1a\n") or head[12:16] != b"IHDR":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def validate_icon(file) -> None:
    if getattr(file, "_committed", False):
        return
    if file.size > ICON_MAX_SIZE:
        raise ValidationError(_("The icon must not exceed 1 MB."), code="icon_too_large")
    size = png_size(file)
    if size is None or size[0] != size[1] or size[0] < ICON_MIN_SIDE:
        raise ValidationError(
            _("The icon must be a square PNG image of at least 512 x 512 pixels."),
            code="icon_format",
        )


def _color(value: str) -> str:
    try:
        return normalize(value)
    except ValueError:
        raise ValidationError(
            _("Enter a colour as #RRGGBB, e.g. #0E5C6B."), code="invalid_color"
        ) from None


def tint(color: str, share: float) -> str:
    """Mélange de la couleur (part `share`) et du blanc, comme `color-mix` dans l'interface."""
    color = _color(color)
    channels = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(c * share + 255 * (1 - share)):02X}" for c in channels)


def validate_primary_color(value: str) -> None:
    # Le fond le plus sombre sous un texte de cette couleur : sa teinte claire (`lake-50`).
    if contrast(_color(value), tint(value, 0.1)) < MIN_CONTRAST:
        raise ValidationError(
            _(
                "This colour is too light: white text on it, or the colour on a light "
                "background, is not readable."
            ),
            code="unreadable_color",
        )


def validate_accent_color(value: str) -> None:
    if contrast(_color(value), BASALT) < MIN_CONTRAST:
        raise ValidationError(
            _("This colour is too dark: it is not readable on the dark menu."),
            code="unreadable_color",
        )


def _path(prefix: str, kind: str) -> str:
    """Nouveau nom à chaque fichier (les navigateurs ne gardent pas l'ancien)."""
    return f"platform/{prefix}-{uuid7().hex[-12:]}.{kind}"


def logo_path(instance, filename: str) -> str:
    try:
        kind = logo_kind(instance.logo)
    except ValueError:  # `logo.save(nom, contenu)` dans le code : pas encore de fichier lié
        kind = None
    return _path("logo", kind or Path(filename).suffix.removeprefix(".").lower() or "bin")


def icon_path(instance, filename: str) -> str:
    return _path("icon", "png")


def file_url(file, field: str) -> str | None:
    if not file:
        return None
    return f"{ADDRESSES[field]}?v={Path(file.name).stem.rsplit('-', 1)[-1]}"

"""Couleur de l'école (décision Q8, `docs/04` § 1) : choisie par l'école, lisible.

Le texte posé sur la couleur (badge de l'école, en-têtes imprimés) est blanc ou encre `#1A2233`,
celui qui contraste le plus, avec un contraste d'au moins 4,5 : 1 (WCAG 2, texte normal). Une
couleur sur laquelle aucun des deux n'est lisible est refusée, avec une teinte voisine proposée.
"""

import colorsys
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

DEFAULT_COLOR = "#0E5C6B"  # `lake`, couleur Mwangaza
WHITE = "#FFFFFF"
INK = "#1A2233"
MIN_CONTRAST = 4.5

_HEX = re.compile(r"^#([0-9A-F]{3}|[0-9A-F]{6})$")


def normalize(value: str) -> str:
    """`#rrggbb` en majuscules ; accepte `#rgb`. `ValueError` pour tout autre format."""
    value = value.strip().upper()
    if not _HEX.match(value):
        raise ValueError(f"Couleur attendue au format #RRGGBB : {value!r}")
    if len(value) == 4:
        value = "#" + "".join(digit * 2 for digit in value[1:])
    return value


def rgb(color: str) -> tuple[int, int, int]:
    color = normalize(color)
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(color: str) -> float:
    """Luminance relative (WCAG 2)."""
    red, green, blue = (_linear(channel) for channel in rgb(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: str, second: str) -> float:
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def text_color(color: str) -> str | None:
    """Blanc ou encre, le plus lisible des deux s'il atteint 4,5 : 1 ; sinon None."""
    best = max((WHITE, INK), key=lambda text: contrast(color, text))
    return best if contrast(color, best) >= MIN_CONTRAST else None


def nearby_readable(color: str) -> str:
    """La couleur elle-même si elle est lisible ; sinon la plus proche de même teinte, en
    changeant le moins possible sa luminosité (plus sombre d'abord, à écart égal)."""
    color = normalize(color)
    if text_color(color) is not None:
        return color
    hue, lightness, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in rgb(color)))
    for step in range(1, 201):
        for candidate_lightness in (lightness - step / 200, lightness + step / 200):
            if not 0 <= candidate_lightness <= 1:
                continue
            channels = colorsys.hls_to_rgb(hue, candidate_lightness, saturation)
            candidate = "#" + "".join(f"{round(channel * 255):02X}" for channel in channels)
            if text_color(candidate) is not None:
                return candidate
    return DEFAULT_COLOR  # jamais atteint : le noir et le blanc sont toujours lisibles


def validate_school_color(value: str) -> None:
    try:
        color = normalize(value)
    except ValueError:
        raise ValidationError(
            _("Enter a colour as #RRGGBB, e.g. #0E5C6B."), code="invalid_color"
        ) from None
    if text_color(color) is None:
        raise ValidationError(
            _(
                "Text is not readable on this colour, neither in white nor in dark ink. "
                "Nearby readable colour: %(proposal)s."
            ),
            code="unreadable_color",
            params={"proposal": nearby_readable(color)},
        )

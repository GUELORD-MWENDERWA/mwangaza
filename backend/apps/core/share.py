"""Image de partage d'une page du site public (WEB.1c) : 1200 x 630, montrée par WhatsApp,
Facebook et LinkedIn quand on colle son adresse. Dessinée d'après `maquettes/site/partage.html`
(mêmes mesures) : icône, nom pour la recherche et couleur d'accent de la plateforme ; fond nuit,
lignes de relief et police du site (système de design). JPEG léger (WhatsApp : moins de 300 Ko)."""

from functools import cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

SIZE = (1200, 630)
MARGIN = 72
NIGHT = (11, 28, 53)
NIGHT_3 = (33, 58, 99)
NIGHT_SOFT = (195, 207, 224)
WHITE = (255, 255, 255)
SITE = Path(__file__).parent / "static" / "core" / "site"
DEFAULT_ICON = SITE / "icon-512.png"
# Lignes de relief (le volcan vu d'en haut), en bas à droite, blanc à 9 %.
RELIEF_CENTER = (1010, 530)
RELIEF = ((90, 40), (170, 80), (250, 120), (330, 160), (410, 200), (490, 240))
HEADLINE_LINES = 4
SMOOTH = 4  # coins arrondis dessinés 4 fois plus grands, puis réduits (bords lisses)


@cache
def _font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(
        str(SITE / f"atkinson-hyperlegible-next-latin-{weight}-normal.woff2"), size
    )


def _rounded(image: Image.Image, radius: int) -> Image.Image:
    """`image` aux coins arrondis (transparents)."""
    width, height = image.size
    mask = Image.new("L", (width * SMOOTH, height * SMOOTH), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, width * SMOOTH - 1, height * SMOOTH - 1), radius * SMOOTH, fill=255
    )
    result = image.convert("RGBA")
    result.putalpha(mask.resize(image.size, Image.Resampling.LANCZOS))
    return result


def _framed(
    picture: Image.Image, size: tuple[int, int], radius: int, border: int, color
) -> Image.Image:
    """Capture recadrée par le haut dans un cadre arrondi (bord de `border` px)."""
    inner = (size[0] - 2 * border, size[1] - 2 * border)
    frame = Image.new("RGB", size, color)
    frame.paste(ImageOps.fit(picture.convert("RGB"), inner, centering=(0.5, 0)), (border, border))
    return _rounded(frame, radius)


def _lines(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """Texte coupé aux mots dans `width` px ; au-delà de quatre lignes, « … »."""
    lines: list[str] = []
    for word in text.split():
        candidate = f"{lines[-1]} {word}" if lines else word
        if lines and font.getlength(candidate) <= width:
            lines[-1] = candidate
        else:
            lines.append(word)
    if len(lines) > HEADLINE_LINES:
        lines = lines[:HEADLINE_LINES]
        lines[-1] += " …"
    return lines


def _fitting(text: str, weight: int, size: int, width: float) -> ImageFont.FreeTypeFont:
    """Police aussi grande que possible (jusqu'à `size`) pour tenir dans `width` px."""
    font = _font(weight, size)
    while size > 20 and font.getlength(text) > width:
        size -= 2
        font = _font(weight, size)
    return font


def draw(
    *,
    brand: tuple[str, str],
    headline: str,
    domain: str,
    accent: str,
    icon: Image.Image | None,
    capture: Path | None,
) -> bytes:
    """Image JPEG. `brand` : le nom en gras et la suite plus claire (« Mwangaza », « School ») ;
    `icon` : celle de la plateforme (sinon le symbole) ; `capture` : la capture principale de la
    page (Portail : en téléphone ; aucune : titre sur toute la largeur)."""
    image = Image.new("RGBA", SIZE, NIGHT)
    relief = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    pen = ImageDraw.Draw(relief)
    cx, cy = RELIEF_CENTER
    for rx, ry in RELIEF:
        pen.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(*WHITE, 23), width=2)
    image.alpha_composite(relief)

    if capture:
        picture = Image.open(capture)
        if capture.stem.endswith("-mobile"):
            image.alpha_composite(_framed(picture, (300, 650), 32, 8, (0, 0, 0)), (830, 96))
        else:
            image.alpha_composite(_framed(picture, (640, 400), 16, 2, NIGHT_3), (720, 150))

    pen = ImageDraw.Draw(image)
    logo = (
        (icon or Image.open(DEFAULT_ICON))
        .convert("RGBA")
        .resize((72, 72), Image.Resampling.LANCZOS)
    )
    image.alpha_composite(logo, (MARGIN, 64))
    bold, rest = brand
    x, room = MARGIN + 72 + 18, SIZE[0] - MARGIN - (MARGIN + 72 + 18)
    font = _fitting(f"{bold} {rest}".strip(), 800, 40, room)
    pen.text((x, 100), bold, font=font, fill=WHITE, anchor="lm")
    if rest:
        light = _font(400, font.size)
        pen.text(
            (x + font.getlength(bold) + 18, 100), rest, font=light, fill=NIGHT_SOFT, anchor="lm"
        )

    width = 600 if capture else SIZE[0] - 2 * MARGIN
    font = _font(800, 60)
    for row, line in enumerate(_lines(headline, font, width)):
        pen.text((MARGIN, 203 + row * 66), line, font=font, fill=WHITE, anchor="la")

    pen.rounded_rectangle((MARGIN, 545, MARGIN + 48, 551), 3, fill=accent)
    pen.text(
        (MARGIN + 64, 548), domain, font=_fitting(domain, 700, 30, 600), fill=accent, anchor="lm"
    )

    output = BytesIO()
    image.convert("RGB").save(output, "JPEG", quality=85, optimize=True, progressive=True)
    return output.getvalue()

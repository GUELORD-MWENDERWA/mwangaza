"""Images envoyées (S.4) : PNG ou JPEG, poids et dimensions limités, puis **ré-encodées**. Ce qui
est enregistré est une image neuve, faite des seuls pixels : ni métadonnées (EXIF, position GPS,
commentaires), ni octets cachés derrière l'image. Liste blanche (deux décodeurs de Pillow), jamais
un filtre de ce qui est interdit."""

import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageChops, ImageOps
from rest_framework import serializers
from rest_framework.fields import get_error_detail

MAX_SIZE = 1024 * 1024
# Lu dans l'en-tête avant de décoder : au pire 2 048 x 2 048 x 4 octets = 16 Mo en mémoire.
MAX_SIDE = 2048
FORMATS = {"PNG": "png", "JPEG": "jpg"}
JPEG_QUALITY = 90


def _too_large() -> ValidationError:
    return ValidationError(_("The image must not exceed 1 MB."), code="image_too_large")


def _wrong_type() -> ValidationError:
    return ValidationError(_("The image must be a PNG or JPEG image."), code="image_type")


def _too_big() -> ValidationError:
    return ValidationError(
        _("The image must not exceed %(side)s pixels on its longest side."),
        code="image_dimensions",
        params={"side": MAX_SIDE},
    )


def check_size(file) -> None:
    if file.size > MAX_SIZE:
        raise _too_large()


def _mode(image: Image.Image) -> str:
    """Couleurs gardées : gris ou RVB, avec la transparence d'un PNG ; jamais de palette, de CMJN
    ni de 16 bits."""
    if image.format == "PNG" and (
        image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
    ):
        return "RGBA"
    return "L" if image.mode in ("L", "1") else "RGB"


def clean_image(file, *, formats: dict[str, str] = FORMATS) -> ContentFile:
    """L'image ré-encodée dans son format, tournée comme l'appareil photo l'indiquait ;
    `ValidationError` si le fichier n'en est pas une, pèse ou mesure trop."""
    check_size(file)
    file.seek(0)
    try:
        image = Image.open(file, formats=list(formats))
    except Image.DecompressionBombError:
        raise _too_big() from None
    except Exception:  # fichier inconnu ou en-tête faux : le décodeur lève des erreurs variées
        raise _wrong_type() from None
    if max(image.size) > MAX_SIDE:
        raise _too_big()
    # Certains téléphones rangent plusieurs vues dans un JPEG (« MPO ») : la première est la photo.
    kind = formats.get("JPEG" if image.format == "MPO" else image.format)
    if kind is None:
        raise _wrong_type()
    try:
        pixels = ImageOps.exif_transpose(image).convert(_mode(image))
    except Exception:  # image tronquée ou abîmée
        raise _wrong_type() from None
    # Image neuve : rien de l'ancienne ne suit, sauf les pixels.
    fresh = Image.new(pixels.mode, pixels.size)
    fresh.paste(pixels)
    output = io.BytesIO()
    if kind == "jpg":
        fresh.save(output, "JPEG", quality=JPEG_QUALITY)
    else:
        fresh.save(output, "PNG")
    return ContentFile(output.getvalue(), name=f"image.{kind}")


# Cachet et signatures (DOC.1) : assez net pour un document imprimé, léger dans un PDF de 50 pages.
SIGNATURE_SIDE = 800
# Luminance (0 noir, 255 blanc) : au-dessus de PAPER, transparent ; sous INK, opaque ; entre les
# deux, en partie (bords du trait adoucis).
PAPER, INK = 225, 160


def clean_signature(file) -> ContentFile:
    """Cachet ou signature : contrôlé comme toute image (`clean_image`), réduit à
    `SIGNATURE_SIDE` et enregistré en PNG. Sans transparence (photo ou scan d'une feuille), le
    fond clair devient transparent : seul le trait se pose sur le document, le cachet peut
    chevaucher la signature. Un PNG déjà détouré garde la sienne."""
    with Image.open(clean_image(file)) as image:
        image = image.convert("RGBA")
    image.thumbnail((SIGNATURE_SIDE, SIGNATURE_SIDE))
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] == 255:
        # Feuille photographiée : le papier le plus clair devient blanc, l'encre la plus foncée
        # noire, avant de choisir ce qui est transparent.
        light = ImageOps.autocontrast(image.convert("L"), cutoff=1)
        ink = light.point(
            lambda v: 0 if v >= PAPER else 255 if v <= INK else (PAPER - v) * 255 // (PAPER - INK)
        )
        image.putalpha(ImageChops.multiply(alpha, ink))
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return ContentFile(output.getvalue(), name="signature.png")


class CleanedFileField(serializers.FileField):
    """Fichier envoyé, remplacé par sa version nettoyée : `clean` rend le fichier à enregistrer ou
    lève `ValidationError`."""

    def __init__(self, *, clean=clean_image, **kwargs):
        self.clean = clean
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            return self.clean(super().to_internal_value(data))
        except ValidationError as exc:
            raise serializers.ValidationError(get_error_detail(exc)) from None


# Photothèque du site public (SITE.3) : photos d'appareil, plus lourdes que les logos.
PHOTO_MAX_SIZE = 10 * 1024 * 1024
PHOTO_MIN_WIDTH = 600
# Lu dans l'en-tête avant de décoder ; un JPEG est décodé directement à une échelle réduite
# (`draft`) : une photo de 24 Mpx tient en moins de 20 Mo de mémoire.
PHOTO_MAX_PIXELS = 24_000_000
PHOTO_FORMATS = ("JPEG", "PNG", "WEBP")
PHOTO_WIDTHS = (1600, 600)
WEBP_QUALITY = 80


def clean_site_photo(file) -> tuple[dict[int, ContentFile], tuple[int, int]]:
    """La photo ré-encodée en WebP à chaque largeur de `PHOTO_WIDTHS` (jamais agrandie), faite
    des seuls pixels, et la taille de la plus grande ; `ValidationError` si le fichier n'est pas
    une photo JPEG, PNG ou WebP, pèse trop ou mesure trop peu ou trop."""
    if file.size > PHOTO_MAX_SIZE:
        raise ValidationError(_("The photo must not exceed 10 MB."), code="image_too_large")
    file.seek(0)
    try:
        image = Image.open(file, formats=list(PHOTO_FORMATS))
    except Image.DecompressionBombError:
        raise _too_big() from None
    except Exception:  # fichier inconnu ou en-tête faux
        raise ValidationError(
            _("The photo must be a JPEG, PNG or WebP image."), code="image_type"
        ) from None
    width, height = image.size
    if width * height > PHOTO_MAX_PIXELS:
        raise ValidationError(_("The photo is too large."), code="image_dimensions")
    if width < PHOTO_MIN_WIDTH:
        raise ValidationError(
            _("The photo must be at least %(width)s pixels wide."),
            code="image_dimensions",
            params={"width": PHOTO_MIN_WIDTH},
        )
    if image.format == "JPEG":
        # Largeur seule : le décodeur réduit tant que la photo garde 1 600 px de large.
        image.draft("RGB", (PHOTO_WIDTHS[0], 1))
    try:
        pixels = ImageOps.exif_transpose(image)
        mode = "RGBA" if "A" in pixels.getbands() or "transparency" in pixels.info else "RGB"
        pixels = pixels.convert(mode)
    except Exception:  # image tronquée ou abîmée
        raise ValidationError(
            _("The photo must be a JPEG, PNG or WebP image."), code="image_type"
        ) from None
    sizes: dict[int, ContentFile] = {}
    size = pixels.size
    for target in PHOTO_WIDTHS:
        copy = pixels.copy()
        if copy.width > target:
            copy = copy.resize((target, round(copy.height * target / copy.width)), Image.LANCZOS)
        # Image neuve : rien de l'ancienne ne suit, sauf les pixels.
        fresh = Image.new(copy.mode, copy.size)
        fresh.paste(copy)
        output = io.BytesIO()
        fresh.save(output, "WEBP", quality=WEBP_QUALITY, method=4)
        sizes[target] = ContentFile(output.getvalue(), name=f"{target}.webp")
        if target == PHOTO_WIDTHS[0]:
            size = fresh.size
    return sizes, size


CONSENT_MAX_SIZE = 5 * 1024 * 1024
CONSENT_SIGNATURES = {b"%PDF-": "pdf", b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}


def consent_extension(file) -> str:
    """Accord écrit (lettre signée) : PDF, ou photo JPEG ou PNG de la lettre, 5 Mo au plus,
    reconnu à ses premiers octets. Gardé tel quel (jamais montré : seulement téléchargé à la
    console) ; rend l'extension à donner au fichier."""
    if file.size > CONSENT_MAX_SIZE:
        raise ValidationError(_("The file must not exceed 5 MB."), code="attachment_too_large")
    file.seek(0)
    start = file.read(8)
    file.seek(0)
    for signature, extension in CONSENT_SIGNATURES.items():
        if start.startswith(signature):
            return extension
    raise ValidationError(
        _("The consent must be a PDF, or a JPEG or PNG photo of the letter."), code="consent_type"
    )

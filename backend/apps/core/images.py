"""Images envoyées (S.4) : PNG ou JPEG, poids et dimensions limités, puis **ré-encodées**. Ce qui
est enregistré est une image neuve, faite des seuls pixels : ni métadonnées (EXIF, position GPS,
commentaires), ni octets cachés derrière l'image. Liste blanche (deux décodeurs de Pillow), jamais
un filtre de ce qui est interdit."""

import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps
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

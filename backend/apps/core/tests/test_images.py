"""Images envoyées (S.4) : ré-encodées, sans métadonnées ; tout le reste est refusé."""

import io
import zlib

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from apps.core.images import MAX_SIDE, MAX_SIZE, clean_image
from tests.images import PNG, image_bytes

GPS_IFD, ORIENTATION = 0x8825, 0x0112


def cleaned(content: bytes) -> bytes:
    return clean_image(SimpleUploadedFile("envoi", content)).read()


def test_a_phone_photo_loses_its_position_and_keeps_its_orientation():
    exif = Image.Exif()
    exif[ORIENTATION] = 6  # tenue debout : l'appareil enregistre couché et le note ici
    exif[0x010F] = "Appareil fictif"
    exif.get_ifd(GPS_IFD)[2] = (1.0, 40.0, 30.0)  # latitude de Goma
    photo = image_bytes("JPEG", (40, 20), exif=exif, comment=b"prise a la maison")
    assert b"Appareil fictif" in photo and b"prise a la maison" in photo
    hidden = b"<script>alert(1)</script>"

    result = cleaned(photo + hidden)

    image = Image.open(io.BytesIO(result))
    assert image.format == "JPEG" and image.size == (20, 40)
    assert not image.getexif() and "comment" not in image.info
    for trace in (b"Exif", b"Appareil fictif", b"prise a la maison", hidden):
        assert trace not in result


def test_a_phone_file_holding_several_pictures_keeps_the_photo():
    output = io.BytesIO()
    photo, depth_map = Image.new("RGB", (40, 20), (120, 20, 20)), Image.new("RGB", (40, 20))
    photo.save(output, "MPO", save_all=True, append_images=[depth_map])
    assert Image.open(io.BytesIO(output.getvalue())).format == "MPO"

    image = Image.open(io.BytesIO(cleaned(output.getvalue())))

    assert image.format == "JPEG" and image.size == (40, 20)


def test_a_png_keeps_its_transparency_and_loses_its_text():
    text = PngInfo()
    text.add_text("Author", "Parent fictif")
    logo = image_bytes("PNG", mode="RGBA", pnginfo=text)
    assert b"Parent fictif" in logo

    result = cleaned(logo)

    image = Image.open(io.BytesIO(result))
    assert image.format == "PNG" and image.getpixel((0, 0)) == (120, 20, 20, 128)
    assert b"Parent fictif" not in result and not image.text


def _bomb() -> bytes:
    """En-tête d'un PNG de 60 000 x 60 000 pixels : 14 Go une fois décodé."""
    side = (60_000).to_bytes(4, "big")
    header = b"IHDR" + side + side + PNG[24:29]
    return PNG[:12] + header + zlib.crc32(header).to_bytes(4, "big") + PNG[33:]


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (PNG + bytes(MAX_SIZE), "image_too_large"),
        (image_bytes("PNG", (MAX_SIDE + 1, 8)), "image_dimensions"),
        (_bomb(), "image_dimensions"),
        (image_bytes("GIF"), "image_type"),
        (image_bytes("BMP"), "image_type"),
        (PNG[:40], "image_type"),
        (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>', "image_type"),
        (b"%PDF-1.7", "image_type"),
    ],
)
def test_anything_else_is_refused(content, code):
    with pytest.raises(ValidationError) as error:
        cleaned(content)

    assert error.value.code == code

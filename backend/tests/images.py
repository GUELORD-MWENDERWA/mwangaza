"""Vraies images pour les tests : les fichiers envoyés sont décodés (`apps.core.images`)."""

import io

from PIL import Image


def image_bytes(kind: str = "PNG", size: tuple[int, int] = (32, 32), mode: str = "RGB", **save):
    """Une image unie (rouge sombre), dans le format et la taille voulus."""
    output = io.BytesIO()
    color = {"RGB": (120, 20, 20), "RGBA": (120, 20, 20, 128)}.get(mode, 90)
    Image.new(mode, size, color).save(output, kind, **save)
    return output.getvalue()


PNG = image_bytes("PNG")
JPEG = image_bytes("JPEG")

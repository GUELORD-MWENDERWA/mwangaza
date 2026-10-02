"""Photo de l'élève : PNG ou JPEG, 1 Mo au plus, reconnue à ses premiers octets et non à son nom.
Pas de Pillow : la Gestion la réduit dans le navigateur avant l'envoi. Jamais publique : servie
par l'API aux comptes de l'école qui ont `students.view` (`views.StudentViewSet.photo`) et, avec
le consentement du parent, à sa famille sur le portail (H3)."""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.utils.translation import gettext_lazy as _

PHOTO_MAX_SIZE = 1024 * 1024
CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg"}


def photo_kind(file) -> str | None:
    """`png` ou `jpg` d'après le contenu ; None pour tout autre fichier."""
    file.seek(0)
    start = file.read(8)
    file.seek(0)
    if start.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if start.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return None


def validate_photo(file) -> None:
    if file.size > PHOTO_MAX_SIZE:
        raise ValidationError(_("The photo must not exceed 1 MB."), code="photo_too_large")
    if photo_kind(file) is None:
        raise ValidationError(_("The photo must be a PNG or JPEG image."), code="photo_type")


def photo_path(student, filename: str) -> str:
    """Un dossier par école ; le nom (nouveau à chaque photo) est choisi par le service."""
    return f"schools/{student.school_id}/students/{filename}"


def photo_version(student) -> str:
    """Partie variable du nom du fichier : l'adresse de la photo change avec chaque photo."""
    return student.photo.name.rsplit("/", 1)[-1].split(".")[0].removeprefix("photo-")


def photo_response(student) -> FileResponse | None:
    """La photo, jamais dans un cache partagé ; None sans photo ou fichier manquant."""
    if not student.photo:
        return None
    try:
        file = student.photo.open("rb")
    except FileNotFoundError:
        return None
    kind = Path(student.photo.name).suffix.removeprefix(".")
    response = FileResponse(file, content_type=CONTENT_TYPES.get(kind, "image/jpeg"))
    response["X-Content-Type-Options"] = "nosniff"
    # L'adresse donnée par l'API change avec chaque photo (`photo_version`).
    response["Cache-Control"] = "private, max-age=86400"
    return response

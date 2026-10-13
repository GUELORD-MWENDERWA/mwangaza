"""Pièce jointe d'une annonce : un PDF de 5 Mo au plus, reconnu à ses premiers octets et non à son
nom. Jamais publique : servie par l'API aux comptes de l'école qui publient les annonces, puis
aux familles destinataires dans le portail (4.4). Toujours **téléchargée** (`attachment`, S.4) :
un fichier venu d'une école ne s'ouvre jamais dans une page à l'adresse de l'application."""

from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

ATTACHMENT_MAX_SIZE = 5 * 1024 * 1024


def is_pdf(file) -> bool:
    file.seek(0)
    start = file.read(5)
    file.seek(0)
    return start == b"%PDF-"


def validate_attachment(file) -> None:
    if file.size > ATTACHMENT_MAX_SIZE:
        raise ValidationError(_("The file must not exceed 5 MB."), code="attachment_too_large")
    if not is_pdf(file):
        raise ValidationError(_("The file must be a PDF."), code="attachment_type")


def attachment_path(announcement, filename: str) -> str:
    """Un dossier par école ; le nom (nouveau à chaque fichier) est choisi par le service."""
    return f"schools/{announcement.school_id}/announcements/{filename}"


def attachment_response(announcement) -> FileResponse | None:
    """Le PDF à télécharger, nommé d'après le titre ; None sans pièce jointe."""
    if not announcement.attachment:
        return None
    try:
        file = announcement.attachment.open("rb")
    except FileNotFoundError:
        return None
    filename = f"{slugify(announcement.title)[:60] or 'annonce'}.pdf"
    response = FileResponse(
        file, content_type="application/pdf", as_attachment=True, filename=filename
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=86400"
    return response

"""Pièce jointe d'une annonce : un PDF de 5 Mo au plus, reconnu à ses premiers octets et non à son
nom. Jamais publique : servie par l'API aux comptes de l'école qui publient les annonces, puis
aux familles destinataires dans le portail (4.4)."""

from django.core.exceptions import ValidationError
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

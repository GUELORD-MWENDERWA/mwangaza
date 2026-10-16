"""PDF gardés (PERF.2) : un bulletin se met en page une fois (≈ 1,9 s et 13 Mo), puis se sert comme
un fichier. La clé est l'empreinte du HTML du bulletin (notes, élève, gabarit, réglages de l'école,
décalages d'impression), sans ce qui change à chaque tirage (QR code signé, date) : la modifier
change la clé, donc le bulletin est refait et l'ancien fichier de la même inscription effacé.
Isolation : le gestionnaire scopé ne montre que les fichiers de l'école courante, et la clé
contient l'identifiant de l'école."""

import hashlib
import io
from dataclasses import dataclass, field
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import KeptDocument
from apps.core.tenancy import require_current_school, use_all_schools, use_school

UNUSED_AFTER = timedelta(days=60)
TOUCH_AFTER = timedelta(days=1)  # `last_used_at` n'est réécrit qu'une fois par jour


@dataclass
class Keep:
    """Ce que le document demande à `render` : genre, une inscription par page, variante (mode du
    bulletin), et le contexte à neutraliser pour calculer l'empreinte."""

    kind: str
    subjects: list
    variant: str = ""
    volatile: dict = field(default_factory=dict)


def fingerprint(html: str) -> str:
    school = require_current_school()
    return hashlib.sha256(f"{school.pk}|".encode() + html.encode()).hexdigest()


def lookup(keys: list[str]) -> dict[str, KeptDocument]:
    """Les fichiers déjà gardés pour ces clés (école courante), rafraîchis au plus une fois par
    jour (pas d'écriture à chaque lecture)."""
    found = {doc.key: doc for doc in KeptDocument.objects.filter(key__in=keys)}
    stale = [d.pk for d in found.values() if timezone.now() - d.last_used_at > TOUCH_AFTER]
    if stale:
        KeptDocument.objects.filter(pk__in=stale).update(last_used_at=timezone.now())
    return found


def read(document: KeptDocument) -> bytes:
    with document.file.open("rb") as file:
        return file.read()


def store(kind: str, subject, variant: str, key: str, pdf: bytes) -> None:
    """Garde le PDF et efface l'ancien de la même inscription et du même mode."""
    if KeptDocument.objects.filter(key=key).exists():
        return
    try:
        with transaction.atomic():
            document = KeptDocument(
                kind=kind, subject=subject, variant=variant, key=key, size=len(pdf)
            )
            document.file.save(f"{key[:12]}.pdf", ContentFile(pdf), save=False)
            document.save()
    except IntegrityError:  # deux tirages en même temps : l'autre a gagné
        document.file.delete(save=False)
        return
    for old in KeptDocument.objects.filter(kind=kind, subject=subject, variant=variant).exclude(
        pk=document.pk
    ):
        old.file.delete(save=False)
        old.delete()


def merge(pdfs: list[bytes]) -> bytes:
    """Les PDF mis bout à bout (polices identiques regroupées)."""
    if len(pdfs) == 1:
        return pdfs[0]
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for pdf in pdfs:
        writer.append(PdfReader(io.BytesIO(pdf)))
    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def purge() -> int:
    """Efface les fichiers non relus depuis `UNUSED_AFTER` ; retourne leur nombre."""
    count = 0
    with use_all_schools():
        old = list(
            KeptDocument.all_schools.select_related("school").filter(
                last_used_at__lt=timezone.now() - UNUSED_AFTER
            )[:500]
        )
    for document in old:
        with use_school(document.school):
            document.file.delete(save=False)
            document.delete()
        count += 1
    return count

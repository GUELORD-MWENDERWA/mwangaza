"""Cachet de l'école, signature du chef d'établissement et signature de chaque membre du
personnel (DOC.1). Images contrôlées et détourées à l'envoi (`core.images.clean_signature`),
toujours en PNG. **Jamais publiques** : servies au seul personnel connecté de l'école (cache du
navigateur, pour le reçu imprimé hors ligne), intégrées en `data:` aux PDF ; ni sur le portail
des parents, ni sur les pages de vérification d'un QR code. L'authenticité d'un document reste
prouvée par son QR code (F4), pas par l'image."""

from pathlib import Path

from django.utils.translation import gettext as _

from apps.core.ids import uuid7

PNG = {"png": "image/png"}
ADDRESSES = {"stamp": "/api/school/stamp/", "head_signature": "/api/school/head-signature/"}


def _version(file) -> str:
    return Path(file.name).stem.rsplit("-", 1)[-1]


def stamp_path(school, filename: str) -> str:
    return f"schools/{school.pk}/stamp-{uuid7().hex[-12:]}.png"


def head_signature_path(school, filename: str) -> str:
    return f"schools/{school.pk}/head-signature-{uuid7().hex[-12:]}.png"


def member_signature_path(membership, filename: str) -> str:
    return f"schools/{membership.school_id}/signature-{uuid7().hex[-12:]}.png"


def school_image_url(school, field: str) -> str | None:
    """Adresse du cachet ou de la signature du chef ; elle change avec chaque image (cache)."""
    file = getattr(school, field)
    return f"{ADDRESSES[field]}?v={_version(file)}" if file else None


def member_signature_url(membership) -> str | None:
    if membership is None or not membership.signature:
        return None
    return f"/api/school/signatures/{membership.user_id}/?v={_version(membership.signature)}"


def documents(school, membership) -> dict:
    """Ce que la Gestion pose sur les documents qu'elle imprime (reçus, bordereau) : gardé avec
    le compte pour imprimer hors ligne."""
    return {
        "stamp": school_image_url(school, "stamp"),
        "head_name": school.head_name,
        "head_title": school.head_title,
        "head_signature": school_image_url(school, "head_signature"),
        "signature": member_signature_url(membership),
    }


def _data(file) -> str:
    from apps.core.documents import data_uri

    return data_uri(file, "png", PNG)


def _head(school) -> dict | None:
    if not (school.head_name or school.head_signature):
        return None
    return {
        "title": school.head_title or _("The head of the school"),
        "name": school.head_name,
        "signature": _data(school.head_signature),
    }


def _person(school, user) -> dict:
    from apps.accounts.models import Membership

    membership = Membership.objects.filter(school=school, user=user).first()
    return {
        "title": "",
        "name": str(user),
        "signature": _data(membership.signature) if membership else "",
    }


def signature_context(school, *, author=None, head_first: bool = False) -> dict:
    """Bas d'un document du serveur (PDF) : `signer` (titre, nom, signature en `data:`) et
    `stamp`. Par défaut le chef d'établissement ; `author` signe à sa place (convocation), ou
    seulement s'il n'est ni nommé ni signé (`head_first`, circulaire). Personne : le gabarit
    garde sa ligne à la main."""
    head = _head(school)
    own = author is not None and not (head_first and head)
    signer = _person(school, author) if own else head
    return {"signer": signer, "stamp": _data(school.stamp)}

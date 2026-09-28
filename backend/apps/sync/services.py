"""Appareils (3.3.1) : enregistrement, reprise à chaque connexion, révocation, signature des
reçus émis hors ligne.

Une session connectée garde l'appareil sous `DEVICE_SESSION_KEY` : le journal d'audit note
l'appareil de chaque action (`AuditMiddleware`)."""

import base64
import binascii
from importlib import import_module

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.serialization import load_der_public_key
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.finance.models import CashRegister
from apps.schools.models import School
from apps.sync.models import Device

DEVICE_SESSION_KEY = "sync.device"
# « Poste » : jamais égal au code d'une caisse (`C1`), qui numérote les reçus donnés en ligne.
PREFIX_LETTER = "P"

DEVICE_REVOKED = ApiError(
    "device_revoked", _("This device was disconnected. It is no longer remembered."), 409
)


def session_device(session, school: School | None) -> str | None:
    """Identifiant de l'appareil de la session, s'il a été enregistré dans cette école."""
    data = session.get(DEVICE_SESSION_KEY)
    if not data or school is None or data.get("school") != str(school.pk):
        return None
    return data["id"]


def register_device(school: School, user: User, session, *, label: str, public_key: str) -> Device:
    """« Se souvenir de cet appareil » : nouvel appareil du compte, rattaché à la session."""
    _load_public_key(public_key)
    with transaction.atomic():
        # Deux enregistrements en même temps ne prennent pas le même préfixe.
        School.objects.select_for_update().filter(pk=school.pk).first()
        device = Device(
            user=user, label=label, prefix=_next_prefix(), public_key=public_key, created_by=user
        )
        _attach(device, school, session)
        device.save()
        audit.record(
            Action.DEVICES_REGISTERED,
            device,
            actor=user,
            after={"prefix": device.prefix, "label": device.label},
        )
    return device


def resume_device(device: Device, school: School, session) -> Device:
    """Connexion depuis un appareil déjà enregistré : il reprend la nouvelle session."""
    if device.revoked_at is not None:
        raise BusinessError(DEVICE_REVOKED)
    _attach(device, school, session)
    device.save(update_fields=["session_key", "last_seen_at", "updated_at"])
    return device


def revoke_device(device: Device, *, actor: User) -> None:
    """« Déconnecter » : l'appareil ne sert plus (préfixe jamais redonné) et sa session est
    fermée ; il efface ses données au prochain contact."""
    if device.revoked_at is not None:
        return
    with transaction.atomic():
        device.revoked_at = timezone.now()
        device.save(update_fields=["revoked_at", "updated_at"])
        audit.record(Action.DEVICES_REVOKED, device, actor=actor)
    if device.session_key:
        import_module(settings.SESSION_ENGINE).SessionStore(device.session_key).delete()


def verify_signature(device: Device, message: bytes, signature: bytes) -> bool:
    """Signature ECDSA P-256 / SHA-256 faite par l'appareil avec WebCrypto (`r ‖ s`, 64 octets).
    Ne regarde pas la révocation : c'est à l'appelant de décider."""
    if len(signature) != 64:
        return False
    der = encode_dss_signature(
        int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
    )
    try:
        _load_public_key(device.public_key).verify(der, message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return False
    return True


def _attach(device: Device, school: School, session) -> None:
    if session.session_key is None:
        session.save()
    device.session_key = session.session_key
    device.last_seen_at = timezone.now()
    session[DEVICE_SESSION_KEY] = {"id": str(device.pk), "school": str(school.pk)}


def _next_prefix() -> str:
    """`P1`, `P2`… dans l'école courante : jamais redonné (un appareil révoqué garde le sien),
    jamais égal au code d'une caisse."""
    taken = set(Device.objects.values_list("prefix", flat=True))
    taken |= set(CashRegister.objects.values_list("code", flat=True))
    number = Device.objects.count() + 1
    while f"{PREFIX_LETTER}{number}" in taken:
        number += 1
    return f"{PREFIX_LETTER}{number}"


def _load_public_key(value: str) -> ec.EllipticCurvePublicKey:
    try:
        key = load_der_public_key(base64.b64decode(value, validate=True))
    except (ValueError, binascii.Error):
        key = None
    if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
        raise ValidationError(
            {"public_key": ValidationError(_("Invalid device key."), code="invalid_key")}
        )
    return key

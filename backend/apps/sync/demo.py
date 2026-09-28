"""Appareils de démonstration : un poste pour chaque caissier et secrétaire fictif, pour voir
« Appareils connectés » (Mon compte). Leur clé privée n'est gardée nulle part : ils ne signent
rien."""

import base64
from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.utils import timezone

from apps.accounts.demo import DEMO_ACCOUNTS
from apps.accounts.models import Membership
from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.sync.models import Device
from apps.sync.services import _next_prefix

DEMO_DEVICES = {"cashier": "PC Caisse · Windows · Edge", "secretary": "PC Secrétariat · Windows"}


def _public_key() -> str:
    key = ec.generate_private_key(ec.SECP256R1()).public_key()
    spki = key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(spki).decode()


def create_demo_devices(schools: dict[str, School]) -> None:
    """Crée les appareils qui manquent ; remet les autres comme au départ (pas déconnectés).
    Ceux que les comptes fictifs ont enregistrés en essayant sont déconnectés."""
    phones = [account.phone for account in DEMO_ACCOUNTS]
    for school in schools.values():
        members = (
            Membership.objects.filter(
                school=school,
                roles__code__in=DEMO_DEVICES,
                user__phone__in=phones,
            )
            .values_list("user", "roles__code")
            .distinct()
        )
        with use_school(school):
            kept = []
            for index, (user_id, role) in enumerate(members):
                device = Device.objects.filter(user_id=user_id, label=DEMO_DEVICES[role]).first()
                if device is None:
                    device = Device(
                        user_id=user_id,
                        label=DEMO_DEVICES[role],
                        prefix=_next_prefix(),
                        public_key=_public_key(),
                    )
                device.revoked_at = None
                device.last_seen_at = timezone.now() - timedelta(hours=2 + index)
                device.save()
                kept.append(device.pk)
            Device.objects.filter(user__phone__in=phones, revoked_at__isnull=True).exclude(
                pk__in=kept
            ).update(revoked_at=timezone.now())

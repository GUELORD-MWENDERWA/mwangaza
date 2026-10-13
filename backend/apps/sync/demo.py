"""Appareils de démonstration : le poste de chaque compte fictif qui en a un (`device`), pour voir
« Appareils connectés » (Mon compte). Leur clé privée n'est gardée nulle part : ils ne signent
rien."""

import base64
from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.utils import timezone

from apps.accounts.demo import demo_accounts
from apps.accounts.models import Membership
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace
from apps.sync.models import Device
from apps.sync.services import _next_prefix


def _public_key() -> str:
    key = ec.generate_private_key(ec.SECP256R1()).public_key()
    spki = key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(spki).decode()


def create_demo_devices(spaces: list[DemoSpace]) -> None:
    """Crée les appareils qui manquent ; remet les autres comme au départ (pas déconnectés).
    Ceux que les comptes fictifs ont enregistrés en essayant sont déconnectés."""
    for space in spaces:
        school = space.school
        accounts = demo_accounts(space)
        phones = [space.numbers.of(account.phone) for account in accounts]
        labels = {
            space.numbers.of(account.phone): account.device
            for account in accounts
            if account.device
        }
        members = (
            Membership.objects.filter(school=school, user__phone__in=labels)
            .order_by("user__phone")
            .values_list("user", "user__phone")
        )
        with use_school(school):
            kept = []
            for index, (user_id, phone) in enumerate(members):
                device = Device.objects.filter(user_id=user_id, label=labels[phone]).first()
                if device is None:
                    device = Device(
                        user_id=user_id,
                        label=labels[phone],
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

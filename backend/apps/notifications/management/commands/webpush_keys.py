"""Paire de clés Web Push (VAPID) de la plateforme, à créer une seule fois pour la production :
`python manage.py webpush_keys`, puis les deux lignes dans les variables d'environnement."""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Crée une paire de clés Web Push (VAPID) à mettre dans les variables d'environnement."

    def handle(self, *args, **options) -> None:
        key = ec.generate_private_key(ec.SECP256R1())
        public = key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        private = key.private_numbers().private_value.to_bytes(32, "big")
        self.stdout.write(f"WEBPUSH_VAPID_PUBLIC_KEY={_b64(public)}")
        self.stdout.write(f"WEBPUSH_VAPID_PRIVATE_KEY={_b64(private)}")

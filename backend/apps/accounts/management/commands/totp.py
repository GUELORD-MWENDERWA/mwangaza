"""`make totp` : code de double authentification du moment, pour essayer la connexion en
développement sans téléphone (comptes de démonstration, ou une clé donnée par l'activation)."""

import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import totp
from apps.accounts.demo import DEMO_TOTP_SECRET


class Command(BaseCommand):
    help = "Code de double authentification du moment (développement seulement)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--key", default=DEMO_TOTP_SECRET, help="Clé TOTP ; par défaut celle de make demo."
        )

    def handle(self, *args, key: str, **options):
        if not settings.DEBUG:
            raise CommandError("Refusé hors développement (DEBUG).")
        key = "".join(key.split()).upper()
        try:
            code = totp.code_at(key, totp.current_step())
        except ValueError as exc:
            raise CommandError("Clé TOTP invalide (lettres A à Z et chiffres 2 à 7).") from exc
        seconds_left = totp.PERIOD - int(time.time()) % totp.PERIOD
        self.stdout.write(f"{code[:3]} {code[3:]}  (valable encore {seconds_left} s)")

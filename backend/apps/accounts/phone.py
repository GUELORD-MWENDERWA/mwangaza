"""Numéros de téléphone, rangés au format international E.164 : +243971234567.

Le numéro identifie la personne sur toute la plateforme (`User.phone`). On accepte ce que les gens
tapent (`0971234567`, `+243 97 123 45 67`, `00243…`) et on range toujours la même forme.
"""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

E164_PATTERN = re.compile(r"\+[1-9]\d{7,14}")
# Longueur du numéro sans l'indicatif, pour les pays connus : RDC et voisins de Goma. Un chiffre de
# trop ou de moins est refusé au lieu d'enregistrer un numéro qui ne joindra personne.
NATIONAL_NUMBER_LENGTHS = {"243": 9, "250": 9, "256": 9, "257": 8}
_SEPARATORS = re.compile(r"[\s.\-()/]")


# Plage réservée aux comptes de démonstration (`03` § 4 bis) : en RDC, aucun vrai numéro ne
# commence par 0 après l'indicatif, ces comptes ne peuvent donc être ceux de personne. Ceux qu'on
# donne à taper commencent par `000` (+243 00…) : `0012…` serait lu comme un numéro international
# (`normalize_phone`).
DEMO_PHONE_PREFIX = "+2430"


def is_demo_phone(phone: str) -> bool:
    """`phone` (forme E.164) est-il dans la plage réservée aux espaces de démonstration ?"""
    return phone.startswith(DEMO_PHONE_PREFIX)


def demo_block(phone: str) -> int | None:
    """Bloc d'un numéro +243 00 BB… : celui d'un espace de démonstration créé depuis la console
    (`schools.demo.DemoNumbers.block`). `None` : pas un numéro de ces blocs."""
    block = phone[6:8] if phone.startswith(f"{DEMO_PHONE_PREFIX}0") else ""
    return int(block) if block.isdigit() else None


INVALID_PHONE_MESSAGE = _("Enter a valid phone number, for example 0971234567 or +243971234567.")


class InvalidPhoneError(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    """Forme E.164 du numéro ; `InvalidPhoneError` s'il ne peut pas en être un.

    `00` suivi d'un indicatif (jamais de 0 au début d'un indicatif) est un numéro international,
    comme `+…`. Sinon `0…` est un numéro national : l'indicatif du pays par défaut
    (`PHONE_DEFAULT_COUNTRY_CODE`, 243 pour la RDC) remplace le 0."""
    value = _SEPARATORS.sub("", str(raw))
    if value.startswith("00") and value[2:3] != "0":
        value = f"+{value[2:]}"
    elif value.startswith("0"):
        value = f"+{settings.PHONE_DEFAULT_COUNTRY_CODE}{value[1:]}"
    if not E164_PATTERN.fullmatch(value):
        raise InvalidPhoneError(raw)
    for country_code, length in NATIONAL_NUMBER_LENGTHS.items():
        if value.startswith(f"+{country_code}") and len(value) != 1 + len(country_code) + length:
            raise InvalidPhoneError(raw)
    return value


class PhoneNumberField(models.CharField):
    """Numéro rangé au format E.164 ; accepte à la saisie les formes courantes (voir
    `normalize_phone`), y compris dans l'administration et `createsuperuser`."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 16)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        try:
            return normalize_phone(value)
        except InvalidPhoneError:
            raise ValidationError(INVALID_PHONE_MESSAGE, code="invalid_phone") from None


def format_phone(phone: str) -> str:
    """« +243 97 123 45 67 » pour un numéro de la RDC, comme dans la Gestion ; sinon tel quel."""
    match = re.fullmatch(r"\+243(\d{2})(\d{3})(\d{2})(\d{2})", phone or "")
    return f"+243 {' '.join(match.groups())}" if match else phone or ""

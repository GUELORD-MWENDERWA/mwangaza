"""Double authentification (B4) : codes TOTP et codes de secours.

TOTP (RFC 6238, celui de Google Authenticator, Microsoft Authenticator ou Aegis) : code à
6 chiffres qui change toutes les 30 secondes, calculé à partir d'une clé partagée à l'activation.
Écrit avec la bibliothèque standard de Python et vérifié avec les vecteurs de test de la RFC.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

PERIOD = 30
DIGITS = 6
# Un code de la période précédente ou suivante est accepté aussi : horloge du téléphone un peu
# décalée, code tapé à la fin de sa période.
WINDOW = 1
ISSUER = "Mwangaza"

RECOVERY_CODE_COUNT = 8
# Majuscules et chiffres sans ceux qu'on confond en les recopiant (I, O, 0, 1) : 32 signes,
# 8 par code (40 bits).
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_RECOVERY_LENGTH = 8


def new_secret() -> str:
    """Clé de 160 bits (RFC 4226) en base32 : 32 caractères, à taper si on ne peut pas scanner."""
    return base64.b32encode(secrets.token_bytes(20)).decode()


def current_step(at: float | None = None) -> int:
    return int((time.time() if at is None else at) // PERIOD)


def code_at(secret: str, step: int, *, digits: int = DIGITS, digest=hashlib.sha1) -> str:
    """Code de la période `step` (HOTP de la RFC 4226 sur le compteur de la RFC 6238)."""
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    mac = hmac.new(key, struct.pack(">Q", step), digest).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def matching_step(
    secret: str, code: str, *, after: int = -1, at: float | None = None
) -> int | None:
    """Période du code s'il est valable maintenant (à une période près) et plus récent que
    `after`, la dernière période déjà utilisée : un code ne sert qu'une fois."""
    code = "".join(code.split())
    if len(code) != DIGITS or not code.isdigit():
        return None
    now = current_step(at)
    for step in range(now - WINDOW, now + WINDOW + 1):
        if step > after and hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str) -> str:
    """Adresse `otpauth://` du QR code à scanner avec l'application."""
    label = f"{quote(ISSUER)}:{quote(account)}"
    query = urlencode(
        {
            "secret": secret,
            "issuer": ISSUER,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": PERIOD,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def new_recovery_codes() -> list[str]:
    """8 codes de secours à usage unique, au format `7KQ4-M2XP` (maquette M1)."""
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_LENGTH))
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def normalize_recovery_code(code: str) -> str | None:
    """Code de secours sans tiret ni espace, en majuscules ; None si ce n'en est pas un."""
    raw = "".join(code.split()).replace("-", "").upper()
    if len(raw) != _RECOVERY_LENGTH or any(char not in _RECOVERY_ALPHABET for char in raw):
        return None
    return raw

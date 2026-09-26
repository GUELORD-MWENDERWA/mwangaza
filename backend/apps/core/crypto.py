"""Chiffrement de petites valeurs secrètes gardées en base (ex. clé TOTP d'un compte).

La clé de chiffrement est dérivée de `SECRET_KEY` (HKDF-SHA256) : aucun secret de plus à gérer.
Après un changement de `SECRET_KEY`, les anciennes clés listées dans `SECRET_KEY_FALLBACKS`
déchiffrent encore ; `encrypt` utilise toujours la nouvelle. Perdre `SECRET_KEY` rend ces
valeurs illisibles (pour la double authentification : chacun la réactive).
"""

import base64

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

_INFO = b"mwangaza.core.crypto"


class DecryptionError(Exception):
    """Valeur falsifiée, ou chiffrée avec une clé qui n'est plus connue."""


def _fernet(secret_key: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(
        secret_key.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


def _keys() -> MultiFernet:
    secret_keys = [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
    return MultiFernet([_fernet(secret_key) for secret_key in secret_keys])


def encrypt(value: str) -> str:
    """Texte chiffré et authentifié (Fernet : AES-128-CBC + HMAC-SHA256), différent à chaque
    appel."""
    return _keys().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _keys().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("Valeur chiffrée illisible avec les clés connues.") from exc

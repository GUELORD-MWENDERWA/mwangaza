"""Identifiants UUID v7 (RFC 9562) : triés par date de création, générables sans serveur.

Python 3.12 n'a pas `uuid.uuid7()` (arrivé en 3.14) : même algorithme ici, sans dépendance.
Horodatage de 48 bits en millisecondes, compteur de 42 bits (ordre croissant dans la même
milliseconde, même si l'horloge recule), puis 32 bits aléatoires : un identifiant ne permet pas
de deviner le suivant. À remplacer par `uuid.uuid7()` quand le minimum sera Python 3.14.
"""

import os
import threading
import time
import uuid

_COUNTER_MAX = (1 << 42) - 1
_VERSION_7_AND_VARIANT = (0x7 << 76) | (0b10 << 62)

_lock = threading.Lock()
_last_ms = 0
_last_counter = 0


def _new_counter() -> int:
    # Point de départ aléatoire, bit de poids fort à 0 pour laisser de la marge au compteur.
    return int.from_bytes(os.urandom(6)) & ((1 << 41) - 1)


def uuid7() -> uuid.UUID:
    global _last_ms, _last_counter
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms > _last_ms:
            timestamp_ms, counter = now_ms, _new_counter()
        else:
            timestamp_ms, counter = _last_ms, _last_counter + 1
            if counter > _COUNTER_MAX:
                timestamp_ms, counter = _last_ms + 1, _new_counter()
        _last_ms, _last_counter = timestamp_ms, counter

    tail = int.from_bytes(os.urandom(4))
    value = (
        (timestamp_ms & 0xFFFF_FFFF_FFFF) << 80
        | (counter >> 30) << 64
        | (counter & 0x3FFF_FFFF) << 32
        | tail
        | _VERSION_7_AND_VARIANT
    )
    return uuid.UUID(int=value)


def is_uuid7(value: object) -> bool:
    """Vrai si `value` (UUID ou texte) est un UUID v7 : sert à valider les identifiants créés
    hors ligne par les appareils."""
    if isinstance(value, str):
        try:
            value = uuid.UUID(value)
        except ValueError:
            return False
    return isinstance(value, uuid.UUID) and value.version == 7 and value.variant == uuid.RFC_4122

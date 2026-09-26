"""Chiffrement des petites valeurs secrètes gardées en base (`apps/core/crypto.py`)."""

import pytest

from apps.core.crypto import DecryptionError, decrypt, encrypt


def test_round_trip():
    token = encrypt("JBSWY3DPEHPK3PXP")

    assert "JBSWY3DPEHPK3PXP" not in token
    assert decrypt(token) == "JBSWY3DPEHPK3PXP"


def test_same_value_gives_a_different_text_each_time():
    assert encrypt("secret") != encrypt("secret")


def test_modified_text_is_refused():
    token = encrypt("secret")
    tampered = token[:-6] + ("A" if token[-6] != "A" else "B") + token[-5:]

    with pytest.raises(DecryptionError):
        decrypt(tampered)


def test_another_secret_key_cannot_read_it(settings):
    token = encrypt("secret")
    settings.SECRET_KEY = "une-autre-cle"

    with pytest.raises(DecryptionError):
        decrypt(token)


def test_old_key_still_reads_after_a_rotation(settings):
    old_token = encrypt("secret")
    settings.SECRET_KEY_FALLBACKS = [settings.SECRET_KEY]
    settings.SECRET_KEY = "nouvelle-cle"
    new_token = encrypt("secret")

    assert decrypt(old_token) == "secret"
    # Chiffré avec la nouvelle clé : l'ancienne seule ne le lit pas.
    settings.SECRET_KEY, settings.SECRET_KEY_FALLBACKS = settings.SECRET_KEY_FALLBACKS[0], []
    with pytest.raises(DecryptionError):
        decrypt(new_token)

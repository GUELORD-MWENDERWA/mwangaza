"""Lecture des variables d'environnement : une ligne `NOM=` vide dans `.env` vaut « absente »."""

import pytest

from config.settings.base import env, env_bool, env_list


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_variable_falls_back_to_default(monkeypatch, value):
    monkeypatch.setenv("MWANGAZA_TEST_VAR", value)

    assert env("MWANGAZA_TEST_VAR", "par-defaut") == "par-defaut"
    assert env("MWANGAZA_TEST_VAR") is None
    assert env_bool("MWANGAZA_TEST_VAR", True) is True
    assert env_list("MWANGAZA_TEST_VAR", "a,b") == ["a", "b"]


def test_set_variable_is_used(monkeypatch):
    monkeypatch.setenv("MWANGAZA_TEST_VAR", "valeur")

    assert env("MWANGAZA_TEST_VAR", "par-defaut") == "valeur"


def test_missing_variable_uses_default(monkeypatch):
    monkeypatch.delenv("MWANGAZA_TEST_VAR", raising=False)

    assert env("MWANGAZA_TEST_VAR", "par-defaut") == "par-defaut"
    assert env_bool("MWANGAZA_TEST_VAR") is False
    assert env_list("MWANGAZA_TEST_VAR") == []


def test_passwords_are_hashed_with_argon2():
    # Les tests hachent vite (MD5) ; les autres réglages hachent avec Argon2 (`03` § 8).
    from config.settings import base

    # Argon2 de Django, un hachage à la fois par processus (`core/hashers.py`, PERF.5a).
    assert base.PASSWORD_HASHERS[0] == "apps.core.hashers.SerialArgon2PasswordHasher"
    from django.contrib.auth.hashers import Argon2PasswordHasher

    from apps.core.hashers import SerialArgon2PasswordHasher

    assert issubclass(SerialArgon2PasswordHasher, Argon2PasswordHasher)
    # Anciens mots de passe (avant la 1.3) : lus, puis convertis à la connexion.
    assert "django.contrib.auth.hashers.PBKDF2PasswordHasher" in base.PASSWORD_HASHERS


def test_argon2_is_installed():
    from django.contrib.auth.hashers import Argon2PasswordHasher

    hasher = Argon2PasswordHasher()
    encoded = hasher.encode("un-mot-de-passe", hasher.salt())

    assert encoded.startswith("argon2$argon2id$")
    assert hasher.verify("un-mot-de-passe", encoded)


def test_password_needs_ten_characters(db):
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        validate_password("court-123")
    validate_password("assez-long-42")

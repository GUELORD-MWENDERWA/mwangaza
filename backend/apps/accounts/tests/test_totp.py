"""Codes TOTP (RFC 6238) et codes de secours (`apps/accounts/totp.py`)."""

import base64
import re
from urllib.parse import parse_qs, urlparse

import pytest

from apps.accounts import totp

# Clé des vecteurs de test des RFC 4226 et 6238 (SHA-1).
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()
AT = 1_700_000_000.0


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_rfc_6238_vectors(at, expected):
    assert totp.code_at(RFC_SECRET, totp.current_step(at), digits=8) == expected


@pytest.mark.parametrize(
    ("counter", "expected"),
    list(
        enumerate(
            [
                "755224",
                "287082",
                "359152",
                "969429",
                "338314",
                "254676",
                "287922",
                "162583",
                "399871",
                "520489",
            ]
        )
    ),
)
def test_rfc_4226_vectors(counter, expected):
    assert totp.code_at(RFC_SECRET, counter) == expected


def test_new_secret_has_160_bits():
    secret = totp.new_secret()

    assert re.fullmatch(r"[A-Z2-7]{32}", secret)
    assert len(base64.b32decode(secret)) == 20
    assert totp.new_secret() != secret


def test_code_is_accepted_one_period_around_now():
    secret = totp.new_secret()
    now = totp.current_step(AT)

    for step in (now - 1, now, now + 1):
        assert totp.matching_step(secret, totp.code_at(secret, step), at=AT) == step
    for step in (now - 2, now + 2):
        assert totp.matching_step(secret, totp.code_at(secret, step), at=AT) is None


def test_a_code_is_used_only_once():
    secret = totp.new_secret()
    now = totp.current_step(AT)
    code = totp.code_at(secret, now)

    assert totp.matching_step(secret, code, after=now - 1, at=AT) == now
    assert totp.matching_step(secret, code, after=now, at=AT) is None
    # Ni un code plus ancien que le dernier utilisé.
    assert totp.matching_step(secret, totp.code_at(secret, now - 1), after=now, at=AT) is None


def test_code_typed_with_spaces():
    secret = totp.new_secret()
    code = totp.code_at(secret, totp.current_step(AT))

    assert totp.matching_step(secret, f" {code[:3]} {code[3:]} ", at=AT) is not None


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12-456"])
def test_malformed_codes_are_refused(code):
    assert totp.matching_step(totp.new_secret(), code, at=AT) is None


def test_provisioning_uri_for_the_qr_code(db):
    uri = totp.provisioning_uri("JBSWY3DPEHPK3PXP", "+243970000000")

    parsed = urlparse(uri)
    assert (parsed.scheme, parsed.netloc) == ("otpauth", "totp")
    assert parsed.path == "/Mwangaza:%2B243970000000"
    assert parse_qs(parsed.query) == {
        "secret": ["JBSWY3DPEHPK3PXP"],
        "issuer": ["Mwangaza"],
        "algorithm": ["SHA1"],
        "digits": ["6"],
        "period": ["30"],
    }


def test_eight_recovery_codes_easy_to_copy():
    codes = totp.new_recovery_codes()

    assert len(codes) == len(set(codes)) == 8
    for code in codes:
        # Sans I, O, 0 ni 1, qu'on confond en recopiant.
        assert re.fullmatch(r"[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}", code)


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("7KQ4-M2XP", "7KQ4M2XP"),
        (" 7kq4 m2xp ", "7KQ4M2XP"),
        ("7KQ4M2XP", "7KQ4M2XP"),
        ("7KQ4-M2X0", None),
        ("7KQ4-M2X", None),
        ("123456", None),
    ],
)
def test_normalize_recovery_code(typed, expected):
    assert totp.normalize_recovery_code(typed) == expected

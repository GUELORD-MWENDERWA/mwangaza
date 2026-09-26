"""Numéro de téléphone : ce que les gens tapent → une seule forme rangée (E.164)."""

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.phone import InvalidPhoneError, PhoneNumberField, normalize_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0971234567", "+243971234567"),
        ("097 123 45 67", "+243971234567"),
        ("097-123-4567", "+243971234567"),
        ("(097) 123.45.67", "+243971234567"),
        ("+243971234567", "+243971234567"),
        ("+243 97 123 45 67", "+243971234567"),
        ("00243971234567", "+243971234567"),
        ("0812345678", "+243812345678"),
        # Pays voisins de Goma.
        ("+250788123456", "+250788123456"),
        ("+256772123456", "+256772123456"),
        ("+25779123456", "+25779123456"),
        # Autre pays : seulement le format international général.
        ("+33612345678", "+33612345678"),
        # Numéros de démonstration (0 après l'indicatif : aucun vrai numéro). « 000 » n'est pas
        # un préfixe international : aucun indicatif ne commence par 0.
        ("0000001001", "+243000001001"),
        ("0000000000", "+243000000000"),
        ("+243000001001", "+243000001001"),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "abc",
        "097123456a",
        "+243",
        "097123456",  # 8 chiffres après l'indicatif
        "09712345678",  # 10 chiffres après l'indicatif
        "+2430971234567",  # 0 national laissé après +243
        "+25078812345",  # Rwanda : 8 chiffres au lieu de 9
        "+0971234567",
        "+1234567",  # trop court
        "+1234567890123456",  # trop long
        "243971234567",  # sans + ni 0
    ],
)
def test_invalid_phone_is_refused(raw):
    with pytest.raises(InvalidPhoneError):
        normalize_phone(raw)


def test_default_country_code_is_a_setting(settings):
    settings.PHONE_DEFAULT_COUNTRY_CODE = "250"

    assert normalize_phone("0788123456") == "+250788123456"


def test_model_field_normalizes_and_explains():
    field = PhoneNumberField()

    assert field.clean("097 123 45 67", None) == "+243971234567"
    with pytest.raises(ValidationError) as error:
        field.clean("12", None)
    assert error.value.code == "invalid_phone"

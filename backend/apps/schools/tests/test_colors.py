"""Couleur de l'école (Q8) : texte blanc ou encre choisi pour un contraste d'au moins 4,5 : 1."""

import pytest
from django.core.exceptions import ValidationError

from apps.schools import colors
from apps.schools.colors import INK, WHITE


def test_contrast_of_black_and_white_is_21():
    assert colors.contrast("#000000", "#FFFFFF") == pytest.approx(21)
    assert colors.contrast("#FFFFFF", "#FFFFFF") == pytest.approx(1)


def test_contrast_is_symmetric():
    assert colors.contrast("#0E5C6B", INK) == pytest.approx(colors.contrast(INK, "#0E5C6B"))


@pytest.mark.parametrize(
    ("color", "text"),
    [
        ("#0E5C6B", WHITE),  # couleur Mwangaza (défaut)
        ("#003C6C", WHITE),  # ITIG de démonstration
        ("#000000", WHITE),
        ("#FFFFFF", INK),
        ("#F2C94C", INK),  # jaune
        ("#B00020", WHITE),  # rouge foncé
    ],
)
def test_text_color_is_the_most_readable_of_white_and_ink(color, text):
    assert colors.text_color(color) == text
    assert colors.contrast(color, text) >= colors.MIN_CONTRAST


def test_pure_red_is_readable_with_neither_white_nor_ink():
    assert colors.contrast("#FF0000", WHITE) < colors.MIN_CONTRAST
    assert colors.contrast("#FF0000", INK) < colors.MIN_CONTRAST
    assert colors.text_color("#FF0000") is None


def test_a_nearby_readable_shade_is_proposed():
    proposal = colors.nearby_readable("#FF0000")
    assert colors.text_color(proposal) is not None
    # Même teinte (rouge), à peine plus sombre ou plus claire.
    red, green, blue = colors.rgb(proposal)
    assert green == blue
    assert red > 200


def test_a_readable_color_is_its_own_proposal():
    assert colors.nearby_readable("#0E5C6B") == "#0E5C6B"


def test_normalize_accepts_lowercase_and_short_forms():
    assert colors.normalize("#0e5c6b") == "#0E5C6B"
    assert colors.normalize(" #abc ") == "#AABBCC"


@pytest.mark.parametrize("value", ["", "0E5C6B", "#0E5C6", "#GGGGGG", "red", "#0E5C6B00"])
def test_normalize_refuses_other_formats(value):
    with pytest.raises(ValueError):
        colors.normalize(value)


def test_validator_refuses_an_unreadable_color_and_proposes_one():
    with pytest.raises(ValidationError) as error:
        colors.validate_school_color("#FF0000")
    proposal = colors.nearby_readable("#FF0000")
    assert error.value.code == "unreadable_color"
    assert proposal in str(error.value)


def test_validator_refuses_a_malformed_color():
    with pytest.raises(ValidationError) as error:
        colors.validate_school_color("rouge")
    assert error.value.code == "invalid_color"


def test_validator_accepts_a_readable_color():
    colors.validate_school_color("#003C6C")

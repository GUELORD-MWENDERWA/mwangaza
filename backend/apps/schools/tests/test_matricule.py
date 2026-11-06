"""Format du matricule (C3) : variables, formats refusés, rendu."""

import itertools

import pytest
from django.core.exceptions import ValidationError

from apps.schools.matricule import check_ok, default_format, render, validate_matricule_format


@pytest.mark.parametrize(
    "value",
    [
        "ITIG-{AAAA}-{0000}",
        "{AA}{000}",
        "LV/{AA}/{000000}",
        "ITIG-{OPT}-{AAAA}-{0000}",
        "X.{AAAA}_{0000}",
        "ITIG-{AA}-{0000}-{C}",
    ],
)
def test_accepted_formats(value):
    validate_matricule_format(value)


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("ITIG-{AAAA}-0000", "matricule_number_missing"),
        ("ITIG-{0000}", "matricule_year_missing"),
        ("{AAAA}-{0000}-{000}", "matricule_number_twice"),
        ("ITIG-{ANNEE}-{0000}", "matricule_unknown_variable"),
        ("ITIG-{00}-{AAAA}", "matricule_unknown_variable"),
        ("ITIG-{0000000}-{AAAA}", "matricule_unknown_variable"),
        ("ITIG-{}-{AAAA}-{0000}", "matricule_unknown_variable"),
        ("ITIG-{AAAA-{0000}", "matricule_braces"),
        ("ITIG-{AAAA}}-{0000}", "matricule_braces"),
        ("ÉCOLE-{AAAA}-{0000}", "matricule_characters"),
        ("ITIG {AAAA} {0000}", "matricule_characters"),
        ("ITIG-{C}-{AA}-{0000}", "matricule_check_place"),
        ("ITIG-{AA}-{0000}{C}{C}", "matricule_check_place"),
    ],
)
def test_refused_formats(value, code):
    with pytest.raises(ValidationError) as error:
        validate_matricule_format(value)
    assert error.value.code == code


@pytest.mark.parametrize(
    ("template", "number", "track", "expected"),
    [
        ("ITIG-{AAAA}-{0000}", 612, "", "ITIG-2026-0612"),
        ("{AA}{000}", 7, "", "26007"),
        ("ITIG-{0000}-{AAAA}", 12345, "", "ITIG-12345-2026"),  # plus de chiffres que prévu
        ("ITIG-{OPT}-{AAAA}-{0000}", 1, "ELEC", "ITIG-ELEC-2026-0001"),
        # Classe sans option : la variable disparaît avec un séparateur voisin.
        ("ITIG-{OPT}-{AAAA}-{0000}", 1, "", "ITIG-2026-0001"),
        ("{OPT}/{AA}/{0000}", 1, "", "26/0001"),
        ("ITIG-{AAAA}-{0000}-{OPT}", 1, "", "ITIG-2026-0001"),
        ("ITIG{OPT}{AAAA}{0000}", 1, "", "ITIG20260001"),
        # Clé de contrôle (MAT.1) : un chiffre de plus, calculé sur les chiffres qui précèdent.
        ("ITIG-{AA}-{0000}-{C}", 612, "", "ITIG-26-0612-5"),
        ("LV/{OPT}/{AA}/{000}{C}", 7, "ELEC", "LV/ELEC/26/0075"),
    ],
)
def test_render(template, number, track, expected):
    assert render(template, year=2026, number=number, track_code=track) == expected


def test_default_format_uses_the_school_code():
    assert default_format("itig") == "ITIG-{AAAA}-{0000}"
    validate_matricule_format(default_format("saint-paul"))


def test_the_check_key_refuses_every_single_typo_and_swap_of_neighbours():
    """MAT.1 : un matricule mal tapé à la porte ou à la caisse ne tombe jamais sur un autre."""
    for number in (1, 42, 612, 9090):
        value = render("ITIG-{AA}-{0000}-{C}", year=2026, number=number)
        assert check_ok(value)
        digits = [i for i, char in enumerate(value) if char.isdigit()]
        for i in digits:
            for wrong in "0123456789".replace(value[i], ""):
                assert not check_ok(value[:i] + wrong + value[i + 1 :])
        for i, j in itertools.pairwise(digits):
            if j == i + 1 and value[i] != value[j]:
                swapped = value[:i] + value[j] + value[i] + value[j + 1 :]
                assert not check_ok(swapped)

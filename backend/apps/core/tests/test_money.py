"""Montants en entiers (centimes USD, francs CDF), jamais de float ; conversion selon Q4."""

from decimal import Decimal

import pytest

from apps.core.money import (
    Currency,
    CurrencyMismatchError,
    Money,
    format_amount,
    percent_of,
    prorate,
)

USD = Currency.USD
CDF = Currency.CDF


# Construction


def test_money_keeps_integer_amount_and_currency():
    money = Money(15025, USD)

    assert money.amount_minor == 15025
    assert money.currency == "USD"


def test_money_accepts_currency_code_as_text():
    assert Money(30000, "CDF") == Money(30000, CDF)


@pytest.mark.parametrize("amount", [150.25, Decimal("150.25"), "15025", True, None])
def test_money_refuses_anything_but_an_integer(amount):
    with pytest.raises(TypeError):
        Money(amount, USD)


@pytest.mark.parametrize("currency", ["EUR", "usd", "", None])
def test_money_refuses_unknown_currency(currency):
    with pytest.raises(ValueError):
        Money(100, currency)


def test_money_is_immutable():
    money = Money(100, USD)

    with pytest.raises(AttributeError):
        money.amount_minor = 200


def test_zero():
    assert Money.zero(CDF) == Money(0, CDF)
    assert Money.zero(CDF).is_zero()
    assert not Money(1, CDF).is_zero()


# Unités principales (dollars, francs)


@pytest.mark.parametrize(
    ("value", "currency", "expected"),
    [
        ("150.25", USD, 15025),
        ("150", USD, 15000),
        ("0.05", USD, 5),
        (Decimal("-12.50"), USD, -1250),
        (150, USD, 15000),
        ("285000", CDF, 285000),
        (Decimal("30000"), CDF, 30000),
    ],
)
def test_from_major(value, currency, expected):
    assert Money.from_major(value, currency) == Money(expected, currency)


@pytest.mark.parametrize(
    ("value", "currency"),
    [("150.255", USD), ("30000.5", CDF), ("abc", USD), ("", USD), ("NaN", USD), ("Infinity", CDF)],
)
def test_from_major_refuses_invalid_or_too_precise_amounts(value, currency):
    with pytest.raises(ValueError):
        Money.from_major(value, currency)


@pytest.mark.parametrize("value", [150.25, True])
def test_from_major_refuses_float_and_bool(value):
    with pytest.raises(TypeError):
        Money.from_major(value, USD)


def test_to_major():
    assert Money(15025, USD).to_major() == Decimal("150.25")
    assert Money(5, USD).to_major() == Decimal("0.05")
    assert Money(285000, CDF).to_major() == Decimal("285000")


# Calculs


def test_add_and_subtract_same_currency():
    assert Money(15000, USD) + Money(2525, USD) == Money(17525, USD)
    assert Money(15000, USD) - Money(2525, USD) == Money(12475, USD)
    assert -Money(100, CDF) == Money(-100, CDF)


def test_multiply_by_integer():
    assert Money(2500, USD) * 10 == Money(25000, USD)
    assert 3 * Money(10000, CDF) == Money(30000, CDF)


@pytest.mark.parametrize("factor", [1.5, Decimal("1.5"), True])
def test_multiply_refuses_non_integer_factor(factor):
    with pytest.raises(TypeError):
        Money(100, USD) * factor


def test_sum_of_amounts():
    amounts = [Money(1000, USD), Money(2000, USD), Money(3000, USD)]

    assert sum(amounts, Money.zero(USD)) == Money(6000, USD)


def test_operations_between_currencies_are_refused():
    with pytest.raises(CurrencyMismatchError):
        Money(100, USD) + Money(100, CDF)
    with pytest.raises(CurrencyMismatchError):
        Money(100, USD) - Money(100, CDF)
    with pytest.raises(CurrencyMismatchError):
        _ = Money(100, USD) < Money(100, CDF)


def test_adding_a_plain_number_is_refused():
    with pytest.raises(TypeError):
        Money(100, USD) + 1


def test_comparisons_same_currency():
    assert Money(100, USD) < Money(200, USD)
    assert Money(200, USD) >= Money(200, USD)
    assert Money(300, USD) > Money(200, USD)
    assert Money(100, USD) <= Money(100, USD)
    assert Money(100, USD) != Money(100, CDF)


# Conversion (décision Q4) : taux toujours USD → CDF, tel que saisi.

RATE = Decimal("2850")


@pytest.mark.parametrize(
    ("amount", "rate", "expected"),
    [
        (15000, RATE, 427500),  # 150,00 $ fois 2 850 = 427 500 FC
        (1, RATE, 29),  # 0,01 $ = 28,5 FC → 29 (demi supérieur)
        (1, Decimal("2849"), 28),  # 28,49 FC → 28
        (15025, Decimal("2850.5"), 428288),  # 150,25 fois 2 850,5 = 428 287,625 → 428 288
        (0, RATE, 0),
    ],
)
def test_convert_usd_to_cdf_multiplies_and_rounds_half_up(amount, rate, expected):
    assert Money(amount, USD).convert(CDF, rate) == Money(expected, CDF)


@pytest.mark.parametrize(
    ("amount", "rate", "expected"),
    [
        (427500, RATE, 15000),  # 427 500 FC ÷ 2 850 = 150,00 $
        (100000, RATE, 3509),  # 35,087… $ → 35,09 $
        (57, Decimal("2850"), 2),  # 0,02 $ exactement
        (1425, RATE, 50),  # 0,50 $
        (14, Decimal("2800"), 1),  # 0,005 $ → 0,01 $ (demi supérieur)
        (13, Decimal("2800"), 0),  # 0,00464… $ → 0,00 $
    ],
)
def test_convert_cdf_to_usd_divides_and_rounds_half_up(amount, rate, expected):
    assert Money(amount, CDF).convert(USD, rate) == Money(expected, USD)


def test_convert_round_trip_stays_within_one_unit():
    money = Money(12345, USD)

    back = money.convert(CDF, RATE).convert(USD, RATE)

    assert abs(back.amount_minor - money.amount_minor) <= 1


def test_convert_to_same_currency_returns_same_amount():
    assert Money(15000, USD).convert(USD, RATE) == Money(15000, USD)


@pytest.mark.parametrize("rate", [2850.0, 2850, "2850", None])
def test_convert_refuses_rate_that_is_not_decimal(rate):
    with pytest.raises(TypeError):
        Money(100, USD).convert(CDF, rate)


@pytest.mark.parametrize("rate", [Decimal("0"), Decimal("-2850"), Decimal("NaN")])
def test_convert_refuses_zero_or_negative_rate(rate):
    with pytest.raises(ValueError):
        Money(100, USD).convert(CDF, rate)


# Réductions (E3)


@pytest.mark.parametrize(
    ("amount", "percent", "expected"),
    [(36000, 25, 9000), (12345, 10, 1235), (12344, 10, 1234), (25000, 100, 25000), (999, 0, 0)],
)
def test_percent_rounds_half_up_to_the_unit(amount, percent, expected):
    assert percent_of(amount, percent) == expected


@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    [
        (9000, [12000, 12000, 12000], [3000, 3000, 3000]),
        (5000, [12000, 12000, 12000], [1667, 1667, 1666]),
        (1000, [10000, 5000, 5000], [500, 250, 250]),
        (2, [1, 1, 1], [1, 1, 0]),
        (36000, [12000, 12000, 12000], [12000, 12000, 12000]),
    ],
)
def test_prorate_adds_up_exactly_and_the_last_parts_absorb_the_rounding(total, weights, expected):
    assert prorate(total, weights) == expected


def test_prorate_and_percent_refuse_floats():
    with pytest.raises(TypeError):
        prorate(10.0, [1, 2])
    with pytest.raises(TypeError):
        percent_of(1000, 12.5)


def test_format_amount_matches_the_interface_for_printed_documents():
    """Même texte que `formatAmount` de `@mwangaza/money` (espaces insécables)."""
    assert [
        format_amount(123456, "USD"),
        format_amount(5, "USD"),
        format_amount(1260000, "CDF"),
        format_amount(-2500, "USD"),
    ] == ["1\xa0234,56\xa0$", "0,05\xa0$", "1\xa0260\xa0000\xa0FC", "\u221225,00\xa0$"]
    with pytest.raises(TypeError):
        format_amount(12.5, "USD")

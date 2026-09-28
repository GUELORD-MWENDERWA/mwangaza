"""Montants : entiers dans la plus petite unité (centimes USD, francs CDF) + devise.

Jamais de float. Règles : `docs/03-architecture-technique.md` § 6, `docs/04-modele-de-donnees.md`
§ 4, skill `argent`.
L'affichage (`1 234,56 $`, `1 260 000 FC`) se fait dans l'interface, pas ici.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import models
from django.utils.translation import gettext_lazy as _


class Currency(models.TextChoices):
    USD = "USD", _("US dollar")
    CDF = "CDF", _("Congolese franc")


# Nombre de décimales de la plus petite unité utilisée : centime pour USD, franc pour CDF.
DECIMALS = {Currency.USD: 2, Currency.CDF: 0}


class CurrencyMismatchError(ValueError):
    """Opération entre deux devises différentes : convertir d'abord avec un taux."""


def _require_int(value: object, what: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{what} doit être un entier (int), pas {type(value).__name__}")
    return value


@dataclass(frozen=True, slots=True)
class Money:
    amount_minor: int
    currency: Currency

    def __post_init__(self) -> None:
        _require_int(self.amount_minor, "amount_minor")
        object.__setattr__(self, "currency", Currency(self.currency))

    @classmethod
    def zero(cls, currency: Currency | str) -> "Money":
        return cls(0, currency)

    @classmethod
    def from_major(cls, value: Decimal | str | int, currency: Currency | str) -> "Money":
        """`"150.25"` USD → 15025. Refuse les décimales en trop (pas d'arrondi caché)."""
        if isinstance(value, float | bool):
            raise TypeError("un montant ne se donne jamais en float")
        currency = Currency(currency)
        try:
            major = Decimal(value)
        except InvalidOperation as error:
            raise ValueError(f"montant illisible : {value!r}") from error
        if not major.is_finite():
            raise ValueError(f"montant illisible : {value!r}")
        minor = major.scaleb(DECIMALS[currency])
        if minor != minor.to_integral_value():
            raise ValueError(f"{value} {currency} a trop de décimales")
        return cls(int(minor), currency)

    def to_major(self) -> Decimal:
        return Decimal(self.amount_minor).scaleb(-DECIMALS[self.currency])

    def is_zero(self) -> bool:
        return self.amount_minor == 0

    def convert(self, currency: Currency | str, rate_usd_to_cdf: Decimal) -> "Money":
        """Conversion avec le taux USD → CDF tel que saisi (décision Q4).

        USD → CDF : multiplier ; CDF → USD : diviser (jamais multiplier par 1/taux).
        Arrondi demi supérieur à l'unité de la devise cible, calculé en Decimal.
        """
        if type(rate_usd_to_cdf) is not Decimal:
            raise TypeError("le taux doit être un Decimal")
        if not rate_usd_to_cdf.is_finite() or rate_usd_to_cdf <= 0:
            raise ValueError(f"taux invalide : {rate_usd_to_cdf}")
        currency = Currency(currency)
        if currency == self.currency:
            return self
        if currency == Currency.CDF:
            target_major = self.to_major() * rate_usd_to_cdf
        else:
            target_major = self.to_major() / rate_usd_to_cdf
        target_minor = target_major.scaleb(DECIMALS[currency])
        return Money(int(target_minor.quantize(Decimal(1), rounding=ROUND_HALF_UP)), currency)

    def _same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"{self.currency} et {other.currency}")

    def __add__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount_minor, self.currency)

    def __mul__(self, factor: int) -> "Money":
        return Money(self.amount_minor * _require_int(factor, "le multiplicateur"), self.currency)

    __rmul__ = __mul__

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return self.amount_minor < other.amount_minor

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return self.amount_minor <= other.amount_minor

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return self.amount_minor > other.amount_minor

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return self.amount_minor >= other.amount_minor


def percent_of(amount_minor: int, percent: int) -> int:
    """`percent` % d'un montant positif, arrondi demi supérieur à l'unité de la devise (réduction
    en %, skill `argent`), en entiers seulement."""
    amount_minor, percent = _require_int(amount_minor, "montant"), _require_int(percent, "%")
    if amount_minor < 0 or percent < 0:
        raise ValueError("montant et pourcentage positifs seulement")
    return (amount_minor * percent * 2 + 100) // 200


def prorate(total_minor: int, weights: list[int]) -> list[int]:
    """`total_minor` réparti au prorata de `weights` (montants positifs), en entiers dont la
    somme vaut exactement `total_minor` : chaque part arrondie à l'inférieur, puis une unité de
    plus aux restes les plus grands, à égalité aux premières ; l'écart d'arrondi tombe ainsi sur
    les dernières parts. Aucune part ne dépasse son poids si `total_minor` ≤ leur somme."""
    total_minor = _require_int(total_minor, "montant")
    base = sum(_require_int(weight, "montant") for weight in weights)
    if base <= 0 or total_minor < 0 or any(weight < 0 for weight in weights):
        raise ValueError("répartition impossible")
    shares, remainders = [], []
    for index, weight in enumerate(weights):
        share, remainder = divmod(total_minor * weight, base)
        shares.append(share)
        remainders.append((-remainder, index))
    for _remainder, index in sorted(remainders)[: total_minor - sum(shares)]:
        shares[index] += 1
    return shares

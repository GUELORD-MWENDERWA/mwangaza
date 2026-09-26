import zoneinfo
from contextlib import suppress
from functools import cache

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.core.money import Currency
from apps.core.tenancy import RESERVED_SUBDOMAINS
from apps.schools import colors
from apps.schools.logos import logo_path, validate_logo

# Le code est le sous-domaine de l'école : 2 à 30 caractères, minuscules, chiffres, tirets.
CODE_PATTERN = r"^[a-z0-9][a-z0-9-]{0,28}[a-z0-9]$"
# Goma est en UTC+2 ; Kinshasa (UTC+1) : `Africa/Kinshasa`.
DEFAULT_TIMEZONE = "Africa/Lubumbashi"


def validate_not_reserved(value: str) -> None:
    if value in RESERVED_SUBDOMAINS:
        raise ValidationError(_("This code is reserved by the platform."), code="reserved")


@cache
def _timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def validate_timezone(value: str) -> None:
    if value not in _timezones():
        raise ValidationError(
            _("Unknown time zone, e.g. Africa/Lubumbashi."), code="invalid_timezone"
        )


def default_currencies() -> list[str]:
    return [Currency.USD, Currency.CDF]


def sorted_currencies(currencies) -> list[str]:
    """Sans doublon, dans l'ordre de `Currency` (USD, puis CDF)."""
    return [currency for currency in Currency.values if currency in set(currencies)]


class School(BaseModel):
    """École [G]. Tout ce qui est propre à une école se règle ici, jamais dans le code.
    Champs de `docs/04-modele-de-donnees.md` § 1 ajoutés avec leur tâche (1.7, 3.2…)."""

    class Status(models.TextChoices):
        TRIAL = "trial", _("Trial")
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")

    code = models.CharField(
        _("code"),
        max_length=30,
        unique=True,
        validators=[
            RegexValidator(
                CODE_PATTERN,
                _("2 to 30 characters: lowercase letters, digits and hyphens (not at the ends)."),
            ),
            validate_not_reserved,
        ],
        help_text=_(
            "Subdomain of the school: {code}.mwangaza.school. Changed by the platform only: "
            "the old address stops working."
        ),
    )
    # Nom court : menu, reçu thermique, portail (M5).
    name = models.CharField(_("name"), max_length=200)
    # Reçus A4, fiches, bulletins (M5).
    official_name = models.CharField(_("official name"), max_length=255, blank=True)
    logo = models.FileField(
        _("logo"),
        upload_to=logo_path,
        blank=True,
        validators=[validate_logo],
        help_text=_("PNG, JPEG or SVG, 1 MB at most."),
    )
    # Q8 : choisie par l'école ; texte blanc ou encre choisi pour rester lisible (`colors.py`).
    primary_color = models.CharField(
        _("colour"),
        max_length=7,
        default=colors.DEFAULT_COLOR,
        validators=[colors.validate_school_color],
        help_text=_("Printed documents and the school badge, e.g. #0E5C6B."),
    )
    timezone = models.CharField(
        _("time zone"),
        max_length=64,
        default=DEFAULT_TIMEZONE,
        validators=[validate_timezone],
        help_text=_("Dates and times of the school, e.g. Africa/Lubumbashi (Goma)."),
    )
    enabled_currencies = ArrayField(
        models.CharField(max_length=3, choices=Currency.choices),
        verbose_name=_("currencies"),
        default=default_currencies,
    )
    default_currency = models.CharField(
        _("main currency"),
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
        help_text=_("Currency of the reports."),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.TRIAL
    )
    # Abonnement, saisi à la main par le super-admin en V1.0 (A2) ; facturation : 7.2.
    plan = models.CharField(
        _("plan"), max_length=50, blank=True, help_text=_("e.g. Discovery, Standard.")
    )
    trial_ends_on = models.DateField(_("end of the trial"), null=True, blank=True)
    paid_until = models.DateField(_("paid until"), null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("school")
        verbose_name_plural = _("schools")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__regex=CODE_PATTERN), name="school_code_format"
            ),
            models.CheckConstraint(
                condition=models.Q(primary_color__regex=r"^#[0-9A-F]{6}$"),
                name="school_color_format",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        with suppress(ValueError):  # message du validateur du champ
            self.primary_color = colors.normalize(self.primary_color)
        self.enabled_currencies = sorted_currencies(self.enabled_currencies or [])
        if not self.enabled_currencies:
            raise ValidationError(
                {"enabled_currencies": _("Choose at least one currency.")}, code="no_currency"
            )
        if self.default_currency not in self.enabled_currencies:
            message = _("The main currency must be one of the school's currencies.")
            raise ValidationError({"default_currency": message}, code="default_currency_disabled")

    @property
    def url(self) -> str:
        """Adresse de l'école : https://{code}.mwangaza.school (`SCHOOL_URL`)."""
        return settings.SCHOOL_URL.format(code=self.code)

    @property
    def text_color(self) -> str:
        """Couleur du texte posé sur `primary_color` : blanc ou encre."""
        return colors.text_color(self.primary_color) or colors.WHITE

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.core.tenancy import RESERVED_SUBDOMAINS

# Le code est le sous-domaine de l'école : 2 à 30 caractères, minuscules, chiffres, tirets.
CODE_PATTERN = r"^[a-z0-9][a-z0-9-]{0,28}[a-z0-9]$"


def validate_not_reserved(value: str) -> None:
    if value in RESERVED_SUBDOMAINS:
        raise ValidationError(_("This code is reserved by the platform."), code="reserved")


class School(BaseModel):
    """École [G]. Tout ce qui est propre à une école se règle ici, jamais dans le code.
    Champs de `docs/04-modele-de-donnees.md` § 1 ajoutés avec leur tâche (1.5, 1.7, 2.5…)."""

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
        help_text=_("Subdomain of the school: {code}.mwangaza.school"),
    )
    name = models.CharField(_("name"), max_length=200)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.TRIAL
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("school")
        verbose_name_plural = _("schools")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__regex=CODE_PATTERN), name="school_code_format"
            )
        ]

    def __str__(self) -> str:
        return self.name

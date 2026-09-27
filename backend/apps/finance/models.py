"""Configuration des frais (`docs/04-modele-de-donnees.md` § 4, E1, E2, E5) : types de frais,
barèmes d'une année et leurs tranches, taux de change de l'année.

Montants en entiers dans la plus petite unité de la devise du barème (skill `argent`).
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.core.money import Currency
from apps.core.tenancy import TenantManager, TenantQuerySet
from apps.schools.models import AcademicYear, ClassGroup, Level, Track


class FeeType(TenantModel):
    """Type de frais [T] (« Minerval », « Frais d'atelier ») ; pas de devise ici : elle est
    choisie dans chaque barème."""

    class Category(models.TextChoices):
        TUITION = "tuition", _("Tuition")
        REGISTRATION = "registration", _("Registration")
        OPERATING = "operating", _("Operating costs")
        ANCILLARY = "ancillary", _("Ancillary fees")
        UNIFORM = "uniform", _("Uniform")
        TRANSPORT = "transport", _("Transport")
        CANTEEN = "canteen", _("Canteen")
        EXTRACURRICULAR = "extracurricular", _("Extracurricular")
        OFFICIAL_EXAM = "official_exam", _("Official exam")
        CUSTOM = "custom", _("Other")

    name = models.CharField(_("name"), max_length=80)
    category = models.CharField(_("category"), max_length=20, choices=Category.choices)
    # Alimentera la prime des enseignants (paie, V1.1).
    funds_teacher_bonus = models.BooleanField(_("funds the teacher bonus"), default=False)
    accounting_code = models.CharField(_("accounting code"), max_length=20, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("fee type")
        verbose_name_plural = _("fee types")
        constraints = [
            models.UniqueConstraint(
                "school", models.functions.Lower("name"), name="fee_type_name_unique_per_school"
            )
        ]

    def __str__(self) -> str:
        return self.name


class FeeRule(TenantModel):
    """Barème [T] : montant d'un type de frais pour une année, dans une devise, pour toute
    l'école ou une seule portée (niveau, option ou classe), découpé en tranches.

    Au plus un barème par type de frais et par portée dans l'année. Pour un élève, le barème
    applicable est le plus précis : classe, puis niveau, puis option, puis toute l'école (2.6)."""

    class ScheduleKind(models.TextChoices):
        INSTALLMENTS = "installments", _("Installments")
        MONTHLY = "monthly", _("Monthly")
        SINGLE = "single", _("Single payment")

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="fee_rules", verbose_name=_("year")
    )
    fee_type = models.ForeignKey(
        FeeType, on_delete=models.PROTECT, related_name="rules", verbose_name=_("fee type")
    )
    level = models.ForeignKey(
        Level, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    track = models.ForeignKey(
        Track, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    total_amount_minor = models.BigIntegerField(_("total"), validators=[MinValueValidator(1)])
    schedule_kind = models.CharField(_("schedule"), max_length=15, choices=ScheduleKind.choices)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("fee rule")
        verbose_name_plural = _("fee rules")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "fee_type", "level", "track", "class_group"],
                nulls_distinct=False,
                name="fee_rule_unique_scope",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(level__isnull=True, track__isnull=True)
                    | models.Q(level__isnull=True, class_group__isnull=True)
                    | models.Q(track__isnull=True, class_group__isnull=True)
                ),
                name="fee_rule_single_scope",
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount_minor__gt=0), name="fee_rule_total_positive"
            ),
        ]
        indexes = [models.Index(fields=["school", "academic_year"], name="fee_rule_school_year")]

    def __str__(self) -> str:
        return f"{self.fee_type} — {self.scope_name}"

    @property
    def scope_name(self) -> str:
        target = self.class_group or self.level or self.track
        return str(target) if target else ""


class InstallmentTemplate(TenantModel):
    """Tranche d'un barème [T] (« 1re tranche », 120,00 $, avant le 15/10/2026), dans la devise
    du barème. Somme des tranches = total du barème (vérifié par le service)."""

    fee_rule = models.ForeignKey(
        FeeRule, on_delete=models.CASCADE, related_name="installments", verbose_name=_("fee rule")
    )
    label = models.CharField(_("label"), max_length=40)
    amount_minor = models.BigIntegerField(_("amount"), validators=[MinValueValidator(1)])
    due_on = models.DateField(_("due date"))
    order = models.PositiveSmallIntegerField(_("order"))

    class Meta:
        ordering = ["order"]
        verbose_name = _("installment")
        verbose_name_plural = _("installments")
        constraints = [
            models.UniqueConstraint(fields=["fee_rule", "order"], name="installment_order_unique"),
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0), name="installment_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return self.label


IMMUTABLE_RATE = "Un taux enregistré ne se modifie pas et ne s'efface pas : ajouter une ligne."


class ImmutableRateError(Exception):
    """Erreur de programmation : modification ou suppression d'un taux enregistré."""


class ExchangeRateQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        raise ImmutableRateError(IMMUTABLE_RATE)

    def delete(self):
        raise ImmutableRateError(IMMUTABLE_RATE)


class ExchangeRateManager(TenantManager.from_queryset(ExchangeRateQuerySet)):
    pass


class ExchangeRate(TenantModel):
    """Taux de change de l'année [T] [I] : francs pour 1 dollar, tel que saisi (décision Q4),
    fixe toute l'année. Une correction ajoute une ligne avec son motif ; le taux en vigueur est
    la dernière ligne de l'année. Qui et quand : `created_by`, `created_at`. Ni modifiable ni
    effaçable, ici et par la base (déclencheur de la migration 0001)."""

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="exchange_rates",
        verbose_name=_("year"),
    )
    from_currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.USD, editable=False
    )
    to_currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.CDF, editable=False
    )
    rate = models.DecimalField(_("rate"), max_digits=14, decimal_places=6)
    # Obligatoire pour une correction (vérifié par le service).
    reason = models.CharField(_("reason"), max_length=200, blank=True)

    objects = ExchangeRateManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("exchange rate")
        verbose_name_plural = _("exchange rates")
        constraints = [
            models.CheckConstraint(condition=models.Q(rate__gt=0), name="exchange_rate_positive")
        ]
        indexes = [
            models.Index(fields=["school", "academic_year", "-created_at"], name="rate_school_year")
        ]

    def __str__(self) -> str:
        return f"1 {self.from_currency} = {self.rate} {self.to_currency}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRateError(IMMUTABLE_RATE)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRateError(IMMUTABLE_RATE)

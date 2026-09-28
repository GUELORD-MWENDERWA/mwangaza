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


class StudentCharge(TenantModel):
    """Ce que doit un élève pour son année [T] : une ligne par tranche du barème qui s'applique
    à sa classe (`source=rule`), ou par versement d'un échéancier particulier (`source=custom`,
    2.6.2). Montant dans la devise du barème.

    Jamais effacé (aucune suppression dans les finances) : un frais qui ne s'applique plus
    (changement de classe, barème modifié ou supprimé) passe « retiré » et ne compte plus dans ce
    que doit l'élève ; il redevient dû si le barème s'applique de nouveau. Un frais réorganisé
    par un échéancier particulier passe « remplacé », pour de bon."""

    class Source(models.TextChoices):
        RULE = "rule", _("Fee rule")
        CUSTOM = "custom", _("Custom schedule")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Due")
        REMOVED = "removed", _("Removed")
        REPLACED = "replaced", _("Replaced")

    enrollment = models.ForeignKey(
        "students.Enrollment",
        on_delete=models.PROTECT,
        related_name="charges",
        verbose_name=_("enrollment"),
    )
    fee_type = models.ForeignKey(
        FeeType, on_delete=models.PROTECT, related_name="charges", verbose_name=_("fee type")
    )
    label = models.CharField(_("label"), max_length=40)
    amount_minor = models.BigIntegerField(_("amount"), validators=[MinValueValidator(1)])
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    due_on = models.DateField(_("due date"))
    source = models.CharField(_("source"), max_length=10, choices=Source.choices)
    # Tranche d'origine : garde le lien quand le barème est modifié ; vide si elle est retirée.
    installment_template = models.ForeignKey(
        InstallmentTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="charges",
        verbose_name=_("installment"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        ordering = ["due_on", "label"]
        verbose_name = _("student charge")
        verbose_name_plural = _("student charges")
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "installment_template"],
                condition=models.Q(installment_template__isnull=False),
                name="student_charge_one_per_installment",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0), name="student_charge_amount_positive"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "enrollment", "status"], name="charge_enrollment_status")
        ]

    def __str__(self) -> str:
        return f"{self.fee_type} — {self.label}"


class Discount(TenantModel):
    """Réduction accordée à un élève pour son année [T] (E3) : un pourcentage, ou un montant dans
    la devise du frais, sur un type de frais ou sur tous (`fee_type` vide, pourcentage seulement).
    Qui et quand : `created_by`, `created_at`. Son effet n'est pas stocké : il se répartit sur
    les frais dus actifs (`services.discount_shares`) et suit donc changement de classe, barème
    modifié et échéancier particulier. Jamais effacée : un retrait se note, avec son motif."""

    class Kind(models.TextChoices):
        PERCENT = "percent", _("Percentage")
        AMOUNT = "amount", _("Amount")

    class Reason(models.TextChoices):
        STAFF_CHILD = "staff_child", _("Staff child")
        SIBLING = "sibling", _("Sibling")
        SCHOLARSHIP = "scholarship", _("Scholarship")
        WAIVER = "waiver", _("Waiver from the head")
        OTHER = "other", _("Other")

    enrollment = models.ForeignKey(
        "students.Enrollment",
        on_delete=models.PROTECT,
        related_name="discounts",
        verbose_name=_("enrollment"),
    )
    fee_type = models.ForeignKey(
        FeeType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="discounts",
        verbose_name=_("fee type"),
    )
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    percent = models.PositiveSmallIntegerField(_("percentage"), null=True, blank=True)
    amount_minor = models.BigIntegerField(_("amount"), null=True, blank=True)
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices, blank=True)
    reason_code = models.CharField(_("reason"), max_length=12, choices=Reason.choices)
    reason = models.CharField(_("note"), max_length=200)
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    revoked_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("revoked by"),
    )
    revoke_reason = models.CharField(_("revocation reason"), max_length=200, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("discount")
        verbose_name_plural = _("discounts")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind="percent",
                        percent__gte=1,
                        percent__lte=100,
                        amount_minor__isnull=True,
                        currency="",
                    )
                    | models.Q(
                        kind="amount",
                        amount_minor__gt=0,
                        percent__isnull=True,
                        fee_type__isnull=False,
                    )
                    & ~models.Q(currency="")
                ),
                name="discount_percent_or_amount",
            ),
        ]
        indexes = [models.Index(fields=["school", "enrollment"], name="discount_enrollment")]

    def __str__(self) -> str:
        if self.kind == self.Kind.PERCENT:
            return f"{self.get_reason_code_display()} {self.percent} %"
        return f"{self.get_reason_code_display()} {self.amount_minor} {self.currency}"


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

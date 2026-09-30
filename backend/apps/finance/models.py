"""Configuration des frais (`docs/04-modele-de-donnees.md` § 4, E1, E2, E5) : types de frais,
barèmes d'une année et leurs tranches, taux de change de l'année ; caisses et paiements (F1-F2).

Montants en entiers dans la plus petite unité de la devise du barème (skill `argent`).
"""

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
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


# Caisses et paiements (F1-F2)


class CashRegister(TenantModel):
    """Caisse de l'école [T] (« Caisse 1 », code `C1`). Le code entre dans le numéro des reçus
    (`{ÉCOLE}-{CAISSE}-{AA}-{séquence}`) : fixé à la création. Désactivée, jamais effacée (ses
    sessions la protègent)."""

    name = models.CharField(_("name"), max_length=40)
    code = models.CharField(
        _("code"),
        max_length=4,
        validators=[RegexValidator(r"^[A-Z0-9]{1,4}$", _("Capital letters and digits only."))],
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = _("cash register")
        verbose_name_plural = _("cash registers")
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], name="cash_register_code_unique"),
            models.UniqueConstraint(fields=["school", "name"], name="cash_register_name_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class CashSession(TenantModel):
    """Ouverture d'une caisse par un caissier [T] : une seule session ouverte par caisse et par
    caissier, sauf ouverture hors ligne (`device`) : arrivée après coup, l'argent déjà reçu, elle
    n'est jamais refusée (3.8.2). Fermée par la clôture de caisse (`CashClosing`)."""

    cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        related_name="sessions",
        verbose_name=_("cash register"),
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cash_sessions",
        verbose_name=_("cashier"),
    )
    opened_at = models.DateTimeField(_("opened at"), default=timezone.now)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    # Ouverte hors ligne (3.5.2) : l'appareil ; `opened_at` est alors l'heure de l'appareil.
    device = models.ForeignKey(
        "sync.Device",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cash_sessions",
        verbose_name=_("device"),
    )

    class Meta:
        ordering = ["-opened_at"]
        verbose_name = _("cash session")
        verbose_name_plural = _("cash sessions")
        constraints = [
            models.UniqueConstraint(
                fields=["cash_register"],
                condition=models.Q(closed_at__isnull=True, device__isnull=True),
                name="cash_session_one_open_per_register",
            ),
            models.UniqueConstraint(
                fields=["school", "cashier"],
                condition=models.Q(closed_at__isnull=True, device__isnull=True),
                name="cash_session_one_open_per_cashier",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.cash_register} · {self.opened_at:%d/%m/%Y %H:%M}"


IMMUTABLE_PAYMENT = "Un paiement ne se modifie pas et ne s'efface pas : l'annuler."


class ImmutablePaymentError(Exception):
    """Erreur de programmation : modification ou suppression d'un paiement, de sa répartition
    ou de son annulation."""


class ImmutableQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        raise ImmutablePaymentError(IMMUTABLE_PAYMENT)

    def delete(self):
        raise ImmutablePaymentError(IMMUTABLE_PAYMENT)


class ImmutableManager(TenantManager.from_queryset(ImmutableQuerySet)):
    pass


class ImmutableModel(TenantModel):
    """Écriture [I] : ni modifiable ni effaçable, ici et par la base (déclencheur de la
    migration 0005)."""

    objects = ImmutableManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutablePaymentError(IMMUTABLE_PAYMENT)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutablePaymentError(IMMUTABLE_PAYMENT)


class Payment(ImmutableModel):
    """Paiement encaissé [T] [I] (F2) : montant reçu dans une devise, réparti sur les frais dus
    de l'élève (`PaymentAllocation`), avec le taux USD → CDF en vigueur à l'encaissement. Le reçu
    n'est pas un modèle : c'est la vue imprimable du paiement (décision Q2). Jamais modifié ni
    effacé : une annulation est une `PaymentCancellation`."""

    class Method(models.TextChoices):
        CASH = "cash", _("Cash")

    enrollment = models.ForeignKey(
        "students.Enrollment",
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("enrollment"),
    )
    cash_session = models.ForeignKey(
        CashSession, on_delete=models.PROTECT, related_name="payments", verbose_name=_("session")
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("cashier"),
    )
    received_amount_minor = models.BigIntegerField(_("amount received"))
    received_currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    # Taux USD → CDF (décision Q4) ; vide seulement pour une école à une seule devise sans taux.
    rate_used = models.DecimalField(
        _("rate used"), max_digits=14, decimal_places=6, null=True, blank=True
    )
    paid_at = models.DateTimeField(_("paid at"))
    receipt_number = models.CharField(_("receipt number"), max_length=40)
    method = models.CharField(
        _("method"), max_length=12, choices=Method.choices, default=Method.CASH
    )
    note = models.CharField(_("note"), max_length=200, blank=True)
    # Encaissé hors ligne (3.3.2) : l'appareil qui a donné le numéro du reçu et l'arrivée au
    # serveur ; `paid_at` est alors l'heure de l'appareil.
    device = models.ForeignKey(
        "sync.Device",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name=_("device"),
    )
    synced_at = models.DateTimeField(_("received by the server"), null=True, blank=True)

    class Meta:
        ordering = ["-paid_at"]
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "receipt_number"], name="payment_receipt_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(received_amount_minor__gt=0), name="payment_amount_positive"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "enrollment"], name="payment_enrollment"),
            models.Index(fields=["school", "cash_session", "-paid_at"], name="payment_session"),
        ]

    def __str__(self) -> str:
        return self.receipt_number


class PaymentAllocation(ImmutableModel):
    """Part d'un paiement affectée à un frais dû [T] [I] : `received_minor` dans la devise
    reçue, `amount_minor` dans la devise du frais (converti au taux du paiement, demi
    supérieur)."""

    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name="allocations", verbose_name=_("payment")
    )
    student_charge = models.ForeignKey(
        StudentCharge,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name=_("student charge"),
    )
    received_minor = models.BigIntegerField(_("part of the amount received"))
    amount_minor = models.BigIntegerField(_("amount"))

    class Meta:
        verbose_name = _("payment allocation")
        verbose_name_plural = _("payment allocations")
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "student_charge"], name="allocation_one_per_charge"
            ),
            models.CheckConstraint(
                condition=models.Q(received_minor__gt=0, amount_minor__gt=0),
                name="allocation_amounts_positive",
            ),
        ]


class CancellationRequest(TenantModel):
    """Demande d'annulation d'un paiement [T] (F7) : motif donné par le caissier (ou le
    comptable), en ligne ou hors ligne (`device`, `requested_at` : heure de l'appareil). Le
    paiement compte jusqu'à la décision d'un autre compte (`finance.approve_cancellation`) :
    validée, elle devient une `PaymentCancellation` ; refusée, le paiement reste valable et une
    nouvelle demande est possible. Une seule demande en attente par paiement."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="cancellation_requests",
        verbose_name=_("payment"),
    )
    reason = models.CharField(_("reason"), max_length=200)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("requested by"),
    )
    requested_at = models.DateTimeField(_("requested at"), default=timezone.now)
    device = models.ForeignKey(
        "sync.Device",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("device"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("decided by"),
    )
    decided_at = models.DateTimeField(_("decided at"), null=True, blank=True)
    decision_note = models.CharField(_("comment"), max_length=200, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        verbose_name = _("cancellation request")
        verbose_name_plural = _("cancellation requests")
        constraints = [
            models.UniqueConstraint(
                fields=["payment"],
                condition=models.Q(status="pending"),
                name="cancellation_request_one_pending",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "status", "-requested_at"], name="cancellation_status"),
        ]

    def __str__(self) -> str:
        return f"{self.payment} · {self.get_status_display()}"


class PaymentCancellation(ImmutableModel):
    """Annulation validée d'un paiement [T] [I] (F7) : ses allocations ne comptent plus dans ce
    que doit l'élève. Son reçu d'annulation a un numéro d'une série propre à l'école
    (`ITIG-AN-26-000007`) ; la demande est la `CancellationRequest` validée du paiement."""

    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name="cancellation",
        verbose_name=_("payment"),
    )
    receipt_number = models.CharField(_("receipt number"), max_length=40)
    reason = models.CharField(_("reason"), max_length=200)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("requested by"),
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("approved by"),
    )
    approved_at = models.DateTimeField(_("approved at"), default=timezone.now)

    class Meta:
        verbose_name = _("payment cancellation")
        verbose_name_plural = _("payment cancellations")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "receipt_number"], name="cancellation_receipt_number_unique"
            ),
        ]


class StudentCredit(TenantModel):
    """Argent reçu en trop pour un élève [T] (M14), dans la devise de cet argent : le surplus
    d'un paiement hors ligne arrivé quand l'élève devait moins (`source_payment`), ou le
    trop-payé qu'une réduction fait apparaître sur des échéances déjà payées (`source_discount`).
    Jamais perdu : le comptable l'utilise sur les prochaines échéances (`CreditAllocation`),
    sans nouveau paiement ; il est annulé (`voided_at`, jamais effacé) si sa réduction est
    retirée, et ses affectations ne comptent plus."""

    class Origin(models.TextChoices):
        OFFLINE_SURPLUS = "offline_surplus", _("Paid twice offline")
        DISCOUNT = "discount", _("Discount granted")

    enrollment = models.ForeignKey(
        "students.Enrollment",
        on_delete=models.PROTECT,
        related_name="credits",
        verbose_name=_("enrollment"),
    )
    origin = models.CharField(_("origin"), max_length=20, choices=Origin.choices)
    amount_minor = models.BigIntegerField(_("amount"))
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    source_payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credits",
        verbose_name=_("payment"),
    )
    source_discount = models.ForeignKey(
        Discount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credits",
        verbose_name=_("discount"),
    )
    voided_at = models.DateTimeField(_("voided at"), null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("voided by"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("student credit")
        verbose_name_plural = _("student credits")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0), name="credit_amount_positive"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "enrollment"], name="credit_enrollment"),
            models.Index(fields=["school", "-created_at"], name="credit_created"),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.amount_minor} {self.currency}"


class CreditAllocation(ImmutableModel):
    """Part d'un crédit utilisée sur un frais dû de la même devise [T] [I] : comptée comme payée
    tant que le crédit n'est pas annulé. Pas de paiement ni de reçu : les totaux de caisse ne
    bougent pas."""

    credit = models.ForeignKey(
        StudentCredit,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name=_("credit"),
    )
    student_charge = models.ForeignKey(
        StudentCharge,
        on_delete=models.PROTECT,
        related_name="credit_allocations",
        verbose_name=_("student charge"),
    )
    amount_minor = models.BigIntegerField(_("amount"))

    class Meta:
        verbose_name = _("credit allocation")
        verbose_name_plural = _("credit allocations")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0), name="credit_allocation_positive"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "student_charge"], name="credit_allocation_charge"),
        ]


# Clôture de caisse (F8)


class CashClosing(ImmutableModel):
    """Clôture d'une session de caisse [T] [I], une ligne par devise (jamais additionnées) :
    l'attendu (paiements de la session pas annulés à l'heure de clôture), le compté par le
    caissier, l'écart (compté - attendu) et son explication. Faite hors ligne : `device` et
    `closed_at` de l'appareil ; `created_at` est l'arrivée au serveur. Un paiement hors ligne
    arrivé après la clôture n'entre pas dans l'attendu déjà figé."""

    cash_session = models.ForeignKey(
        CashSession, on_delete=models.PROTECT, related_name="closings", verbose_name=_("session")
    )
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    expected_minor = models.BigIntegerField(_("expected"))
    counted_minor = models.BigIntegerField(_("counted"))
    difference_minor = models.BigIntegerField(_("difference"))
    note = models.CharField(_("explanation"), max_length=500, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("closed by"),
    )
    closed_at = models.DateTimeField(_("closed at"), default=timezone.now)
    device = models.ForeignKey(
        "sync.Device",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("device"),
    )

    class Meta:
        verbose_name = _("cash closing")
        verbose_name_plural = _("cash closings")
        constraints = [
            models.UniqueConstraint(
                fields=["cash_session", "currency"], name="cash_closing_one_per_currency"
            ),
            models.CheckConstraint(
                condition=models.Q(counted_minor__gte=0, expected_minor__gte=0),
                name="cash_closing_amounts_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    difference_minor=models.F("counted_minor") - models.F("expected_minor")
                ),
                name="cash_closing_difference",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.cash_session} · {self.currency}"

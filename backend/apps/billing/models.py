"""Offres, contrats et conditions générales (CTR.1, ABO.1). Montants en entiers (règle 2).

`Plan` et `LegalDocument` sont à la plateforme ; `Contract` et `LegalAcceptance` sont rattachés à
une école (isolation et sécurité au niveau des lignes comme toute donnée d'école). Rien ne se
modifie une fois publié, activé ou accepté : une nouvelle version, un avenant, une autre ligne."""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.modules import MODULE_CHOICES
from apps.core.models import BaseModel, TenantModel
from apps.core.money import Currency


class Plan(BaseModel):
    """Offre de la plateforme [G] (« Essentiel », « Complet »…) : les modules qu'elle donne et son
    prix par élève inscrit et par période. Un plan retiré de la vente (`active=False`) reste lu
    par les contrats qui l'ont signé."""

    class Period(models.TextChoices):
        TERM = "term", _("Per term")
        YEAR = "year", _("Per school year")

    code = models.SlugField(_("code"), max_length=40, unique=True)
    name = models.CharField(_("name"), max_length=80)
    description = models.CharField(_("description"), max_length=240, blank=True)
    modules = ArrayField(
        models.CharField(max_length=20, choices=MODULE_CHOICES), default=list, blank=True
    )
    price_per_student = models.PositiveIntegerField(
        _("price per enrolled student"), help_text=_("Smallest unit of the currency.")
    )
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    period = models.CharField(_("billing period"), max_length=4, choices=Period.choices)
    # Usages et crédits de l'IA compris dans l'offre (§ 6.5) ; la console les copie dans
    # `AiAllowance` au démarrage du contrat.
    ai_uses = ArrayField(models.CharField(max_length=40), default=list, blank=True)
    ai_monthly_credits = models.PositiveIntegerField(_("AI credits per month"), default=0)
    active = models.BooleanField(_("on sale"), default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Counter(models.Model):
    """Numéro suivant d'une suite (contrats par année) : la ligne est verrouillée le temps de
    prendre le numéro, jamais de trou ni de doublon."""

    key = models.CharField(max_length=40, primary_key=True)
    value = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.key}: {self.value}"


class Contract(TenantModel):
    """Contrat d'une école avec la plateforme. Brouillon modifiable ; une fois `ACTIVE`, plus rien
    ne change : un avenant est un nouveau contrat (`replaces`) qui termine le précédent. Offre,
    prix et modules sont copiés à la signature : changer le plan ne réécrit pas les contrats."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        ACTIVE = "active", _("Active")
        ENDED = "ended", _("Ended")

    class Signature(models.TextChoices):
        UPLOAD = "upload", _("Signed copy uploaded")
        ONLINE = "online", _("Accepted online")

    number = models.CharField(_("number"), max_length=20, unique=True)
    status = models.CharField(
        _("status"), max_length=6, choices=Status.choices, default=Status.DRAFT
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="+")
    replaces = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="amendment"
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))
    # Copie du plan à la signature.
    modules = ArrayField(models.CharField(max_length=20), default=list, blank=True)
    price_per_student = models.PositiveIntegerField(_("price per enrolled student"))
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    period = models.CharField(_("billing period"), max_length=4, choices=Plan.Period.choices)
    trial_days = models.PositiveSmallIntegerField(_("trial days"), default=0)
    auto_renew = models.BooleanField(_("renews automatically"), default=True)
    # Signature.
    signature = models.CharField(
        _("signature"), max_length=6, choices=Signature.choices, blank=True
    )
    signed_at = models.DateTimeField(_("signed at"), null=True, blank=True)
    signer_name = models.CharField(_("signer"), max_length=120, blank=True)
    signed_file = models.FileField(_("signed copy"), upload_to="contracts/", blank=True)

    class Meta:
        ordering = ["-start_date", "-number"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")), name="contract_dates"
            ),
            # Un seul contrat actif par école.
            models.UniqueConstraint(
                fields=["school"],
                condition=models.Q(status="active"),
                name="contract_one_active_per_school",
            ),
        ]

    def __str__(self) -> str:
        return self.number


class LegalDocument(BaseModel):
    """Version publiée des conditions d'utilisation et de vente, de la politique de
    confidentialité ou du registre des traitements [G]. Une version publiée ne change plus."""

    class Kind(models.TextChoices):
        TERMS = "terms", _("Terms of use and sale")
        PRIVACY = "privacy", _("Privacy policy")
        REGISTER = "register", _("Register of processing")

    kind = models.CharField(_("kind"), max_length=8, choices=Kind.choices)
    version = models.PositiveSmallIntegerField(_("version"))
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    title_fr = models.CharField(max_length=160)
    title_en = models.CharField(max_length=160)
    # Markdown limité (`core/markdown.py`).
    body_fr = models.TextField()
    body_en = models.TextField()

    class Meta:
        ordering = ["kind", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "version"], name="legal_version_unique")
        ]

    def __str__(self) -> str:
        return f"{self.kind} v{self.version}"


class LegalAcceptance(TenantModel):
    """Acceptation d'une version par l'administrateur d'une école : version, date, compte,
    adresse. Jamais modifiée ni effacée."""

    document = models.ForeignKey(LegalDocument, on_delete=models.PROTECT, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-accepted_at"]
        constraints = [
            models.UniqueConstraint(fields=["school", "document"], name="legal_accepted_once")
        ]


class Invoice(TenantModel):
    """Facture de la plateforme à une école (ABO.2), ou avoir qui l'annule en entier. Jamais
    modifiée ni supprimée : une erreur se corrige par un avoir (`credit_for`) puis une nouvelle
    facture. Montants en entiers de la plus petite unité de la devise (règle 2)."""

    class Kind(models.TextChoices):
        INVOICE = "invoice", _("Invoice")
        CREDIT_NOTE = "credit_note", _("Credit note")

    number = models.CharField(_("number"), max_length=20, unique=True)
    kind = models.CharField(_("kind"), max_length=11, choices=Kind.choices, default=Kind.INVOICE)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="invoices")
    credit_for = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="credit_note"
    )
    issued_on = models.DateField(_("issued on"))
    due_on = models.DateField(_("due on"))
    period_start = models.DateField(_("period start"), null=True, blank=True)
    period_end = models.DateField(_("period end"), null=True, blank=True)
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    total = models.PositiveIntegerField(_("total"))

    class Meta:
        ordering = ["-issued_on", "-number"]

    def __str__(self) -> str:
        return self.number


class InvoiceLine(TenantModel):
    """Ligne d'une facture : élèves inscrits x prix, ou ligne libre (recharge de crédits IA,
    module en plus)."""

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="lines")
    description = models.CharField(_("description"), max_length=200)
    quantity = models.PositiveIntegerField(_("quantity"), default=1)
    unit_amount = models.PositiveIntegerField(_("unit price"))
    amount = models.PositiveIntegerField(_("amount"))

    class Meta:
        ordering = ["created_at"]


class InvoicePayment(TenantModel):
    """Paiement d'une facture par l'école, saisi par la console (espèces, banque, Mobile Money).
    Jamais modifié ni supprimé (règle 3) : une erreur est une écriture d'annulation liée
    (`reverses`), avec motif. La devise est celle de la facture : pas de conversion, donc pas de
    taux à garder."""

    class Method(models.TextChoices):
        CASH = "cash", _("Cash")
        BANK = "bank", _("Bank transfer")
        MOBILE = "mobile_money", _("Mobile Money")

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.PositiveIntegerField(_("amount"))
    method = models.CharField(_("method"), max_length=12, choices=Method.choices)
    reference = models.CharField(_("reference"), max_length=80, blank=True)
    paid_on = models.DateField(_("paid on"))
    reverses = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal"
    )
    reason = models.CharField(_("reason"), max_length=200, blank=True)

    class Meta:
        ordering = ["paid_on", "created_at"]

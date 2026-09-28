from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel


class Device(TenantModel):
    """Appareil enregistré par un compte dans une école [T] (« Se souvenir de cet appareil »).

    `prefix` entre dans le numéro des reçus émis hors ligne (`ITIG-P1-26-000184`) : donné par le
    serveur, jamais redonné. `public_key` (ECDSA P-256, SPKI en base64) vérifie la signature de
    ces reçus ; la clé privée ne quitte pas le navigateur. Jamais effacé : révoqué, sa session
    est fermée."""

    class Kind(models.TextChoices):
        BROWSER = "browser", _("browser")
        READER = "reader", _("card reader")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("account"),
        on_delete=models.PROTECT,
        related_name="devices",
    )
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices, default=Kind.BROWSER)
    label = models.CharField(_("name"), max_length=80)
    prefix = models.CharField(_("prefix"), max_length=6)
    cash_register = models.ForeignKey(
        "finance.CashRegister",
        verbose_name=_("cash register"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="devices",
    )
    public_key = models.TextField(_("public key"))
    # Session ouverte sur l'appareil, fermée à sa révocation.
    session_key = models.CharField(max_length=40, blank=True)
    last_seen_at = models.DateTimeField(_("last seen"), null=True, blank=True)
    last_receipt_seq = models.PositiveIntegerField(_("last receipt number"), default=0)
    revoked_at = models.DateTimeField(_("disconnected at"), null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]
        verbose_name = _("device")
        verbose_name_plural = _("devices")
        constraints = [
            models.UniqueConstraint(fields=["school", "prefix"], name="device_prefix_unique"),
        ]
        indexes = [models.Index(fields=["school", "user"], name="device_school_user")]

    def __str__(self) -> str:
        return f"{self.prefix} · {self.label}"

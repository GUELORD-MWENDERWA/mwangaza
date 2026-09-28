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


class SyncOperation(TenantModel):
    """Opération envoyée par un appareil (`POST /api/sync/push`) [T], gardée avec son résultat :
    le même `op_id` reçu deux fois n'est appliqué qu'une fois et rend le même résultat. Refusée,
    elle reste refusée (l'appareil la montre ; un nouvel essai est une nouvelle opération).
    `created_at` : arrivée au serveur."""

    class Status(models.TextChoices):
        APPLIED = "applied", _("applied")
        REJECTED = "rejected", _("rejected")

    op_id = models.UUIDField(_("operation"))
    device = models.ForeignKey(
        Device, verbose_name=_("device"), on_delete=models.PROTECT, related_name="operations"
    )
    type = models.CharField(_("type"), max_length=40)
    payload = models.JSONField(_("content"), default=dict)
    status = models.CharField(_("status"), max_length=10, choices=Status.choices)
    # Appliquée : ce que l'appareil doit savoir (ex. `{"payment": id}`) ; refusée : l'erreur
    # `{code, detail, fields}` de l'API.
    result = models.JSONField(_("result"), default=dict)

    class Meta:
        verbose_name = _("sync operation")
        verbose_name_plural = _("sync operations")
        constraints = [
            models.UniqueConstraint(fields=["school", "op_id"], name="sync_operation_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.type} · {self.op_id}"


class ChangeLog(TenantModel):
    """Dernière modification de chaque entité descendue sur les appareils [T] (`GET
    /api/sync/pull`) : une ligne par entité. Un changement la marque `pending` ; son nouveau
    numéro (`seq`) est donné à la lecture, sous le verrou de l'école (`changes.sequence`) : un
    changement validé après une lecture a toujours un numéro plus grand que ce que l'appareil a
    déjà reçu. Un numéro n'est jamais repris. `updated_at` : heure du changement."""

    class Entity(models.TextChoices):
        ENROLLMENT = "enrollment", _("enrollment")
        CONFIG = "config", _("configuration")

    class Operation(models.TextChoices):
        UPSERT = "upsert", _("created or changed")
        DELETE = "delete", _("deleted")

    # Vide jusqu'au premier numéro ; ensuite, celui de l'avant-dernier changement tant que le
    # dernier attend le sien (le plus grand numéro de l'école ne recule jamais).
    seq = models.BigIntegerField(_("number"), null=True, blank=True)
    pending = models.BooleanField(_("waiting for a number"), default=True)
    entity_type = models.CharField(_("entity"), max_length=20, choices=Entity.choices)
    entity_id = models.UUIDField(_("entity id"))
    operation = models.CharField(_("operation"), max_length=10, choices=Operation.choices)

    class Meta:
        verbose_name = _("change")
        verbose_name_plural = _("changes")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "entity_type", "entity_id"], name="change_log_one_per_entity"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "seq"], name="change_log_school_seq"),
            models.Index(
                fields=["school", "updated_at"],
                condition=models.Q(pending=True),
                name="change_log_pending",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.seq} · {self.entity_type} {self.entity_id}"

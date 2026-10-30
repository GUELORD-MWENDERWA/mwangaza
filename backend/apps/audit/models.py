"""Journal d'audit (`docs/04-modele-de-donnees.md` § 1, I1, maquette M6)."""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit.actions import Action, PlatformAction
from apps.core.models import BaseModel, TenantModel
from apps.core.tenancy import TenantManager, TenantQuerySet

IMMUTABLE_MESSAGE = "Le journal d'audit ne se modifie pas et ne s'efface pas."


class ImmutableError(Exception):
    """Erreur de programmation : modification ou suppression d'une entrée du journal."""


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ImmutableError(IMMUTABLE_MESSAGE)

    def delete(self):
        raise ImmutableError(IMMUTABLE_MESSAGE)


class AuditLogQuerySet(ImmutableQuerySet, TenantQuerySet):
    pass


class AuditLogManager(TenantManager.from_queryset(AuditLogQuerySet)):
    pass


class AuditLog(TenantModel):
    """Une action d'une personne dans une école [T] [I] : qui, quoi, sur quoi, avant / après,
    d'où. Écrite par `apps.audit.services.record()`, dans la transaction de l'action.

    Ni modifiable ni effaçable : refusé ici (`ImmutableError`) et par la base (déclencheur
    PostgreSQL de la migration 0001, même en SQL direct). Jamais de mot de passe, de code ni de
    clé dans `before` / `after`."""

    action = models.CharField(_("action"), max_length=64)
    # Vide pour une action du système. Un compte n'est jamais supprimé : PROTECT.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("by"),
    )
    # Super-admin connecté « en tant qu'école » pour le support (A3, rempli en 1.5).
    impersonated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("impersonated by"),
    )
    # Sur quoi : `accounts.role`, `accounts.membership`… et le nom de l'objet au moment de
    # l'action (un renommage ne réécrit pas l'histoire).
    entity_type = models.CharField(_("object type"), max_length=64, blank=True)
    entity_id = models.UUIDField(_("object"), null=True, blank=True)
    entity_label = models.CharField(_("object name"), max_length=255, blank=True)
    # Seulement les champs changés.
    before = models.JSONField(_("before"), null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(_("after"), null=True, blank=True, encoder=DjangoJSONEncoder)
    ip = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.CharField(_("browser"), max_length=255, blank=True)
    # Appareil enregistré de la session (3.3.1) ; heure de l'appareil pour une action faite hors
    # ligne, reçue plus tard par la synchronisation (`created_at` : heure de réception).
    device = models.ForeignKey(
        "sync.Device",
        verbose_name=_("device"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    device_time = models.DateTimeField(_("device time"), null=True, blank=True)

    objects = AuditLogManager()
    all_schools = models.Manager.from_queryset(AuditLogQuerySet)()

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = _("audit log entry")
        verbose_name_plural = _("audit log")
        indexes = [
            models.Index(fields=["school", "-created_at"], name="auditlog_school_created"),
            models.Index(fields=["school", "actor", "-created_at"], name="auditlog_school_actor"),
            models.Index(fields=["school", "entity_id"], name="auditlog_school_entity"),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} | {self.entity_label}"

    def get_action_display(self) -> str:
        try:
            return str(Action(self.action).label)
        except ValueError:
            return self.action

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableError(IMMUTABLE_MESSAGE)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError(IMMUTABLE_MESSAGE)


class PlatformAuditLog(BaseModel):
    """Une action du super-admin sur la plateforme [G] [I] (identité, 5.2.2 ; écoles et comptes,
    5.3-5.4) : qui, quoi, avant / après, d'où. Sans école : le journal d'une école n'en montre
    rien. Écrite par `apps.audit.services.record_platform()`, dans la transaction de l'action ;
    ni modifiable ni effaçable, jusque dans la base (déclencheur de la migration 0004)."""

    action = models.CharField(_("action"), max_length=64)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("by"),
    )
    entity_type = models.CharField(_("object type"), max_length=64, blank=True)
    # Texte : la ligne de la plateforme a la clé 1, les écoles et les comptes un UUID.
    entity_id = models.CharField(_("object"), max_length=64, blank=True)
    entity_label = models.CharField(_("object name"), max_length=255, blank=True)
    before = models.JSONField(_("before"), null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(_("after"), null=True, blank=True, encoder=DjangoJSONEncoder)
    ip = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.CharField(_("browser"), max_length=255, blank=True)

    objects = models.Manager.from_queryset(ImmutableQuerySet)()

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = _("platform log entry")
        verbose_name_plural = _("platform log")
        indexes = [
            models.Index(fields=["-created_at"], name="platformlog_created"),
            models.Index(fields=["entity_type", "entity_id"], name="platformlog_entity"),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} | {self.entity_label}"

    def get_action_display(self) -> str:
        try:
            return str(PlatformAction(self.action).label)
        except ValueError:
            return self.action

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableError(IMMUTABLE_MESSAGE)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError(IMMUTABLE_MESSAGE)

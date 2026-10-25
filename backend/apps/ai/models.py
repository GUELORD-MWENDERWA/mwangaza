"""Modèles du socle IA (IA.1.1). Aucun texte de demande ni de réponse dans `AiCall` ; la réponse
attend la personne dans `AiResult`, supprimée dès qu'elle est gardée ou abandonnée (ou à 24 h).
Montants en micro-dollars (entiers) ; 1 crédit = 1 000 micro-dollars."""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, TenantModel


class AiSettings(models.Model):
    """Réglages de la plateforme [G] : une seule ligne (clé 1), changés par le super-admin."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(_("AI switched on"), default=True)
    monthly_cap_micro = models.BigIntegerField(_("monthly cap of the platform"), default=50_000_000)
    hourly_limit = models.PositiveSmallIntegerField(_("calls per person and hour"), default=20)
    # Prix et usages que la console a changés, au-dessus de `prices.DEFAULT_PRICES` et du
    # catalogue : {modèle: {input, output, cache_read, cache_write}}, {usage: {model, …}}.
    prices = models.JSONField(_("prices"), default=dict, blank=True)
    use_overrides = models.JSONField(_("use settings"), default=dict, blank=True)

    class Meta:
        verbose_name = _("AI settings")
        verbose_name_plural = _("AI settings")

    def __str__(self) -> str:
        return str(_("AI settings"))


class AiPlatformMonth(BaseModel):
    """Dépense de la plateforme pour un mois [G] : le plafond se lit sur une ligne."""

    month = models.DateField(_("month"), unique=True)
    spent_micro = models.BigIntegerField(_("spent"), default=0)
    alerted_80 = models.BooleanField(default=False)
    alerted_100 = models.BooleanField(default=False)


class AiAllowance(TenantModel):
    """Ce que la plateforme donne à une école [T] : usages affectés, crédits par mois, pause.
    Réglé par la console (IA.1.2) ; jusque-là, par l'administration de dépannage."""

    uses = ArrayField(models.CharField(max_length=40), default=list, blank=True)
    monthly_credits = models.PositiveIntegerField(_("credits per month"), default=0)
    paused = models.BooleanField(_("paused"), default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school"], name="ai_allowance_one_per_school")
        ]


class AiBalance(TenantModel):
    """Crédits d'une école pour un mois [T] : accordés (mensuels + recharges) et dépensés. Le
    contrôle des crédits lit cette ligne, jamais une somme."""

    month = models.DateField(_("month"))
    granted_micro = models.BigIntegerField(_("granted"), default=0)
    spent_micro = models.BigIntegerField(_("spent"), default=0)
    alerted_80 = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "month"], name="ai_balance_month")]

    @property
    def remaining_micro(self) -> int:
        return self.granted_micro - self.spent_micro


class AiUsageMonth(TenantModel):
    """Cumul par école, mois et usage [T], gardé pour la facturation et pour la part des résultats
    gardés (un usage qui coûte sans servir se voit et se coupe)."""

    month = models.DateField(_("month"))
    use = models.CharField(_("use"), max_length=40)
    calls = models.PositiveIntegerField(default=0)
    kept = models.PositiveIntegerField(default=0)
    abandoned = models.PositiveIntegerField(default=0)
    input_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField(default=0)
    cache_tokens = models.BigIntegerField(default=0)
    cost_micro = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "month", "use"], name="ai_usage_month")
        ]


class AiCall(TenantModel):
    """Un appel à l'IA [T] : qui, quel usage, quel modèle, combien de jetons et de micro-dollars,
    et ce que la personne en a fait. **Jamais le texte** de la demande ni de la réponse. Purgé à
    90 jours ; ni supprimé ni modifié ailleurs que par `ai.services`."""

    class State(models.TextChoices):
        QUEUED = "queued", _("Waiting")
        RUNNING = "running", _("Running")
        DONE = "done", _("Done")
        REFUSED = "refused", _("Refused")
        ERROR = "error", _("Failed")
        KEPT = "kept", _("Kept")
        ABANDONED = "abandoned", _("Abandoned")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name=_("by")
    )
    use = models.CharField(_("use"), max_length=40)
    model = models.CharField(_("model"), max_length=60, blank=True)
    request_id = models.UUIDField(_("request"))
    state = models.CharField(max_length=10, choices=State.choices, default=State.QUEUED)
    refusal = models.CharField(_("reason"), max_length=40, blank=True)
    # Session support : compté sur la plateforme, pas sur les crédits de l'école.
    on_platform = models.BooleanField(default=False)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cache_read_tokens = models.PositiveIntegerField(default=0)
    cache_write_tokens = models.PositiveIntegerField(default=0)
    cost_micro = models.BigIntegerField(default=0)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "request_id"], name="ai_call_once")
        ]
        indexes = [
            models.Index(fields=["school", "user", "created_at"], name="aicall_user_hour"),
            models.Index(fields=["created_at"], name="aicall_created"),
        ]
        ordering = ["-created_at", "-id"]


class AiResult(TenantModel):
    """Réponse en attente de la personne [T] : écrite par le travailleur, lue par l'écran, effacée
    quand elle est gardée ou abandonnée, ou après 24 h. Pas de cache partagé dans le projet."""

    call = models.OneToOneField(AiCall, on_delete=models.CASCADE, related_name="+")
    payload = models.JSONField(default=dict)

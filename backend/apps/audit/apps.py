from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuditConfig(AppConfig):
    """Journal d'audit de chaque école : qui a fait quoi, quand, d'où ; ni modifiable ni
    effaçable."""

    name = "apps.audit"
    label = "audit"
    verbose_name = _("Audit")

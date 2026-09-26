from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    """Socle commun : école courante, modèles de base, UUID v7, montants."""

    name = "apps.core"
    label = "core"
    verbose_name = _("Core")

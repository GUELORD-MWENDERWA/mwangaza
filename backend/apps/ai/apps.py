from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AiConfig(AppConfig):
    """Intelligence artificielle (bloc IA, `05` § 6.5) : usages déclarés, crédits, plafond de la
    plateforme, un seul fichier qui parle à l'API."""

    name = "apps.ai"
    label = "ai"
    verbose_name = _("AI assistance")

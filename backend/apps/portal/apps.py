from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PortalConfig(AppConfig):
    """API du portail des familles (H1 à H6) : une seule adresse pour toutes les écoles."""

    name = "apps.portal"
    label = "portal"
    verbose_name = _("Parent portal")

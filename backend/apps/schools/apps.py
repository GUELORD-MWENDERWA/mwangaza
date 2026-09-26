from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SchoolsConfig(AppConfig):
    """Écoles et organisation scolaire (années, périodes, niveaux, options, classes)."""

    name = "apps.schools"
    label = "schools"
    verbose_name = _("Schools")

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SyncConfig(AppConfig):
    """Appareils enregistrés et, en 3.3.2, synchronisation hors ligne (push, pull, instantané)."""

    name = "apps.sync"
    label = "sync"
    verbose_name = _("Devices and synchronisation")

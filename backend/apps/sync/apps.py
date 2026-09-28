from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SyncConfig(AppConfig):
    """Appareils enregistrés et synchronisation hors ligne (push, pull, instantané)."""

    name = "apps.sync"
    label = "sync"
    verbose_name = _("Devices and synchronisation")

    def ready(self) -> None:
        from apps.sync import signals

        signals.connect()

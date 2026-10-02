from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NotificationsConfig(AppConfig):
    """Annonces de l'école aux familles (H4) ; plus tard les notifications sur les téléphones."""

    name = "apps.notifications"
    label = "notifications"
    verbose_name = _("Announcements")

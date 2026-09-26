from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    """Comptes (un par numéro de téléphone), rôles de chaque école, appartenances, permissions."""

    name = "apps.accounts"
    label = "accounts"
    verbose_name = _("Accounts")

    def ready(self) -> None:
        from apps.accounts import signals  # noqa: F401

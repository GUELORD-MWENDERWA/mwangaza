from django.apps import AppConfig
from django.contrib.admin import apps as admin_apps
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    """Comptes (un par numéro de téléphone), rôles de chaque école, appartenances, permissions."""

    name = "apps.accounts"
    label = "accounts"
    verbose_name = _("Accounts")

    def ready(self) -> None:
        from apps.accounts import signals  # noqa: F401


class PlatformAdminConfig(admin_apps.AdminConfig):
    """Administration Django du super-admin, avec la double authentification (`admin_site.py`).
    Dans `INSTALLED_APPS` à la place de `django.contrib.admin`."""

    # Pas la configuration par défaut de l'app `accounts` (c'est `AccountsConfig`).
    default = False
    default_site = "apps.accounts.admin_site.PlatformAdminSite"

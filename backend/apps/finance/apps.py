from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FinanceConfig(AppConfig):
    """Frais, barèmes, taux de l'année (E1-E5) ; plus tard dus, paiements et caisses (F)."""

    name = "apps.finance"
    label = "finance"
    verbose_name = _("Finance")

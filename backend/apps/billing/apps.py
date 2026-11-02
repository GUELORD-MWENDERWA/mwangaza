from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BillingConfig(AppConfig):
    """Ce que l'école doit à la plateforme (bloc ABO, `05` § 6.2) : offres, contrats, conditions
    générales, puis factures. Donnée de la plateforme : la console l'écrit, l'école la lit."""

    name = "apps.billing"
    label = "billing"
    verbose_name = _("Subscriptions")

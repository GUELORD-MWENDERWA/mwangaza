from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InventoryConfig(AppConfig):
    """Bibliothèque et ateliers (lot 11) : un moteur commun (articles, exemplaires étiquetés,
    mouvements de stock, inventaires) sous deux modules, `library` et `workshops`."""

    name = "apps.inventory"
    label = "inventory"
    verbose_name = _("Library and workshops")

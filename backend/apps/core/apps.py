from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    """Socle commun : école courante, modèles de base, UUID v7, montants."""

    name = "apps.core"
    label = "core"
    verbose_name = _("Core")

    def ready(self):
        from apps.core import row_security, tenancy

        # Row Level Security (S.6) : portée de chaque nouvelle connexion, règles après `migrate`.
        connection_created.connect(tenancy.apply_scope_on_connect)
        post_migrate.connect(row_security.install_after_migrate, sender=self)

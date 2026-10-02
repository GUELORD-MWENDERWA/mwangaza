"""Identité de la plateforme pour `make demo` (5.1) : valeurs de départ, contact du support et
mentions légales fictifs. Les vraies valeurs se saisissent dans les paramètres de la plateforme."""

from apps.core.models import PlatformSettings

DEMO_SUPPORT_PHONE = "+243000000999"


def create_demo_platform() -> PlatformSettings:
    """Remet l'identité de départ (nom, couleurs, sans logo ni icône) avec un support fictif."""
    initial = {
        field.name: field.default
        for field in PlatformSettings._meta.concrete_fields
        if field.has_default() and field.name != "id"
    }
    platform, _ = PlatformSettings.objects.update_or_create(
        pk=1,
        defaults={
            **initial,
            "logo": "",
            "icon": "",
            "support_phone": DEMO_SUPPORT_PHONE,
            "support_email": "support@example.com",
            "legal_notice": (
                "Plateforme de démonstration : toutes les données sont fictives.\n"
                "Éditeur, hébergeur et contact : à compléter dans les paramètres de la plateforme."
            ),
        },
    )
    return platform

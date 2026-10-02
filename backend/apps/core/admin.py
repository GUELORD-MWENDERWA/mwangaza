from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.models import PlatformSettings


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    """Identité de la plateforme : une seule fiche, en lecture seule (dépannage) ; elle se modifie
    dans la console (écran « Identité », 5.2.2), qui note chaque changement au journal."""

    fieldsets = [
        (
            None,
            {
                "fields": ["name", "short_name", "logo", "icon"],
                "description": _("To change it: Identity screen of the platform console."),
            },
        ),
        (None, {"fields": ["primary_color", "accent_color"]}),
        (None, {"fields": ["support_phone", "support_email", "legal_notice"]}),
    ]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def changelist_view(self, request, extra_context=None):
        platform = PlatformSettings.load()
        return redirect(reverse("admin:core_platformsettings_change", args=[platform.pk]))

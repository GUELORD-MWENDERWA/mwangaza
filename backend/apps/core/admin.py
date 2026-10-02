from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from apps.core.models import PlatformSettings


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    """Identité de la plateforme : une seule fiche, ni ajout ni suppression. L'écran de la
    console (5.2) la remplacera."""

    fieldsets = [
        (None, {"fields": ["name", "short_name", "logo", "icon"]}),
        (None, {"fields": ["primary_color", "accent_color"]}),
        (None, {"fields": ["support_phone", "support_email", "legal_notice"]}),
    ]

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def changelist_view(self, request, extra_context=None):
        platform = PlatformSettings.load()
        return redirect(reverse("admin:core_platformsettings_change", args=[platform.pk]))

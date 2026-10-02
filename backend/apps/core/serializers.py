from rest_framework import serializers

from apps.core.models import PlatformSettings


class PlatformSerializer(serializers.ModelSerializer):
    """Identité de la plateforme, publique : écrans de connexion, menus, documents."""

    logo = serializers.CharField(
        source="logo_url", allow_null=True, help_text="Adresse du logo ; vide : la lampe."
    )
    icon = serializers.CharField(
        source="icon_url",
        allow_null=True,
        help_text="Adresse de l'icône des applications ; vide : celle de l'application.",
    )

    class Meta:
        model = PlatformSettings
        fields = [
            "name",
            "short_name",
            "logo",
            "icon",
            "primary_color",
            "accent_color",
            "support_phone",
            "support_email",
            "legal_notice",
        ]

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PhoneField
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.audit.serializers import AuditActorSerializer
from apps.core.images import CleanedFileField
from apps.core.models import DemoRequest, PlatformSettings
from apps.core.platform import clean_icon, clean_logo

PUBLIC_FIELDS = [
    "name",
    "short_name",
    "site_name",
    "logo",
    "icon",
    "primary_color",
    "accent_color",
    "support_phone",
    "support_email",
    "legal_notice",
    "address",
    "city",
    "region",
    "whatsapp_url",
    "facebook_url",
    "instagram_url",
    "linkedin_url",
    "youtube_url",
    "tiktok_url",
]


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
        fields = PUBLIC_FIELDS


class PlatformChangeSerializer(serializers.ModelSerializer):
    """Une modification de l'identité, dans le journal de la plateforme."""

    action = serializers.ChoiceField(choices=PlatformAction.choices, read_only=True)
    actor = AuditActorSerializer(read_only=True, allow_null=True)

    class Meta:
        model = PlatformAuditLog
        fields = ["id", "created_at", "action", "actor", "before", "after"]


class ConsolePlatformSerializer(PlatformSerializer):
    """Identité de la plateforme dans la console (5.2.2) : modifiable par le super-admin ;
    couleurs illisibles refusées (contraste 4,5 : 1). Logo et icône s'envoient à part."""

    HISTORY = 5

    logo = serializers.CharField(source="logo_url", read_only=True, allow_null=True)
    icon = serializers.CharField(source="icon_url", read_only=True, allow_null=True)
    support_phone = PhoneField(
        required=False, allow_blank=True, help_text="0970000000 ou +243970000000 ; vide : aucun."
    )
    updated_at = serializers.DateTimeField(read_only=True)
    history = serializers.SerializerMethodField(
        help_text="Les dernières modifications, de la plus récente à la plus ancienne."
    )

    class Meta(PlatformSerializer.Meta):
        fields = [*PUBLIC_FIELDS, "updated_at", "history"]

    @extend_schema_field(PlatformChangeSerializer(many=True))
    def get_history(self, platform: PlatformSettings) -> list[dict]:
        changes = PlatformAuditLog.objects.filter(
            entity_type=platform._meta.label_lower, entity_id=str(platform.pk)
        ).select_related("actor")[: self.HISTORY]
        return PlatformChangeSerializer(changes, many=True).data


class PlatformLogoUploadSerializer(serializers.Serializer):
    logo = CleanedFileField(
        clean=clean_logo,
        help_text="PNG ou JPEG (1 Mo et 2 048 pixels de côté au plus), ou SVG sans script.",
    )


class PlatformIconUploadSerializer(serializers.Serializer):
    icon = CleanedFileField(
        clean=clean_icon, help_text="PNG carré de 512 à 2 048 pixels de côté, 1 Mo au plus."
    )


class ConsoleDemoRequestSerializer(serializers.ModelSerializer):
    """Demande de démonstration du site (WEB.1d), dans la console : seuls le suivi et la note
    interne se modifient. Fonction, taille et langue : codes, traduits par la console."""

    class Meta:
        model = DemoRequest
        fields = [
            "id",
            "created_at",
            "name",
            "role",
            "school_name",
            "town",
            "phone",
            "size",
            "email",
            "message",
            "language",
            "status",
            "notes",
            "updated_at",
        ]
        read_only_fields = [f for f in fields if f not in ("status", "notes")]

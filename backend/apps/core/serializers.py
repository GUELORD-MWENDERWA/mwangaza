from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.serializers import PhoneField
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.audit.serializers import AuditActorSerializer
from apps.core.images import CleanedFileField
from apps.core.models import DemoRequest, PlatformSettings, SiteBanner, SiteEntry
from apps.core.platform import check_colors, clean_icon, clean_logo

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

    def validate(self, attrs: dict) -> dict:
        current = self.instance or PlatformSettings()
        try:
            check_colors(
                attrs.get("primary_color", current.primary_color),
                attrs.get("accent_color", current.accent_color),
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(get_error_detail(error)) from None
        return attrs

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


class ConsoleSiteEntrySerializer(serializers.ModelSerializer):
    """Question de l'accueil ou des parents, ou fonction « Prochainement » (SITE.1a). Français
    obligatoire, anglais facultatif (vide : le français) ; la sorte ne change plus après la
    création ; le rang se change par `move`."""

    class Meta:
        model = SiteEntry
        fields = [
            "id",
            "kind",
            "title_fr",
            "title_en",
            "text_fr",
            "text_en",
            "position",
            "published",
            "updated_at",
        ]
        read_only_fields = ["id", "position", "updated_at"]

    def validate_kind(self, kind: str) -> str:
        if self.instance is not None and kind != self.instance.kind:
            raise serializers.ValidationError(_("The kind of an entry cannot change."))
        if self.instance is None and SiteEntry.objects.filter(kind=kind).count() >= (
            SiteEntry.MAX_PER_KIND
        ):
            raise serializers.ValidationError(
                _("This list is full (%(max)s at most): delete an entry first.")
                % {"max": SiteEntry.MAX_PER_KIND}
            )
        return kind


class SiteEntryMoveSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=["up", "down"])


BANNER_STATES = ["shown", "scheduled", "ended", "hidden"]
HTTPS = URLValidator(schemes=["https"])


class ConsoleSiteBannerSerializer(serializers.ModelSerializer):
    """Bandeau d'annonce du site (SITE.1a). `state` : affiché, programmé, terminé ou caché."""

    state = serializers.SerializerMethodField()

    class Meta:
        model = SiteBanner
        fields = [
            "text_fr",
            "text_en",
            "link",
            "starts_on",
            "ends_on",
            "active",
            "state",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    @extend_schema_field(serializers.ChoiceField(choices=BANNER_STATES))
    def get_state(self, banner: SiteBanner) -> str:
        return banner.state(timezone.localdate())

    def validate_link(self, link: str) -> str:
        """Une page du site (`/demonstration/`) ou une adresse `https://` ; rien d'autre (ni
        `javascript:`, ni `//autre-site`)."""
        if not link:
            return link
        if link.startswith("/") and not link.startswith("//") and " " not in link:
            return link
        try:
            HTTPS(link)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                _("Give a page of the site (/demonstration/) or an address starting with https://.")
            ) from error
        return link

    def validate(self, attrs: dict) -> dict:
        merged = {
            field: attrs.get(field, getattr(self.instance, field, None))
            for field in ("text_fr", "starts_on", "ends_on", "active")
        }
        if merged["active"] and not merged["text_fr"]:
            raise serializers.ValidationError({"text_fr": _("Write the text to show.")})
        if merged["starts_on"] and merged["ends_on"] and merged["ends_on"] < merged["starts_on"]:
            raise serializers.ValidationError({"ends_on": _("The end comes before the start.")})
        return attrs

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.console_serializers import ConsoleSchoolRefSerializer
from apps.notifications.attachments import validate_attachment
from apps.notifications.models import Announcement, Notification, PlatformAnnouncement
from apps.schools.models import ClassGroup, School
from apps.schools.serializers import PersonSerializer


class ClassGroupNameSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True, help_text="« 4e Électricité A ».")

    class Meta:
        model = ClassGroup
        fields = ["id", "name"]


class AnnouncementSerializer(serializers.ModelSerializer):
    class_groups = ClassGroupNameSerializer(many=True, read_only=True)
    attachment = serializers.SerializerMethodField(
        help_text="Adresse du PDF joint (`GET …/attachment/`) ; null sans pièce jointe."
    )
    published_by = PersonSerializer(source="created_by", read_only=True, allow_null=True)
    read_by = serializers.IntegerField(
        read_only=True, help_text="Familles qui l'ont lue dans le portail."
    )

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body",
            "audience",
            "class_groups",
            "attachment",
            "published_at",
            "published_by",
            "archived_at",
            "read_by",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_attachment(self, announcement: Announcement) -> str | None:
        if not announcement.attachment:
            return None
        return f"/api/announcements/{announcement.pk}/attachment/"


@extend_schema_field(OpenApiTypes.UUID)
class CurrentClassGroupField(serializers.PrimaryKeyRelatedField):
    """Une classe de l'année en cours de l'école de l'adresse : une autre est « introuvable »."""

    def get_queryset(self):
        return ClassGroup.objects.filter(academic_year__is_current=True).select_related(
            "level", "track"
        )


class RecipientsQuerySerializer(serializers.Serializer):
    audience = serializers.ChoiceField(choices=Announcement.Audience.choices)
    class_groups = CurrentClassGroupField(
        many=True,
        required=False,
        help_text="Classes de l'année en cours (pour `class_groups`).",
    )


class AnnouncementCreateSerializer(RecipientsQuerySerializer):
    title = serializers.CharField(max_length=120)
    body = serializers.CharField(max_length=4000)
    attachment = serializers.FileField(
        required=False, validators=[validate_attachment], help_text="PDF, 5 Mo au plus."
    )


class RecipientsSerializer(serializers.Serializer):
    families = serializers.IntegerField(
        help_text="Familles qui recevront l'annonce (une fratrie compte une fois)."
    )


class ConsolePlatformAnnouncementSerializer(serializers.ModelSerializer):
    schools = ConsoleSchoolRefSerializer(many=True, read_only=True)
    published_by = PersonSerializer(source="created_by", read_only=True, allow_null=True)
    read_by = serializers.IntegerField(
        read_only=True, help_text="Comptes qui l'ont lue dans la Gestion."
    )

    class Meta:
        model = PlatformAnnouncement
        fields = [
            "id",
            "title",
            "body",
            "audience",
            "schools",
            "published_at",
            "published_by",
            "archived_at",
            "read_by",
        ]
        read_only_fields = fields


class ConsolePlatformAnnouncementCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    body = serializers.CharField(max_length=2000)
    audience = serializers.ChoiceField(choices=PlatformAnnouncement.Audience.choices)
    schools = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        many=True,
        required=False,
        help_text="Écoles visées quand `audience` vaut `schools`.",
    )


class PlatformNewsSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True, help_text="Lue par ce compte.")

    class Meta:
        model = PlatformAnnouncement
        fields = ["id", "title", "body", "published_at", "is_read"]
        read_only_fields = fields


class PlatformNewsReadSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), max_length=100)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "url", "created_at", "read_at"]
        read_only_fields = fields


class NotificationReadSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        max_length=100,
        required=False,
        help_text="Notifications à noter comme lues ; absent ou vide : toutes.",
    )


class PushKeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField(max_length=200)
    auth = serializers.CharField(max_length=100)


class PushSubscriptionSerializer(serializers.Serializer):
    """Abonnement du navigateur, tel que le donne `PushSubscription.toJSON()`."""

    endpoint = serializers.URLField(max_length=1000)
    keys = PushKeysSerializer()


class PushUnsubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=1000)


class NotificationPreferencesSerializer(serializers.Serializer):
    vapid_public_key = serializers.CharField(
        read_only=True, help_text="Clé publique Web Push ; vide : envoi sur l'écran indisponible."
    )
    kinds = serializers.ListField(
        child=serializers.ChoiceField(choices=Notification.Kind.choices),
        read_only=True,
        help_text="Sortes que ce compte peut couper dans cette application.",
    )
    muted = serializers.ListField(
        child=serializers.ChoiceField(choices=Notification.Kind.choices),
        max_length=20,
        help_text="Sortes coupées sur l'écran (gardées au centre de notifications).",
    )

    def validate_muted(self, value: list[str]) -> list[str]:
        allowed = self.context["kinds"]
        return sorted({kind for kind in value if kind in allowed})

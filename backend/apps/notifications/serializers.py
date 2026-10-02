from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.notifications.attachments import validate_attachment
from apps.notifications.models import Announcement
from apps.schools.models import ClassGroup
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

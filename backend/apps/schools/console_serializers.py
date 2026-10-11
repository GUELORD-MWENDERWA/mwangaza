"""Écoles dans la console de la plateforme (5.3) : liste, fiche, création avec le premier
directeur, identité et abonnement (super-admin seulement)."""

from copy import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.models import User
from apps.accounts.serializers import PhoneField
from apps.audit.models import PlatformAuditLog
from apps.core.money import Currency
from apps.core.serializers import PlatformChangeSerializer
from apps.schools.models import School


class HeadAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "last_name", "middle_name", "first_name"]


class ConsoleSchoolSerializer(serializers.ModelSerializer):
    """Une école vue par le super-admin. Il change son adresse (`code` : l'ancienne cesse de
    marcher), ses noms et son abonnement ; couleur, fuseau, devises et logo sont réglés par
    l'école (M5). Suspendre, arrêter et réactiver passent par leurs actions ; le type d'espace
    (`environment`) est fixé à la création."""

    url = serializers.CharField(read_only=True, help_text="Adresse de l'école.")
    environment = serializers.ChoiceField(choices=School.Environment.choices, read_only=True)
    status = serializers.ChoiceField(
        choices=School.Status.choices,
        required=False,
        help_text="Essai gratuit ou active ; « suspendue » et « arrêtée » par leurs actions.",
    )
    student_count = serializers.IntegerField(
        read_only=True, help_text="Inscriptions actives de l'année en cours."
    )
    last_activity_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
        help_text="Dernière entrée de son journal, hors support et super-admin.",
    )

    class Meta:
        model = School
        fields = [
            "id",
            "code",
            "name",
            "official_name",
            "url",
            "environment",
            "status",
            "plan",
            "trial_ends_on",
            "paid_until",
            "enabled_currencies",
            "default_currency",
            "student_count",
            "last_activity_at",
            "created_at",
        ]
        read_only_fields = ["enabled_currencies", "default_currency", "created_at"]

    def validate_status(self, status: str) -> str:
        if status in School.CLOSED_STATUSES:
            message = _("Use « Suspend » or « Stop » to close a school.")
            raise serializers.ValidationError(message, code="use_suspend")
        if self.instance is not None and self.instance.is_closed:
            message = _("Reactivate the school first.")
            raise serializers.ValidationError(message, code="school_suspended")
        return status

    def validate(self, data):
        # Règles du modèle (`School.clean`) : devise principale parmi celles de l'école.
        school = copy(self.instance) if self.instance is not None else School()
        for field, value in data.items():
            if field != "head":
                setattr(school, field, value)
        try:
            school.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(get_error_detail(exc)) from None
        if "enabled_currencies" in data:
            data["enabled_currencies"] = school.enabled_currencies
        return data


class ConsoleSchoolDetailSerializer(ConsoleSchoolSerializer):
    HISTORY = 10

    history = serializers.SerializerMethodField(
        help_text="Les derniers changements faits dans la console, du plus récent au plus ancien."
    )

    class Meta(ConsoleSchoolSerializer.Meta):
        fields = [*ConsoleSchoolSerializer.Meta.fields, "history"]

    @extend_schema_field(PlatformChangeSerializer(many=True))
    def get_history(self, school: School) -> list[dict]:
        changes = PlatformAuditLog.objects.filter(
            entity_type=school._meta.label_lower, entity_id=str(school.pk)
        ).select_related("actor")[: self.HISTORY]
        return PlatformChangeSerializer(changes, many=True).data


class SchoolHeadSerializer(serializers.Serializer):
    """Premier directeur. Nouveau numéro : nom obligatoire ; numéro connu : noms ignorés (B3)."""

    phone = PhoneField(help_text="Ex. 0971234567 ou +243971234567.")
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, data):
        known = User.objects.filter(phone=data["phone"]).exists()
        if not known and not data.get("last_name", "").strip():
            message = _("This phone number has no account yet: enter the name.")
            raise serializers.ValidationError({"last_name": message}, code="name_required")
        return data


class ConsoleSchoolCreateSerializer(ConsoleSchoolSerializer):
    enabled_currencies = serializers.ListField(
        child=serializers.ChoiceField(choices=Currency.choices),
        allow_empty=False,
        help_text="Devises de l'école (au moins une).",
    )
    default_currency = serializers.ChoiceField(choices=Currency.choices)
    environment = serializers.ChoiceField(
        choices=School.Environment.choices,
        default=School.Environment.LIVE,
        help_text="Réel, essai ou démonstration : jamais changé ensuite.",
    )
    head = SchoolHeadSerializer(write_only=True)

    class Meta(ConsoleSchoolSerializer.Meta):
        fields = [*ConsoleSchoolSerializer.Meta.fields, "head"]
        read_only_fields = ["created_at"]


class SchoolStopSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=200, help_text="Motif, gardé dans le journal de la plateforme."
    )


class SchoolDeleteSerializer(serializers.Serializer):
    confirm = serializers.CharField(
        max_length=63, help_text="Code de l'espace, retapé pour confirmer."
    )


class ConsoleSchoolCreatedSerializer(serializers.Serializer):
    school = ConsoleSchoolSerializer()
    head = HeadAccountSerializer()
    temporary_password = serializers.CharField(
        allow_null=True,
        help_text="Nouveau compte seulement : affiché une seule fois, à transmettre au directeur.",
    )

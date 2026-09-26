from copy import copy
from pathlib import Path

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.money import Currency
from apps.schools.logos import validate_logo
from apps.schools.models import School


def logo_url(school: School) -> str | None:
    """Adresse du logo sur l'adresse de l'école ; elle change avec chaque logo (cache)."""
    if not school.logo:
        return None
    return f"/api/school/logo/?v={Path(school.logo.name).stem.removeprefix('logo-')}"


class _LogoMixin(serializers.Serializer):
    text_color = serializers.CharField(
        read_only=True, help_text="Couleur du texte posé sur `primary_color` : blanc ou encre."
    )
    logo = serializers.SerializerMethodField(
        help_text="Adresse du logo (`GET /api/school/logo/`, public) ; null sans logo."
    )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_logo(self, school: School) -> str | None:
        return logo_url(school)


class CurrentSchoolSerializer(_LogoMixin, serializers.ModelSerializer):
    """Informations publiques de l'école : écran de connexion (nom, couleur, logo)."""

    class Meta:
        model = School
        fields = ["code", "name", "primary_color", "text_color", "logo"]


class SchoolSettingsSerializer(_LogoMixin, serializers.ModelSerializer):
    """Paramètres de l'école (M5). Le code (adresse) ne change que par le support Mwangaza."""

    enabled_currencies = serializers.ListField(
        child=serializers.ChoiceField(choices=Currency.choices),
        allow_empty=False,
        required=False,
        help_text="Devises de l'école (au moins une).",
    )

    class Meta:
        model = School
        fields = [
            "code",
            "name",
            "official_name",
            "primary_color",
            "text_color",
            "logo",
            "timezone",
            "enabled_currencies",
            "default_currency",
        ]
        read_only_fields = ["code"]

    def validate(self, data):
        # Mêmes règles que l'administration (`School.clean`) : devise principale parmi celles de
        # l'école, couleur écrite `#RRGGBB`.
        school = copy(self.instance)
        for field, value in data.items():
            setattr(school, field, value)
        try:
            school.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from None
        for field in ("primary_color", "enabled_currencies"):
            if field in data:
                data[field] = getattr(school, field)
        return data


class LogoUploadSerializer(serializers.Serializer):
    logo = serializers.FileField(
        validators=[validate_logo], help_text="PNG, JPEG ou SVG (sans script), 1 Mo au plus."
    )

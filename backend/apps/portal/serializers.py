from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.models import User
from apps.accounts.serializers import LoginSerializer, PhoneField

_PASSWORD = {"max_length": 128, "trim_whitespace": False, "style": {"input_type": "password"}}
_REMEMBER = {"default": False, "help_text": "« Rester connecté » : 30 jours sur ce téléphone."}


class PortalLoginSerializer(LoginSerializer):
    remember = serializers.BooleanField(**_REMEMBER)


class FamilyCodeSerializer(serializers.Serializer):
    """Activation (code imprimé sur la fiche d'inscription) ou mot de passe oublié (nouveau
    code donné par l'école) : numéro, code et mot de passe choisi."""

    phone = PhoneField(help_text="Numéro du tuteur principal. Ex. 0971234567.")
    code = serializers.CharField(max_length=20, help_text="Code famille, ex. K7M4-P9TX.")
    password = serializers.CharField(**_PASSWORD)
    remember = serializers.BooleanField(**_REMEMBER)

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            # Garde le code de chaque règle (`password_too_short`…) : l'interface le traduit.
            raise serializers.ValidationError(get_error_detail(exc)) from None
        return value


class PortalMeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="__str__")

    class Meta:
        model = User
        fields = ["id", "phone", "name", "language"]

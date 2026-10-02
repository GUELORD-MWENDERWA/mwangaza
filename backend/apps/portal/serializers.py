from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.models import User
from apps.accounts.serializers import LoginSerializer, PhoneField
from apps.finance.serializers import BalanceSerializer, LastPaymentSerializer
from apps.portal import families

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


class LinkSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20, help_text="Code famille remis par l'école.")


class ChildSerializer(serializers.Serializer):
    """Un enfant inscrit cette année : classe et situation de paiement de son école."""

    id = serializers.UUIDField(source="enrollment.student_id")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    class_name = serializers.CharField(source="enrollment.class_group.name")
    balance = BalanceSerializer()
    first_overdue = serializers.CharField(
        allow_null=True, help_text="Le plus ancien frais en retard, ex. « Minerval · 1re tranche »."
    )
    last_payment = LastPaymentSerializer(allow_null=True, help_text="Hors paiements annulés.")


class LinkedFamilySerializer(serializers.Serializer):
    """Une famille reliée au compte, dans son école ; sans enfants si l'école est suspendue
    (`school_unavailable`) ou si elle a suspendu l'accès de la famille (`suspended`)."""

    id = serializers.UUIDField(source="family.id")
    school_name = serializers.CharField(source="family.school.name")
    school_timezone = serializers.CharField(source="family.school.timezone")
    status = serializers.ChoiceField(
        choices=[families.ACTIVE, families.SUSPENDED, families.SCHOOL_UNAVAILABLE]
    )
    children = ChildSerializer(many=True)

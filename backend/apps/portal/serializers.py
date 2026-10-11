from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.models import User
from apps.accounts.serializers import LoginSerializer, PhoneField
from apps.core.money import Currency
from apps.finance.models import Payment
from apps.finance.serializers import BalanceSerializer, LastPaymentSerializer
from apps.portal import children, families
from apps.schools.models import School
from apps.students.serializers import ContactDetailsSerializer

_PASSWORD = {"max_length": 128, "trim_whitespace": False, "style": {"input_type": "password"}}
_REMEMBER = {
    "default": False,
    "help_text": "« Rester connecté » : 90 jours après la dernière visite ; sinon 12 heures.",
}


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
    photo = serializers.CharField(
        allow_null=True, help_text="Adresse de la photo, seulement avec le consentement du parent."
    )


class LinkedFamilySerializer(serializers.Serializer):
    """Une famille reliée au compte, dans son école ; sans enfants si l'école est suspendue
    (`school_unavailable`) ou si elle a suspendu l'accès de la famille (`suspended`)."""

    id = serializers.UUIDField(source="family.id")
    school_name = serializers.CharField(source="family.school.name")
    school_timezone = serializers.CharField(source="family.school.timezone")
    school_environment = serializers.ChoiceField(
        source="family.school.environment",
        choices=School.Environment.choices,
        help_text="Type de l'espace : le Portail affiche un bandeau hors espace réel.",
    )
    status = serializers.ChoiceField(
        choices=[families.ACTIVE, families.SUSPENDED, families.SCHOOL_UNAVAILABLE]
    )
    children = ChildSerializer(many=True)


class ChildFeeSerializer(serializers.Serializer):
    """Un frais dû de l'année (« Minerval · 1re tranche »), après réductions."""

    id = serializers.UUIDField()
    fee = serializers.CharField()
    due_on = serializers.DateField()
    currency = serializers.ChoiceField(choices=Currency.choices)
    amount_minor = serializers.IntegerField(source="due_minor", help_text="Dû, après réductions.")
    remaining_minor = serializers.IntegerField()
    state = serializers.ChoiceField(
        choices=children.FEE_STATES,
        source="display_state",
        help_text="`paid_early` : soldé avant son échéance ; `partial` : entamé, pas encore échu.",
    )


class ChildPaymentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    receipt_number = serializers.CharField()
    paid_at = serializers.DateTimeField()
    received_amount_minor = serializers.IntegerField()
    received_currency = serializers.ChoiceField(choices=Currency.choices)
    cancelled = serializers.BooleanField(help_text="Annulé : ne compte plus, pas de reçu PDF.")
    origin = serializers.ChoiceField(
        choices=Payment.Origin.choices,
        help_text="`prior` : payé avant que l'école n'utilise l'application, pas de reçu PDF.",
    )


class ChildPaymentsSerializer(serializers.Serializer):
    """Paiements d'un enfant (H3), dans son école."""

    id = serializers.UUIDField(source="enrollment.student_id")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    class_name = serializers.CharField(source="enrollment.class_group.name")
    academic_year = serializers.CharField(source="enrollment.academic_year.name")
    school_name = serializers.CharField(source="school.name")
    school_timezone = serializers.CharField(source="school.timezone")
    photo = serializers.CharField(
        allow_null=True, help_text="Adresse de la photo, seulement avec le consentement du parent."
    )
    balance = BalanceSerializer()
    fees = ChildFeeSerializer(many=True)
    payments = ChildPaymentSerializer(many=True, help_text="Les plus récents d'abord.")


class AnnouncementsQuerySerializer(serializers.Serializer):
    family = serializers.UUIDField(
        required=False, help_text="Une seule école : l'`id` d'une famille de `families/`."
    )


class PortalAnnouncementSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    school_name = serializers.CharField(source="school.name")
    school_timezone = serializers.CharField(source="school.timezone")
    classes = serializers.ListField(
        child=serializers.CharField(),
        help_text="Classes visées où un enfant est inscrit ; vide : à toutes les familles.",
    )
    title = serializers.CharField()
    body = serializers.CharField()
    attachment = serializers.SerializerMethodField(
        help_text="Adresse du PDF joint ; null sans pièce jointe."
    )
    published_at = serializers.DateTimeField()
    read = serializers.BooleanField(help_text="Déjà lue par la famille.")

    def get_attachment(self, announcement) -> str | None:
        if not announcement.attachment:
            return None
        return f"/api/portal/announcements/{announcement.pk}/attachment/"


class ReadSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        max_length=100,
        help_text="Annonces affichées ; celles qui ne visent pas la famille sont ignorées.",
    )


class PortalProfileSerializer(ContactDetailsSerializer):
    pending_schools = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
        help_text="Écoles qui n'ont pas encore traité les coordonnées envoyées.",
    )

from rest_framework import serializers

from apps.accounts.console_serializers import ConsoleSchoolRefSerializer
from apps.core.errors import ErrorSerializer
from apps.finance.models import CreditAllocation, FeeType
from apps.finance.serializers import (
    CashRegisterSerializer,
    ExchangeRateSerializer,
    PaymentSerializer,
    StudentChargeSerializer,
    StudentCreditSerializer,
)
from apps.schools.models import AcademicYear, ClassGroup
from apps.schools.serializers import CurrentSchoolSerializer
from apps.students.models import Enrollment, Student
from apps.sync.models import ChangeLog, Device


class DeviceSerializer(serializers.ModelSerializer):
    """Un appareil du compte dans l'école (« Appareils connectés » de Mon compte)."""

    is_current = serializers.SerializerMethodField(help_text="Appareil de cette session.")

    class Meta:
        model = Device
        fields = ["id", "label", "prefix", "created_at", "last_seen_at", "is_current"]
        read_only_fields = fields

    def get_is_current(self, device: Device) -> bool:
        return str(device.pk) == self.context.get("current_device")


class SchoolDeviceSerializer(DeviceSerializer):
    """Un appareil de l'école (« Appareils et synchro », `roles.manage`)."""

    user_name = serializers.CharField(source="user.__str__", help_text="Compte de l'appareil.")

    class Meta(DeviceSerializer.Meta):
        fields = [*DeviceSerializer.Meta.fields, "kind", "user_name"]
        read_only_fields = fields


class ConsoleDeviceUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField(source="__str__")


class ConsoleDeviceSerializer(serializers.ModelSerializer):
    """Un appareil enregistré dans une école (console de la plateforme, 5.4.2)."""

    school = ConsoleSchoolRefSerializer(read_only=True)
    user = ConsoleDeviceUserSerializer(read_only=True, help_text="Compte de l'appareil.")

    class Meta:
        model = Device
        fields = [
            "id",
            "label",
            "kind",
            "prefix",
            "school",
            "user",
            "created_at",
            "last_seen_at",
            "revoked_at",
        ]
        read_only_fields = fields


class DeviceRegisterSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=80, help_text="Ex. « Windows · Edge ».")
    public_key = serializers.CharField(
        max_length=400, help_text="Clé publique ECDSA P-256 (SPKI, base64) créée par WebCrypto."
    )


class SyncDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["id", "prefix", "last_receipt_seq"]
        read_only_fields = fields


class SyncYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "name", "starts_on", "ends_on"]
        read_only_fields = fields


class SyncClassGroupSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True, help_text="« 3e Électricité A ».")

    class Meta:
        model = ClassGroup
        fields = ["id", "name", "level", "track", "section"]
        read_only_fields = fields


class SyncFeeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeType
        fields = ["id", "name", "category", "is_active"]
        read_only_fields = fields


class SyncConfigSerializer(serializers.Serializer):
    """Entité `config` : ce qui se modifie en ligne seulement. Frais, caisses et taux : null
    sans droit sur les finances."""

    school = CurrentSchoolSerializer()
    academic_year = SyncYearSerializer(allow_null=True, help_text="Année en cours.")
    class_groups = SyncClassGroupSerializer(many=True, help_text="Classes de l'année en cours.")
    fee_types = SyncFeeTypeSerializer(many=True, allow_null=True)
    cash_registers = CashRegisterSerializer(many=True, allow_null=True)
    exchange_rate = ExchangeRateSerializer(allow_null=True, help_text="Taux des encaissements.")


class SyncStudentSerializer(serializers.ModelSerializer):
    family_code = serializers.CharField(source="family.code", read_only=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "matricule",
            "last_name",
            "middle_name",
            "first_name",
            "sex",
            "birth_date",
            "family_code",
        ]
        read_only_fields = fields


class SyncCreditUseSerializer(serializers.ModelSerializer):
    """Part d'un crédit utilisée sur un frais dû : payée depuis `created_at`, jusqu'à
    l'annulation du crédit (`voided_at`)."""

    voided_at = serializers.DateTimeField(
        source="credit.voided_at", read_only=True, allow_null=True
    )

    class Meta:
        model = CreditAllocation
        fields = ["student_charge", "amount_minor", "created_at", "voided_at"]
        read_only_fields = fields


class SyncEnrollmentSerializer(serializers.ModelSerializer):
    """Entité `enrollment` : l'élève, sa classe, ses frais dus, ses paiements et ses crédits à
    traiter de l'année. Frais, paiements et crédits : null sans droit sur les finances ; `state`
    des frais est calculé le jour de l'envoi (l'appareil le recalcule d'après `due_on`)."""

    student = SyncStudentSerializer(read_only=True)
    charges = StudentChargeSerializer(
        source="sync_charges", many=True, read_only=True, allow_null=True
    )
    payments = PaymentSerializer(source="sync_payments", many=True, read_only=True, allow_null=True)
    credits = StudentCreditSerializer(
        source="sync_credits", many=True, read_only=True, allow_null=True
    )
    credit_uses = SyncCreditUseSerializer(
        source="sync_credit_uses", many=True, read_only=True, allow_null=True
    )

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "academic_year",
            "class_group",
            "status",
            "enrolled_on",
            "left_on",
            "student",
            "charges",
            "payments",
            "credits",
            "credit_uses",
        ]
        read_only_fields = fields


class SnapshotQuerySerializer(serializers.Serializer):
    after = serializers.UUIDField(
        required=False, help_text="Dernière inscription de la page précédente (`next`)."
    )
    limit = serializers.IntegerField(min_value=1, max_value=500, default=200)


class SnapshotSerializer(serializers.Serializer):
    cursor = serializers.IntegerField(
        allow_null=True,
        help_text="Première page seulement : numéro à garder pour `pull` (pas celui d'une page "
        "suivante).",
    )
    device = SyncDeviceSerializer(allow_null=True, help_text="Première page seulement.")
    config = SyncConfigSerializer(allow_null=True, help_text="Première page seulement.")
    enrollments = SyncEnrollmentSerializer(many=True)
    next = serializers.UUIDField(allow_null=True, help_text="`after` de la page suivante.")


class PullQuerySerializer(serializers.Serializer):
    since = serializers.IntegerField(min_value=0, help_text="Dernier numéro reçu (`cursor`).")
    limit = serializers.IntegerField(min_value=1, max_value=1000, default=500)


class ChangeSerializer(serializers.Serializer):
    seq = serializers.IntegerField()
    entity_type = serializers.ChoiceField(choices=ChangeLog.Entity.choices)
    entity_id = serializers.UUIDField()
    operation = serializers.ChoiceField(
        choices=ChangeLog.Operation.choices,
        help_text="`delete` : l'appareil l'efface (inscription hors de l'année en cours).",
    )
    enrollment = SyncEnrollmentSerializer(allow_null=True)
    config = SyncConfigSerializer(allow_null=True)


class PullSerializer(serializers.Serializer):
    changes = ChangeSerializer(many=True)
    cursor = serializers.IntegerField(help_text="`since` de la prochaine demande.")
    has_more = serializers.BooleanField(help_text="Encore des changements : redemander.")


class IncomingSerializer(serializers.Serializer):
    op_id = serializers.UUIDField(help_text="UUID v7 de l'opération, donné par l'appareil.")
    type = serializers.CharField(max_length=40, help_text="Ex. `payment.create`.")
    payload = serializers.DictField(help_text="Contenu propre au type d'opération.")
    created_at = serializers.DateTimeField(required=False, help_text="Heure de l'appareil.")


class PushSerializer(serializers.Serializer):
    receipt_seq = serializers.IntegerField(
        min_value=0, required=False, help_text="Dernier numéro de reçu donné par l'appareil."
    )
    operations = IncomingSerializer(many=True, max_length=100, help_text="Dans l'ordre.")


class OutcomeSerializer(serializers.Serializer):
    op_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=[
            ("applied", "applied"),
            ("duplicate", "duplicate"),
            ("rejected", "rejected"),
        ],
        help_text="`duplicate` : déjà appliquée, même résultat.",
    )
    result = serializers.DictField(help_text="Ex. `{payment, receipt_number}`.")
    error = ErrorSerializer(allow_null=True, help_text="Raison du refus.")


class PushResultSerializer(serializers.Serializer):
    results = OutcomeSerializer(many=True)

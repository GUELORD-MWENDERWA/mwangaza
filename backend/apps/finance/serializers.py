from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from apps.core.money import Currency
from apps.finance import services
from apps.finance.models import (
    CashRegister,
    CashSession,
    Discount,
    ExchangeRate,
    FeeRule,
    FeeType,
    InstallmentTemplate,
    Payment,
    PaymentAllocation,
    StudentCharge,
)
from apps.finance.services import Installment, Scope
from apps.schools.models import AcademicYear, ClassGroup, Level, Track
from apps.schools.serializers import PersonSerializer
from apps.students.models import Enrollment

# Au-delà, c'est une erreur de saisie (et la limite d'un entier de la base reste loin).
MAX_AMOUNT_MINOR = 10**12
# Mensuel : une tranche par mois ; au-delà de deux ans, c'est une erreur.
MAX_INSTALLMENTS = 24


class FeeTypeSerializer(serializers.ModelSerializer):
    rule_count = serializers.IntegerField(
        read_only=True, help_text="Barèmes, toutes années : un type qui en a ne se supprime pas."
    )

    class Meta:
        model = FeeType
        fields = [
            "id",
            "name",
            "category",
            "funds_teacher_bonus",
            "accounting_code",
            "is_active",
            "rule_count",
        ]


class FeeTypeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeType
        fields = ["name", "category", "funds_teacher_bonus", "accounting_code", "is_active"]


class InstallmentSerializer(serializers.ModelSerializer):
    amount_minor = serializers.IntegerField(min_value=1, max_value=MAX_AMOUNT_MINOR)

    class Meta:
        model = InstallmentTemplate
        fields = ["id", "label", "amount_minor", "due_on", "order"]
        read_only_fields = ["id", "order"]


class FeeRuleSerializer(serializers.ModelSerializer):
    scope_name = serializers.CharField(
        read_only=True, help_text="Niveau, option ou classe ; vide : toute l'école."
    )
    installments = InstallmentSerializer(many=True, read_only=True)

    class Meta:
        model = FeeRule
        fields = [
            "id",
            "academic_year",
            "fee_type",
            "level",
            "track",
            "class_group",
            "scope_name",
            "currency",
            "total_amount_minor",
            "schedule_kind",
            "installments",
        ]


class FeeRuleUpdateSerializer(serializers.Serializer):
    """Tout le barème : portée (au plus un de `level`, `track`, `class_group` ; aucun = toute
    l'école), devise, total et tranches (somme = total)."""

    level = serializers.PrimaryKeyRelatedField(
        queryset=Level.objects, required=False, allow_null=True
    )
    track = serializers.PrimaryKeyRelatedField(
        queryset=Track.objects, required=False, allow_null=True
    )
    class_group = serializers.PrimaryKeyRelatedField(
        queryset=ClassGroup.objects, required=False, allow_null=True
    )
    currency = serializers.ChoiceField(choices=Currency.choices)
    total_amount_minor = serializers.IntegerField(
        min_value=1, max_value=MAX_AMOUNT_MINOR, help_text="Plus petite unité : centimes, francs."
    )
    schedule_kind = serializers.ChoiceField(choices=FeeRule.ScheduleKind.choices)
    installments = InstallmentSerializer(many=True, max_length=MAX_INSTALLMENTS)

    def to_service(self) -> dict:
        data = dict(self.validated_data)
        scope = Scope(
            level=data.pop("level", None),
            track=data.pop("track", None),
            class_group=data.pop("class_group", None),
        )
        data["installments"] = [
            Installment(item["label"], item["amount_minor"], item["due_on"])
            for item in data["installments"]
        ]
        return {**data, "scope": scope}


class FeeRuleCreateSerializer(FeeRuleUpdateSerializer):
    academic_year = serializers.PrimaryKeyRelatedField(queryset=AcademicYear.objects)
    fee_type = serializers.PrimaryKeyRelatedField(queryset=FeeType.objects)


class ExchangeRateSerializer(serializers.ModelSerializer):
    set_by = PersonSerializer(source="created_by", read_only=True, allow_null=True)
    set_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ExchangeRate
        fields = ["id", "academic_year", "rate", "reason", "set_by", "set_at"]


class ExchangeRateCreateSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(queryset=AcademicYear.objects)
    rate = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        min_value=Decimal("0.000001"),
        help_text="Francs pour 1 dollar, tel que saisi (« 2850 »).",
    )
    reason = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        default="",
        help_text="Obligatoire pour une correction (l'année a déjà un taux).",
    )


class YearFilterSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects, required=False, help_text="Absent : l'année en cours."
    )


CHARGE_STATES = [services.PAID, services.OVERDUE, services.UPCOMING]


class StudentChargeSerializer(serializers.ModelSerializer):
    fee_type_name = serializers.CharField(source="fee_type.name", read_only=True)
    fee_category = serializers.ChoiceField(
        source="fee_type.category", choices=FeeType.Category.choices, read_only=True
    )
    discount_minor = serializers.IntegerField(
        read_only=True, help_text="Part des réductions de l'élève (E3) ; 0 si ce n'est plus dû."
    )
    paid_minor = serializers.IntegerField(
        read_only=True, help_text="Paiements non annulés affectés à ce frais."
    )
    remaining_minor = serializers.IntegerField(
        read_only=True,
        help_text="Reste dû : montant moins réductions et payé ; 0 si ce n'est plus dû.",
    )
    state = serializers.ChoiceField(
        choices=CHARGE_STATES,
        allow_null=True,
        read_only=True,
        help_text="Soldé, en retard (échéance passée, reste > 0) ou à venir ; "
        "null si le frais est retiré ou remplacé.",
    )

    class Meta:
        model = StudentCharge
        fields = [
            "id",
            "enrollment",
            "fee_type",
            "fee_type_name",
            "fee_category",
            "label",
            "amount_minor",
            "currency",
            "due_on",
            "source",
            "status",
            "discount_minor",
            "paid_minor",
            "remaining_minor",
            "state",
        ]


class CurrencyBalanceSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    total_minor = serializers.IntegerField(help_text="Dû pour l'année, après réductions.")
    paid_minor = serializers.IntegerField()
    remaining_minor = serializers.IntegerField()
    overdue_minor = serializers.IntegerField(help_text="Reste des échéances passées.")
    next_due_minor = serializers.IntegerField(help_text="Reste dû à `next_due_on`.")


class BalanceSerializer(serializers.Serializer):
    """Solde d'un élève (2.7), par devise, jamais additionné entre devises."""

    situation = serializers.ChoiceField(
        choices=[services.UP_TO_DATE, services.PARTIAL, services.OVERDUE],
        help_text="À jour (rien en retard), partielle (en retard, mais des paiements), en retard.",
    )
    next_due_on = serializers.DateField(
        allow_null=True, help_text="Prochaine échéance pas encore passée avec un reste dû."
    )
    currencies = CurrencyBalanceSerializer(many=True)


class StudentChargeFilterSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField(help_text="Inscription de l'élève pour une année.")


class RescheduleSerializer(serializers.Serializer):
    """Échéancier particulier (E4) : les versements remplacent ce qui reste dû pour ce frais."""

    enrollment = serializers.PrimaryKeyRelatedField(queryset=Enrollment.objects)
    fee_type = serializers.PrimaryKeyRelatedField(queryset=FeeType.objects)
    reason = serializers.CharField(max_length=200)
    parent_signed = serializers.BooleanField(
        default=False, help_text="Engagement signé par le parent, à classer au dossier."
    )
    installments = InstallmentSerializer(many=True, allow_empty=False, max_length=MAX_INSTALLMENTS)

    def to_service(self) -> dict:
        data = dict(self.validated_data)
        data["installments"] = [
            Installment(item["label"], item["amount_minor"], item["due_on"])
            for item in data["installments"]
        ]
        return data


class DiscountSerializer(serializers.ModelSerializer):
    fee_type_name = serializers.CharField(source="fee_type.name", read_only=True, allow_null=True)
    granted_by = PersonSerializer(source="created_by", read_only=True, allow_null=True)
    granted_at = serializers.DateTimeField(source="created_at", read_only=True)
    revoked_by = PersonSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Discount
        fields = [
            "id",
            "enrollment",
            "fee_type",
            "fee_type_name",
            "kind",
            "percent",
            "amount_minor",
            "currency",
            "reason_code",
            "reason",
            "granted_by",
            "granted_at",
            "revoked_at",
            "revoked_by",
            "revoke_reason",
        ]


class DiscountCreateSerializer(serializers.Serializer):
    """Réduction (E3) : `percent` (1 à 100) pour un pourcentage, `amount_minor` dans la devise du
    frais pour un montant ; `fee_type` vide : tous les frais (pourcentage seulement)."""

    enrollment = serializers.PrimaryKeyRelatedField(queryset=Enrollment.objects)
    fee_type = serializers.PrimaryKeyRelatedField(
        queryset=FeeType.objects, allow_null=True, default=None
    )
    kind = serializers.ChoiceField(choices=Discount.Kind.choices)
    percent = serializers.IntegerField(min_value=1, max_value=100, required=False)
    amount_minor = serializers.IntegerField(min_value=1, max_value=MAX_AMOUNT_MINOR, required=False)
    reason_code = serializers.ChoiceField(choices=Discount.Reason.choices)
    reason = serializers.CharField(max_length=200)

    def validate(self, attrs: dict) -> dict:
        field = "percent" if attrs["kind"] == Discount.Kind.PERCENT else "amount_minor"
        if attrs.get(field) is None:
            message = self.fields[field].error_messages["required"]
            raise serializers.ValidationError({field: [ErrorDetail(message, code="required")]})
        return attrs


class DiscountRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)


# Caisses et paiements (F1-F2)


class CashRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashRegister
        fields = ["id", "name", "code", "is_active"]
        read_only_fields = ["is_active"]
        extra_kwargs = {"code": {"help_text": "C1 : dans le numéro des reçus, fixé à la création."}}


class OpenSessionSerializer(serializers.ModelSerializer):
    cashier = PersonSerializer(read_only=True)

    class Meta:
        model = CashSession
        fields = ["id", "cashier", "opened_at"]


class CashRegisterStateSerializer(CashRegisterSerializer):
    """Caisse et, si elle est ouverte, sa session (« Occupée » à l'ouverture, M13)."""

    open_session = serializers.SerializerMethodField()

    class Meta(CashRegisterSerializer.Meta):
        fields = [*CashRegisterSerializer.Meta.fields, "open_session"]

    @extend_schema_field(OpenSessionSerializer(allow_null=True))
    def get_open_session(self, register: CashRegister) -> dict | None:
        sessions = getattr(register, "open_sessions", [])
        return OpenSessionSerializer(sessions[0]).data if sessions else None


class CashRegisterUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashRegister
        fields = ["name", "is_active"]


class CashSessionSerializer(serializers.ModelSerializer):
    cash_register = CashRegisterSerializer(read_only=True)
    cashier = PersonSerializer(read_only=True)

    class Meta:
        model = CashSession
        fields = ["id", "cash_register", "cashier", "opened_at", "closed_at"]


class CashSessionOpenSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=False, help_text="UUID v7 de l'appareil : un deuxième envoi rend la même session."
    )
    cash_register = serializers.PrimaryKeyRelatedField(queryset=CashRegister.objects)


class SessionTotalSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    amount_minor = serializers.IntegerField()
    count = serializers.IntegerField()


class CurrentCashSessionSerializer(serializers.Serializer):
    """Caisse ouverte du caissier (M13) et taux des encaissements."""

    session = CashSessionSerializer(allow_null=True)
    totals = SessionTotalSerializer(
        many=True, help_text="Paiements non annulés de la session, par devise, jamais additionnés."
    )
    rate = serializers.DecimalField(
        max_digits=14, decimal_places=6, allow_null=True, help_text="Francs pour 1 dollar."
    )
    rate_is_fallback = serializers.BooleanField(
        help_text="Pas de taux cette année : dernier taux connu, à signaler au comptable."
    )


class PaymentAllocationSerializer(serializers.ModelSerializer):
    fee_type_name = serializers.CharField(source="student_charge.fee_type.name", read_only=True)
    label = serializers.CharField(source="student_charge.label", read_only=True)
    currency = serializers.ChoiceField(
        source="student_charge.currency", choices=Currency.choices, read_only=True
    )

    class Meta:
        model = PaymentAllocation
        fields = [
            "student_charge",
            "fee_type_name",
            "label",
            "currency",
            "received_minor",
            "amount_minor",
        ]
        extra_kwargs = {
            "received_minor": {"help_text": "Part du montant reçu, dans la devise reçue."},
            "amount_minor": {"help_text": "Montant affecté, dans la devise du frais."},
        }


class PaymentStudentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    matricule = serializers.CharField()


class PaymentSerializer(serializers.ModelSerializer):
    student = PaymentStudentSerializer(source="enrollment.student", read_only=True)
    class_group = serializers.CharField(source="enrollment.class_group.name", read_only=True)
    cash_register = serializers.CharField(source="cash_session.cash_register.code", read_only=True)
    cashier = PersonSerializer(read_only=True)
    cancelled = serializers.BooleanField(source="is_cancelled", read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_number",
            "enrollment",
            "student",
            "class_group",
            "cash_register",
            "cashier",
            "received_amount_minor",
            "received_currency",
            "rate_used",
            "paid_at",
            "method",
            "note",
            "cancelled",
            "allocations",
        ]


class PartSerializer(serializers.Serializer):
    student_charge = serializers.UUIDField()
    received_minor = serializers.IntegerField(min_value=1, max_value=MAX_AMOUNT_MINOR)


class PaymentCreateSerializer(serializers.Serializer):
    """Encaissement (F2) : sans `allocations`, répartition par défaut (devise reçue d'abord,
    échéances les plus anciennes) ; avec, la répartition ajustée par le caissier."""

    id = serializers.UUIDField(
        required=False, help_text="UUID v7 de l'appareil : un deuxième envoi rend le même paiement."
    )
    enrollment = serializers.PrimaryKeyRelatedField(queryset=Enrollment.objects)
    received_amount_minor = serializers.IntegerField(min_value=1, max_value=MAX_AMOUNT_MINOR)
    received_currency = serializers.ChoiceField(choices=Currency.choices)
    convert = serializers.BooleanField(
        default=False,
        help_text="Répartition par défaut : aussi sur les frais de l'autre devise, convertis.",
    )
    allocations = PartSerializer(many=True, required=False, allow_empty=False, max_length=100)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def to_service(self) -> dict:
        data = dict(self.validated_data)
        parts = data.pop("allocations", None)
        if parts is not None:
            parts = [services.Part(p["student_charge"], p["received_minor"]) for p in parts]
        return {"parts": parts, "payment_id": data.pop("id", None), **data}


class PaymentFilterSerializer(serializers.Serializer):
    session = serializers.UUIDField(required=False, help_text="Paiements d'une session de caisse.")
    enrollment = serializers.UUIDField(required=False, help_text="Paiements d'une inscription.")
    search = serializers.CharField(
        required=False, help_text="Numéro de reçu, nom ou matricule de l'élève."
    )

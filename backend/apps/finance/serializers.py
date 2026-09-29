from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from apps.core.money import Currency
from apps.finance import services
from apps.finance.models import (
    CancellationRequest,
    CashRegister,
    CashSession,
    CreditAllocation,
    Discount,
    ExchangeRate,
    FeeRule,
    FeeType,
    InstallmentTemplate,
    Payment,
    PaymentAllocation,
    PaymentCancellation,
    StudentCharge,
    StudentCredit,
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
    due_on = serializers.DateField(source="student_charge.due_on", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = [
            "student_charge",
            "fee_type_name",
            "label",
            "currency",
            "due_on",
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
    # Paiements d'une session retrouvés sur l'appareil (caisse hors ligne, 3.5).
    cash_session = serializers.UUIDField(source="cash_session_id", read_only=True)
    cashier = PersonSerializer(read_only=True)
    cancelled = serializers.SerializerMethodField()
    # Pour un duplicata exact sur l'appareil : un paiement annulé après un autre comptait encore
    # quand celui-ci a été encaissé.
    cancelled_at = serializers.DateTimeField(read_only=True, allow_null=True)
    cancellation_pending = serializers.BooleanField(
        read_only=True, help_text="Annulation demandée, en attente de décision : compte encore."
    )
    allocations = PaymentAllocationSerializer(many=True, read_only=True)

    def get_cancelled(self, payment: Payment) -> bool:
        return payment.cancelled_at is not None

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_number",
            "enrollment",
            "student",
            "class_group",
            "cash_register",
            "cash_session",
            "cashier",
            "received_amount_minor",
            "received_currency",
            "rate_used",
            "paid_at",
            "method",
            "note",
            "cancelled",
            "cancelled_at",
            "cancellation_pending",
            "allocations",
        ]


class PaymentReceiptSerializer(PaymentSerializer):
    """Paiement avec ce qu'imprime son reçu (F3) : nom de la caisse, année scolaire et solde de
    l'élève juste après ce paiement (`services.balance_after`, mis dans `balance_after`)."""

    cash_register_name = serializers.CharField(
        source="cash_session.cash_register.name", read_only=True
    )
    academic_year = serializers.CharField(source="enrollment.academic_year.name", read_only=True)
    balance = BalanceSerializer(source="balance_after", read_only=True)

    class Meta(PaymentSerializer.Meta):
        fields = [*PaymentSerializer.Meta.fields, "cash_register_name", "academic_year", "balance"]


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


# Crédits d'élèves (3.6.1, M14)

CREDIT_STATES = [services.TO_PROCESS, services.USED, services.VOIDED]


class StudentCreditFilterSerializer(YearFilterSerializer):
    state = serializers.ChoiceField(
        choices=[*CREDIT_STATES, "all"],
        default=services.TO_PROCESS,
        help_text="À traiter (défaut), utilisés, annulés ou tous.",
    )


class CreditAllocationSerializer(serializers.ModelSerializer):
    fee_type_name = serializers.CharField(source="student_charge.fee_type.name", read_only=True)
    label = serializers.CharField(source="student_charge.label", read_only=True)
    due_on = serializers.DateField(source="student_charge.due_on", read_only=True)
    created_by = PersonSerializer(read_only=True)

    class Meta:
        model = CreditAllocation
        fields = [
            "student_charge",
            "fee_type_name",
            "label",
            "due_on",
            "amount_minor",
            "created_at",
            "created_by",
        ]


class CreditProposalSerializer(serializers.Serializer):
    student_charge = serializers.UUIDField()
    fee_type_name = serializers.CharField()
    label = serializers.CharField()
    due_on = serializers.DateField()
    amount_minor = serializers.IntegerField()


class StudentCreditSerializer(serializers.ModelSerializer):
    """Crédit d'un élève, avec son origine : le reçu du paiement hors ligne en trop, ou la
    réduction accordée sur des échéances déjà payées."""

    student = PaymentStudentSerializer(source="enrollment.student", read_only=True)
    class_group = serializers.CharField(source="enrollment.class_group.name", read_only=True)
    used_minor = serializers.IntegerField(read_only=True)
    remaining_minor = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    receipt_number = serializers.CharField(
        source="source_payment.receipt_number", read_only=True, allow_null=True
    )
    cash_register_name = serializers.CharField(
        source="source_payment.cash_session.cash_register.name", read_only=True, allow_null=True
    )
    paid_at = serializers.DateTimeField(
        source="source_payment.paid_at", read_only=True, allow_null=True
    )
    discount_reason = serializers.CharField(
        source="source_discount.reason", read_only=True, allow_null=True
    )
    discount_fee_type = serializers.CharField(
        source="source_discount.fee_type.name", read_only=True, allow_null=True
    )

    class Meta:
        model = StudentCredit
        fields = [
            "id",
            "enrollment",
            "student",
            "class_group",
            "origin",
            "amount_minor",
            "currency",
            "used_minor",
            "remaining_minor",
            "state",
            "created_at",
            "voided_at",
            "receipt_number",
            "cash_register_name",
            "paid_at",
            "discount_reason",
            "discount_fee_type",
        ]

    def get_remaining_minor(self, credit: StudentCredit) -> int:
        if credit.voided_at is not None:
            return 0
        return credit.amount_minor - credit.used_minor

    @extend_schema_field(serializers.ChoiceField(choices=CREDIT_STATES))
    def get_state(self, credit: StudentCredit) -> str:
        return services.credit_state(credit)


class StudentCreditDetailSerializer(StudentCreditSerializer):
    """Crédit avec ses utilisations (justificatif) et ce que ferait « Utiliser le crédit »
    (`proposal`, vide s'il n'est plus à traiter)."""

    allocations = CreditAllocationSerializer(many=True, read_only=True)
    proposal = CreditProposalSerializer(many=True, read_only=True)

    class Meta(StudentCreditSerializer.Meta):
        fields = [*StudentCreditSerializer.Meta.fields, "allocations", "proposal"]


class CreditAmountSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    amount_minor = serializers.IntegerField()


class CreditSummarySerializer(serializers.Serializer):
    to_process = serializers.IntegerField(help_text="Crédits à traiter.")
    amounts = CreditAmountSerializer(many=True, help_text="Reste des crédits à traiter.")
    used_this_month = serializers.IntegerField(help_text="Crédits utilisés depuis le 1er du mois.")


# Annulations (3.8.1, F7)


class CancelledPaymentSerializer(PaymentSerializer):
    """Paiement d'une demande d'annulation : son état est celui de la demande."""

    cash_register_name = serializers.CharField(
        source="cash_session.cash_register.name", read_only=True
    )
    academic_year = serializers.CharField(source="enrollment.academic_year.name", read_only=True)

    class Meta(PaymentSerializer.Meta):
        fields = [
            *(
                name
                for name in PaymentSerializer.Meta.fields
                if name not in {"cancelled", "cancelled_at", "cancellation_pending"}
            ),
            "cash_register_name",
            "academic_year",
        ]


class PaymentCancellationSerializer(serializers.ModelSerializer):
    approved_by = PersonSerializer(read_only=True)

    class Meta:
        model = PaymentCancellation
        fields = ["receipt_number", "approved_by", "approved_at"]


class CancellationRequestSerializer(serializers.ModelSerializer):
    payment = CancelledPaymentSerializer(read_only=True)
    requested_by = PersonSerializer(read_only=True)
    decided_by = PersonSerializer(read_only=True, allow_null=True)
    offline = serializers.SerializerMethodField(help_text="Demandée hors ligne.")
    cancellation = serializers.SerializerMethodField()

    class Meta:
        model = CancellationRequest
        fields = [
            "id",
            "payment",
            "reason",
            "requested_by",
            "requested_at",
            "offline",
            "status",
            "decided_by",
            "decided_at",
            "decision_note",
            "cancellation",
        ]

    def get_offline(self, request: CancellationRequest) -> bool:
        return request.device_id is not None

    @extend_schema_field(PaymentCancellationSerializer(allow_null=True))
    def get_cancellation(self, request: CancellationRequest) -> dict | None:
        """L'annulation validée et son reçu (demande validée seulement)."""
        if request.status != CancellationRequest.Status.APPROVED:
            return None
        return PaymentCancellationSerializer(request.payment.cancellation).data


class CancellationReceiptSerializer(CancellationRequestSerializer):
    """Demande validée avec ce qu'imprime le reçu d'annulation (M15) : le reste dû par l'élève
    juste après l'annulation (`services.balance_after_cancellation`)."""

    balance = BalanceSerializer(source="balance_after", read_only=True)

    class Meta(CancellationRequestSerializer.Meta):
        fields = [*CancellationRequestSerializer.Meta.fields, "balance"]


class CancellationCreateSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=False, help_text="UUID v7 de l'appareil : un deuxième envoi rend la même demande."
    )
    payment = serializers.PrimaryKeyRelatedField(queryset=Payment.objects)
    reason = serializers.CharField(max_length=200)


class CancellationDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class CancellationFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=CancellationRequest.Status.choices,
        default=CancellationRequest.Status.PENDING,
        help_text="En attente (défaut), validées ou refusées.",
    )

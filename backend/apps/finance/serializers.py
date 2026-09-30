from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from apps.core.money import Currency
from apps.finance import services, unpaid
from apps.finance.models import (
    CancellationRequest,
    CashClosing,
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
from apps.schools import organisation
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


class ClosingCurrencySerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    expected_minor = serializers.IntegerField(
        help_text="Paiements de la session pas annulés à l'heure de clôture."
    )
    count = serializers.IntegerField()


class ClosingFeeTypeSerializer(serializers.Serializer):
    fee_type = serializers.CharField(
        allow_null=True, help_text="Vide : trop-perçu, devenu crédit de l'élève."
    )
    currency = serializers.ChoiceField(choices=Currency.choices, help_text="Devise reçue.")
    amount_minor = serializers.IntegerField()


class CashClosingLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashClosing
        fields = ["currency", "expected_minor", "counted_minor", "difference_minor"]


class CashClosingSerializer(serializers.Serializer):
    lines = CashClosingLineSerializer(many=True)
    note = serializers.CharField(help_text="Explication de l'écart.")
    closed_at = serializers.DateTimeField(help_text="Heure de l'appareil si faite hors ligne.")
    closed_by = PersonSerializer()
    offline = serializers.BooleanField()
    received_at = serializers.DateTimeField(help_text="Arrivée au serveur.")


class CashClosingSummarySerializer(serializers.Serializer):
    """Clôture d'une session de caisse (F8) : à faire, ou faite (`closing`)."""

    session = CashSessionSerializer()
    currencies = ClosingCurrencySerializer(many=True)
    fee_types = ClosingFeeTypeSerializer(many=True)
    payments_count = serializers.IntegerField(help_text="Reçus donnés, annulés compris.")
    first_receipt = serializers.CharField(allow_null=True)
    last_receipt = serializers.CharField(allow_null=True)
    cancelled = SessionTotalSerializer(many=True, help_text="Annulations validées.")
    cancellations_pending = serializers.IntegerField()
    closing = CashClosingSerializer(allow_null=True)


class PaymentStudentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    matricule = serializers.CharField()


# Clôtures vues par le comptable (3.8.3, M16)


class ClosingFilterSerializer(serializers.Serializer):
    month = serializers.DateField(
        input_formats=["%Y-%m"],
        required=False,
        help_text="Mois d'ouverture des sessions (AAAA-MM) ; absent : le mois en cours.",
    )
    cash_register = serializers.PrimaryKeyRelatedField(
        queryset=CashRegister.objects, required=False, help_text="Une seule caisse."
    )


class SessionLineSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    expected_minor = serializers.IntegerField(
        help_text="Figé à la clôture ; session ouverte : paiements pas annulés à cette heure."
    )
    counted_minor = serializers.IntegerField(allow_null=True, help_text="Vide : pas clôturée.")
    difference_minor = serializers.IntegerField(allow_null=True, help_text="Compté - attendu.")


CLOSING_STATES = [services.OPEN, services.UNCLOSED, services.BALANCED, services.DIFFERENCE]
STATE_HELP = "Ouverte aujourd'hui, pas clôturée (ouverte avant aujourd'hui), conforme, ou écart."


class CashSessionClosingSerializer(CashSessionSerializer):
    """Une session dans la liste des clôtures (M16)."""

    payments_count = serializers.IntegerField(help_text="Reçus donnés, annulés compris.")
    state = serializers.ChoiceField(choices=CLOSING_STATES, help_text=STATE_HELP)
    lines = SessionLineSerializer(many=True)
    late = SessionTotalSerializer(
        many=True, help_text="Paiements pas annulés arrivés au serveur après la clôture."
    )

    class Meta(CashSessionSerializer.Meta):
        fields = [*CashSessionSerializer.Meta.fields, "payments_count", "state", "lines", "late"]


class ClosingDifferenceSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    difference_minor = serializers.IntegerField(help_text="Somme des écarts du mois.")
    sessions = serializers.IntegerField(help_text="Sessions avec un écart dans cette devise.")


class ClosingsSummarySerializer(serializers.Serializer):
    sessions = serializers.IntegerField()
    cash_registers = serializers.IntegerField()
    differences = ClosingDifferenceSerializer(many=True)
    registers = CashRegisterSerializer(many=True, help_text="Caisses de l'école (filtre).")
    unclosed = CashSessionSerializer(
        many=True, help_text="Pas clôturées, ouvertes avant aujourd'hui, quel que soit le mois."
    )


class LatePaymentSerializer(serializers.ModelSerializer):
    student = PaymentStudentSerializer(source="enrollment.student", read_only=True)
    amount_minor = serializers.IntegerField(source="received_amount_minor", read_only=True)
    currency = serializers.ChoiceField(
        source="received_currency", choices=Currency.choices, read_only=True
    )
    received_at = serializers.DateTimeField(
        source="created_at", read_only=True, help_text="Arrivée au serveur."
    )
    cancelled = serializers.BooleanField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_number",
            "student",
            "amount_minor",
            "currency",
            "paid_at",
            "received_at",
            "cancelled",
        ]


class CashClosingDetailSerializer(CashClosingSummarySerializer):
    """Clôture d'une session vue par le comptable : le bordereau, l'état, et les paiements
    encaissés hors ligne arrivés après la clôture (hors de l'attendu figé)."""

    state = serializers.ChoiceField(choices=CLOSING_STATES, help_text=STATE_HELP)
    late_payments = LatePaymentSerializer(many=True)


class CountedSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    amount_minor = serializers.IntegerField(min_value=0, max_value=10**13)


class CashCloseSerializer(serializers.Serializer):
    counted = CountedSerializer(many=True, help_text="Argent compté, par devise.")
    note = serializers.CharField(
        max_length=500, required=False, allow_blank=True, help_text="Obligatoire s'il y a un écart."
    )

    def validate_counted(self, value: list[dict]) -> list[dict]:
        if len({item["currency"] for item in value}) != len(value):
            raise serializers.ValidationError(_("Each currency once."), code="counted_currencies")
        return value

    def to_service(self) -> dict:
        data = self.validated_data
        counted = {item["currency"]: item["amount_minor"] for item in data["counted"]}
        return {"counted": counted, "note": data.get("note", "")}


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
            "source_payment",
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
        read_only_fields = fields

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


# Impayés (4.1.1, G1)


class UnpaidFilterSerializer(YearFilterSerializer):
    class_group = serializers.PrimaryKeyRelatedField(
        queryset=ClassGroup.objects, required=False, help_text="Une seule classe."
    )
    fee_type = serializers.PrimaryKeyRelatedField(
        queryset=FeeType.objects, required=False, help_text="Un seul type de frais."
    )
    installment = serializers.CharField(
        required=False,
        max_length=40,
        help_text="Libellé de la tranche (« 1re tranche », « Octobre ») ; absent : toutes.",
    )
    over_days = serializers.IntegerField(
        default=0,
        min_value=0,
        max_value=366,
        help_text="Seulement les frais en retard de plus de ce nombre de jours ; 0 : tous.",
    )
    currency = serializers.ChoiceField(
        choices=Currency.choices, required=False, help_text="Seulement les frais dans cette devise."
    )
    order = serializers.ChoiceField(
        choices=unpaid.ORDERS,
        default=unpaid.AMOUNT,
        help_text="Montant décroissant (la devise choisie, sinon les dollars puis les francs, "
        "jamais additionnés), retard décroissant, nom ou classe.",
    )

    def filters(self) -> unpaid.Filters:
        data = self.validated_data
        return unpaid.Filters(
            academic_year=data.get("academic_year") or organisation.current_year(),
            class_group=data.get("class_group"),
            fee_type=data.get("fee_type"),
            installment=data.get("installment", ""),
            over_days=data["over_days"],
            currency=data.get("currency", ""),
            order=data["order"],
        )


class UnpaidExportSerializer(UnpaidFilterSerializer):
    output = serializers.ChoiceField(
        choices=["xlsx", "pdf", "html"],
        help_text="Excel (une ligne par frais en retard), PDF, ou aperçu HTML du PDF.",
    )
    group = serializers.ChoiceField(
        choices=["class", "list"], default="class", help_text="PDF : par classe ou liste unique."
    )
    page_per_class = serializers.BooleanField(default=True, help_text="PDF : une page par classe.")
    phone = serializers.BooleanField(default=True, help_text="PDF : téléphone du tuteur.")
    detail = serializers.BooleanField(default=False, help_text="PDF : une ligne par tranche.")


class UnpaidAmountSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    overdue_minor = serializers.IntegerField()


class UnpaidChargeSerializer(serializers.Serializer):
    fee_type_name = serializers.CharField(source="fee_type.name")
    label = serializers.CharField()
    due_on = serializers.DateField()
    currency = serializers.ChoiceField(choices=Currency.choices)
    remaining_minor = serializers.IntegerField(help_text="Reste après réductions et paiements.")
    days_late = serializers.IntegerField()


class GuardianContactSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    phone = serializers.CharField()


class LastPaymentSerializer(serializers.Serializer):
    paid_at = serializers.DateTimeField()
    received_amount_minor = serializers.IntegerField()
    received_currency = serializers.ChoiceField(choices=Currency.choices)


class UnpaidStudentSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField(source="enrollment.pk")
    student = PaymentStudentSerializer(source="enrollment.student")
    class_group = serializers.CharField(source="enrollment.class_group.name")
    charges = UnpaidChargeSerializer(
        many=True, help_text="Frais en retard, les plus anciens d'abord."
    )
    amounts = UnpaidAmountSerializer(
        many=True, help_text="En retard, par devise (dollars d'abord)."
    )
    days_late = serializers.IntegerField(help_text="Retard du frais le plus ancien, en jours.")
    guardian = GuardianContactSerializer(allow_null=True, help_text="Tuteur principal.")
    last_payment = LastPaymentSerializer(allow_null=True, help_text="Dernier paiement non annulé.")


class OptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class UnpaidSummarySerializer(serializers.Serializer):
    students = serializers.IntegerField(help_text="Élèves en retard selon les filtres.")
    enrolled = serializers.IntegerField(help_text="Élèves inscrits (de la classe choisie).")
    amounts = UnpaidAmountSerializer(many=True)
    long_overdue = serializers.IntegerField(help_text="Élèves en retard de plus de 30 jours.")
    class_groups = OptionSerializer(many=True, help_text="Classes de l'année (filtre).")
    fee_types = OptionSerializer(many=True, help_text="Types des frais dus de l'année (filtre).")
    installments = serializers.ListField(
        child=serializers.CharField(), help_text="Tranches des frais dus, par échéance (filtre)."
    )

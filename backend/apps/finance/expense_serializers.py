from rest_framework import serializers

from apps.core.money import Currency
from apps.finance.models import CashOut, Expense, ExpenseCategory
from apps.finance.serializers import MAX_AMOUNT_MINOR


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "is_active"]


class ExpenseCategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "is_active"]


class ExpenseSettingsSerializer(serializers.Serializer):
    usd_threshold_minor = serializers.IntegerField(
        min_value=0, max_value=MAX_AMOUNT_MINOR, help_text="Au-dessus : validation (centimes)."
    )
    cdf_threshold_minor = serializers.IntegerField(
        min_value=0, max_value=MAX_AMOUNT_MINOR, help_text="Au-dessus : validation (francs)."
    )


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    decided_by_name = serializers.SerializerMethodField()
    has_voucher = serializers.SerializerMethodField()
    cancelled = serializers.SerializerMethodField()
    cancellation_reason = serializers.SerializerMethodField()
    cash_out_number = serializers.CharField(
        read_only=True, allow_null=True, help_text="Bon de sortie de caisse qui la paie (FIN.2)."
    )

    class Meta:
        model = Expense
        fields = [
            "id",
            "number",
            "category",
            "category_name",
            "beneficiary",
            "reason",
            "amount_minor",
            "currency",
            "spent_on",
            "account",
            "status",
            "has_voucher",
            "requested_by_name",
            "decided_by_name",
            "decided_at",
            "decision_note",
            "paid_at",
            "cancelled",
            "cancellation_reason",
            "cash_out_number",
            "created_at",
        ]

    def get_requested_by_name(self, obj) -> str:
        return obj.requested_by.get_full_name()

    def get_decided_by_name(self, obj) -> str | None:
        return obj.decided_by.get_full_name() if obj.decided_by_id else None

    def get_has_voucher(self, obj) -> bool:
        return bool(obj.voucher)

    def _cancellation(self, obj):
        return getattr(obj, "cancellation", None)

    def get_cancelled(self, obj) -> bool:
        return self._cancellation(obj) is not None

    def get_cancellation_reason(self, obj) -> str | None:
        cancellation = self._cancellation(obj)
        return cancellation.reason if cancellation else None


class ExpenseCreateSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, help_text="Identifiant UUID v7 du client.")
    category = serializers.UUIDField()
    beneficiary = serializers.CharField(max_length=120)
    reason = serializers.CharField(max_length=200)
    amount_minor = serializers.IntegerField(min_value=1, max_value=MAX_AMOUNT_MINOR)
    currency = serializers.ChoiceField(choices=Currency.choices)
    spent_on = serializers.DateField()
    account = serializers.ChoiceField(choices=Expense.Account.choices)
    voucher = serializers.FileField(required=False, allow_empty_file=False)


class ExpenseDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class ExpenseCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)


class ExpenseFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Expense.Status.choices, required=False)
    category = serializers.UUIDField(required=False)
    month = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$", required=False)


class CurrencyTotalSerializer(serializers.Serializer):
    currency = serializers.CharField()
    spent = serializers.IntegerField(allow_null=True)
    pending = serializers.IntegerField(allow_null=True)
    pending_count = serializers.IntegerField()
    cash = serializers.IntegerField(allow_null=True)


class CancelledTotalSerializer(serializers.Serializer):
    currency = serializers.CharField()
    total = serializers.IntegerField()
    count = serializers.IntegerField()


class ExpenseSummarySerializer(serializers.Serializer):
    by_currency = CurrencyTotalSerializer(many=True)
    cancelled = CancelledTotalSerializer(many=True)


# Sorties de caisse (FIN.2)


class PayableExpenseSerializer(serializers.ModelSerializer):
    """Dépense validée à payer en espèces, telle que la voit le caissier."""

    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "number",
            "category_name",
            "beneficiary",
            "reason",
            "amount_minor",
            "currency",
            "spent_on",
        ]


class CashOutSerializer(serializers.ModelSerializer):
    """Une sortie de caisse et ce qu'imprime son bon."""

    expense_number = serializers.CharField(source="expense.number", read_only=True)
    category_name = serializers.CharField(source="expense.category.name", read_only=True)
    beneficiary = serializers.CharField(source="expense.beneficiary", read_only=True)
    reason = serializers.CharField(source="expense.reason", read_only=True)
    cash_register_code = serializers.CharField(
        source="cash_session.cash_register.code", read_only=True
    )
    cash_register_name = serializers.CharField(
        source="cash_session.cash_register.name", read_only=True
    )
    cashier_name = serializers.SerializerMethodField()
    offline = serializers.SerializerMethodField()
    cancelled = serializers.SerializerMethodField()
    cancellation_reason = serializers.SerializerMethodField()

    class Meta:
        model = CashOut
        fields = [
            "id",
            "number",
            "expense",
            "expense_number",
            "category_name",
            "beneficiary",
            "reason",
            "amount_minor",
            "currency",
            "received_by",
            "paid_at",
            "cash_session",
            "cash_register_code",
            "cash_register_name",
            "cashier_name",
            "offline",
            "cancelled",
            "cancellation_reason",
        ]

    def get_cashier_name(self, obj) -> str:
        return obj.cash_session.cashier.get_full_name()

    def get_offline(self, obj) -> bool:
        return obj.device_id is not None

    def _cancellation(self, obj):
        return getattr(obj, "cancellation", None)

    def get_cancelled(self, obj) -> bool:
        return self._cancellation(obj) is not None

    def get_cancellation_reason(self, obj) -> str | None:
        cancellation = self._cancellation(obj)
        return cancellation.reason if cancellation else None


class CashOutCreateSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=False, help_text="UUID v7 de l'appareil : un deuxième envoi rend la même sortie."
    )
    expense = serializers.UUIDField(help_text="Dépense validée à payer en espèces.")
    received_by = serializers.CharField(
        max_length=120, help_text="Nom de la personne qui reçoit l'argent."
    )


class CashOutFilterSerializer(serializers.Serializer):
    cash_session = serializers.UUIDField(required=False)

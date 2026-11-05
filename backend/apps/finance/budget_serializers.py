from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.core.money import Currency
from apps.finance.models import Expense, ExpenseCategory, TreasuryMovement
from apps.finance.serializers import MAX_AMOUNT_MINOR
from apps.schools.models import AcademicYear


class BudgetQuerySerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects, required=False, help_text="Absent : l'année en cours."
    )
    currency = serializers.ChoiceField(
        choices=Currency.choices, required=False, help_text="Absent : la première de l'école."
    )


class BudgetRowSerializer(serializers.Serializer):
    category = serializers.UUIDField()
    name = serializers.CharField()
    is_active = serializers.BooleanField()
    planned_minor = serializers.IntegerField()
    spent_minor = serializers.IntegerField()


class MonthFlowSerializer(serializers.Serializer):
    month = serializers.DateField(help_text="Premier jour du mois.")
    receipts_minor = serializers.IntegerField()
    expenses_minor = serializers.IntegerField()
    balance_minor = serializers.IntegerField()


class AccountBalanceSerializer(serializers.Serializer):
    account = serializers.ChoiceField(choices=Expense.Account.choices)
    currency = serializers.ChoiceField(choices=Currency.choices)
    opening_minor = serializers.IntegerField()
    receipts_minor = serializers.IntegerField(help_text="Reçu à la caisse (compte « caisse »).")
    transfers_in_minor = serializers.IntegerField()
    transfers_out_minor = serializers.IntegerField()
    expenses_minor = serializers.IntegerField()
    balance_minor = serializers.IntegerField()


class BudgetReportSerializer(serializers.Serializer):
    academic_year = serializers.UUIDField()
    currency = serializers.ChoiceField(choices=Currency.choices)
    currencies = serializers.ListField(child=serializers.ChoiceField(choices=Currency.choices))
    budget = BudgetRowSerializer(many=True)
    planned_minor = serializers.IntegerField()
    spent_minor = serializers.IntegerField()
    months = MonthFlowSerializer(many=True)
    accounts = AccountBalanceSerializer(many=True)


class BudgetAmountSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(queryset=ExpenseCategory.objects)
    amount_minor = serializers.IntegerField(min_value=0, max_value=MAX_AMOUNT_MINOR)


class BudgetWriteSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(queryset=AcademicYear.objects)
    currency = serializers.ChoiceField(choices=Currency.choices)
    lines = BudgetAmountSerializer(many=True, allow_empty=False, max_length=200)

    def validate_lines(self, lines: list[dict]) -> list[dict]:
        if len({line["category"].pk for line in lines}) != len(lines):
            raise serializers.ValidationError(_("Each category once."), code="unique_categories")
        return lines


class TreasuryMovementSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source="recorded_by", read_only=True)
    cancelled = serializers.SerializerMethodField()
    cancel_reason = serializers.SerializerMethodField()

    class Meta:
        model = TreasuryMovement
        fields = [
            "id",
            "academic_year",
            "kind",
            "from_account",
            "to_account",
            "amount_minor",
            "currency",
            "made_on",
            "note",
            "recorded_by_name",
            "created_at",
            "cancelled",
            "cancel_reason",
        ]

    def _cancellation(self, movement):
        try:
            return movement.cancellation
        except TreasuryMovement.cancellation.RelatedObjectDoesNotExist:
            return None

    def get_cancelled(self, movement) -> bool:
        return self._cancellation(movement) is not None

    def get_cancel_reason(self, movement) -> str:
        cancellation = self._cancellation(movement)
        return cancellation.reason if cancellation else ""


class TreasuryMovementCreateSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects, required=False, help_text="Absent : l'année en cours."
    )
    kind = serializers.ChoiceField(choices=TreasuryMovement.Kind.choices)
    from_account = serializers.ChoiceField(
        choices=Expense.Account.choices, required=False, help_text="Virement seulement."
    )
    to_account = serializers.ChoiceField(choices=Expense.Account.choices)
    amount_minor = serializers.IntegerField(min_value=1, max_value=MAX_AMOUNT_MINOR)
    currency = serializers.ChoiceField(choices=Currency.choices)
    made_on = serializers.DateField()
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, data: dict) -> dict:
        if data["kind"] == TreasuryMovement.Kind.TRANSFER:
            source = data.get("from_account")
            if not source:
                raise serializers.ValidationError(
                    {"from_account": _("Choose the account the money leaves.")}
                )
            if source == data["to_account"]:
                raise serializers.ValidationError(
                    {"to_account": _("A transfer goes to another account.")}
                )
        else:
            data.pop("from_account", None)
        return data


class TreasuryMovementFilterSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects, required=False, help_text="Absent : l'année en cours."
    )

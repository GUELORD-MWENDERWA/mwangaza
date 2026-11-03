from rest_framework import serializers

from apps.billing.models import (
    Contract,
    Invoice,
    InvoiceLine,
    InvoicePayment,
    LegalDocument,
    ModuleRequest,
    Plan,
)


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id", "code", "name", "description", "modules", "price_per_student", "currency",
            "period", "ai_uses", "ai_monthly_credits", "active",
        ]  # fmt: skip
        read_only_fields = ["id"]


class ContractSerializer(serializers.ModelSerializer):
    school = serializers.SlugRelatedField(slug_field="code", read_only=True)
    plan = serializers.SlugRelatedField(slug_field="code", read_only=True)
    replaces = serializers.SlugRelatedField(slug_field="number", read_only=True)
    signed_file = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "id", "number", "status", "school", "plan", "replaces", "start_date", "end_date",
            "modules", "price_per_student", "currency", "period", "trial_days", "auto_renew",
            "signature", "signed_at", "signer_name", "signed_file",
        ]  # fmt: skip
        read_only_fields = fields

    def get_signed_file(self, contract) -> bool:
        return bool(contract.signed_file)


class ContractCreateSerializer(serializers.Serializer):
    school = serializers.SlugField()
    plan = serializers.SlugField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    price_per_student = serializers.IntegerField(min_value=0, required=False)
    trial_days = serializers.IntegerField(min_value=0, max_value=365, required=False)
    auto_renew = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if attrs["end_date"] <= attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "end_before_start"})
        return attrs


class ContractSignSerializer(serializers.Serializer):
    signature = serializers.ChoiceField(choices=Contract.Signature.choices)
    signer_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    signed_file = serializers.FileField(required=False)


class LegalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalDocument
        fields = [
            "id", "kind", "version", "published_at", "title_fr", "title_en", "body_fr", "body_en",
        ]  # fmt: skip
        read_only_fields = ["id", "version", "published_at"]


class LegalAcceptSerializer(serializers.Serializer):
    document = serializers.UUIDField()


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["description", "quantity", "unit_amount", "amount"]
        read_only_fields = fields


class InvoicePaymentSerializer(serializers.ModelSerializer):
    invoice = serializers.SlugRelatedField(slug_field="number", read_only=True)
    reverses = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = InvoicePayment
        fields = [
            "id", "invoice", "amount", "method", "reference", "paid_on", "reverses", "reason",
        ]  # fmt: skip
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    school = serializers.SlugRelatedField(slug_field="code", read_only=True)
    contract = serializers.SlugRelatedField(slug_field="number", read_only=True)
    credit_for = serializers.SlugRelatedField(slug_field="number", read_only=True)
    cancelled = serializers.SerializerMethodField()
    paid = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = InvoicePaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "number", "kind", "school", "contract", "credit_for", "issued_on", "due_on",
            "period_start", "period_end", "currency", "total", "cancelled", "paid", "balance",
            "lines", "payments",
        ]  # fmt: skip
        read_only_fields = fields

    def get_cancelled(self, invoice) -> bool:
        return hasattr(invoice, "credit_note")

    def get_paid(self, invoice) -> int:
        return getattr(invoice, "paid", 0) or 0

    def get_balance(self, invoice) -> int:
        from apps.billing import invoicing

        return invoicing.balance(invoice)


class InvoiceLineInput(serializers.Serializer):
    description = serializers.CharField(max_length=200)
    quantity = serializers.IntegerField(min_value=1)
    unit_amount = serializers.IntegerField(min_value=1)


class InvoiceCreateSerializer(serializers.Serializer):
    contract = serializers.CharField(max_length=20)
    students = serializers.IntegerField(min_value=0, required=False)
    lines = InvoiceLineInput(many=True, required=False)
    issued_on = serializers.DateField(required=False)
    period_start = serializers.DateField(required=False)
    period_end = serializers.DateField(required=False)


class InvoiceReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)


class InvoicePaymentCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    method = serializers.ChoiceField(choices=InvoicePayment.Method.choices)
    paid_on = serializers.DateField()
    reference = serializers.CharField(max_length=80, required=False, allow_blank=True)


class ModuleRequestCreateSerializer(serializers.Serializer):
    module = serializers.CharField(max_length=20)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class ModuleRequestSerializer(serializers.ModelSerializer):
    school = serializers.SlugRelatedField(slug_field="code", read_only=True)

    class Meta:
        model = ModuleRequest
        fields = ["id", "school", "module", "note", "status", "created_at"]
        read_only_fields = fields


class SubscriptionAmountSerializer(serializers.Serializer):
    currency = serializers.CharField()
    amount = serializers.IntegerField()


class SubscriptionDueSerializer(serializers.Serializer):
    number = serializers.CharField()
    due_on = serializers.DateField()
    currency = serializers.CharField()
    amount = serializers.IntegerField()


class SubscriptionSerializer(serializers.Serializer):
    """« Mon abonnement » : le contrat en vigueur (ou rien) et l'état des paiements."""

    contract = ContractSerializer(allow_null=True)
    plan_name = serializers.CharField()
    balance = SubscriptionAmountSerializer(many=True)
    next_due = SubscriptionDueSerializer(allow_null=True)
    late = serializers.BooleanField()
    read_only = serializers.BooleanField()
    payment_details = serializers.CharField(allow_blank=True)
    open_requests = serializers.ListField(child=serializers.CharField())

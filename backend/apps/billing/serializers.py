from rest_framework import serializers

from apps.billing.models import Contract, LegalDocument, Plan


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

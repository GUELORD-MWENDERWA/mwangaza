"""Serializers de la console de l'IA et des « Crédits IA » de la Gestion (IA.1.2). Montants en
micro-dollars entiers, crédits en entiers."""

from rest_framework import serializers

from apps.ai.models import AiCall


class AiUseRowSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    module = serializers.CharField()
    module_label = serializers.CharField()
    model = serializers.CharField()
    max_input_tokens = serializers.IntegerField()
    max_output_tokens = serializers.IntegerField()
    changed = serializers.BooleanField()
    calls = serializers.IntegerField()
    kept_percent = serializers.IntegerField(allow_null=True)
    abandoned = serializers.IntegerField()
    cost_micro = serializers.IntegerField()


class AiSchoolRowSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    uses = serializers.IntegerField()
    paused = serializers.BooleanField()
    granted_credits = serializers.IntegerField()
    spent_credits = serializers.IntegerField()
    remaining_credits = serializers.IntegerField()
    calls = serializers.IntegerField()
    kept_percent = serializers.IntegerField(allow_null=True)


class AiAlertSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["platform_cap", "school_credits"])
    percent = serializers.IntegerField()
    id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)


class AiPriceSerializer(serializers.Serializer):
    model = serializers.CharField()
    input = serializers.IntegerField(min_value=0)
    output = serializers.IntegerField(min_value=0)
    cache_read = serializers.IntegerField(min_value=0)
    changed = serializers.BooleanField(read_only=True)


class AiSettingsSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    monthly_cap_micro = serializers.IntegerField(min_value=0, max_value=10**12)
    hourly_limit = serializers.IntegerField(min_value=1, max_value=500)
    prices = AiPriceSerializer(many=True, read_only=True)


class AiSettingsChangeSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    monthly_cap_micro = serializers.IntegerField(min_value=0, max_value=10**12, required=False)
    hourly_limit = serializers.IntegerField(min_value=1, max_value=500, required=False)


class AiOverviewSerializer(serializers.Serializer):
    month = serializers.DateField()
    live = serializers.BooleanField()
    spent_micro = serializers.IntegerField()
    cap_micro = serializers.IntegerField(allow_null=True)
    calls = serializers.IntegerField()
    refused = serializers.IntegerField()
    errors = serializers.IntegerField()
    kept_percent = serializers.IntegerField(allow_null=True)
    schools_with_ai = serializers.IntegerField()
    schools_paused = serializers.IntegerField()
    alerts = AiAlertSerializer(many=True)
    schools = AiSchoolRowSerializer(many=True)
    uses = AiUseRowSerializer(many=True)
    settings = AiSettingsSerializer(allow_null=True)


class AiUseChangeSerializer(serializers.Serializer):
    """Tout absent : retour au réglage du catalogue."""

    model = serializers.CharField(required=False, allow_null=True, max_length=60)
    max_input_tokens = serializers.IntegerField(required=False, allow_null=True)
    max_output_tokens = serializers.IntegerField(required=False, allow_null=True)


class AiPriceChangeSerializer(serializers.Serializer):
    input = serializers.IntegerField(min_value=0, max_value=10**9)
    output = serializers.IntegerField(min_value=0, max_value=10**9)
    cache_read = serializers.IntegerField(min_value=0, max_value=10**9)


class AiSchoolUseSerializer(AiUseRowSerializer):
    granted = serializers.BooleanField()
    available = serializers.BooleanField()


class AiLastCallSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    use = serializers.CharField()
    use_label = serializers.CharField()
    user = serializers.CharField()
    state = serializers.ChoiceField(choices=AiCall.State.choices)
    refusal = serializers.CharField()
    credits = serializers.IntegerField()
    on_platform = serializers.BooleanField()


class AiSchoolCardSerializer(serializers.Serializer):
    month = serializers.DateField()
    has_module = serializers.BooleanField()
    uses = AiSchoolUseSerializer(many=True)
    monthly_credits = serializers.IntegerField()
    paused = serializers.BooleanField()
    granted_credits = serializers.IntegerField()
    spent_credits = serializers.IntegerField()
    remaining_credits = serializers.IntegerField()
    last_calls = AiLastCallSerializer(many=True)


class AiAllowanceChangeSerializer(serializers.Serializer):
    uses = serializers.ListField(child=serializers.CharField(max_length=40), max_length=50)
    monthly_credits = serializers.IntegerField(min_value=0, max_value=10_000_000)
    paused = serializers.BooleanField()


class AiTopUpSerializer(serializers.Serializer):
    credits = serializers.IntegerField(min_value=1, max_value=10_000_000)


class AiCreditUseSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    blocked = serializers.CharField()


class AiCreditsSerializer(serializers.Serializer):
    month = serializers.DateField()
    has_module = serializers.BooleanField()
    granted_credits = serializers.IntegerField()
    spent_credits = serializers.IntegerField()
    remaining_credits = serializers.IntegerField()
    blocked = serializers.CharField()
    uses = AiCreditUseSerializer(many=True)

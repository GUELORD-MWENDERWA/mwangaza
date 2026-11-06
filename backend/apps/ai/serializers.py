"""Serializers de la console de l'IA et des « Crédits IA » de la Gestion (IA.1.2). Montants en
micro-dollars entiers, crédits en entiers."""

from rest_framework import serializers

from apps.ai import drafting
from apps.ai.models import AiCall


class AiUseRowSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    module = serializers.CharField()
    module_label = serializers.CharField()
    model = serializers.CharField()
    max_input_tokens = serializers.IntegerField()
    max_output_tokens = serializers.IntegerField()
    daily_limit = serializers.IntegerField(
        allow_null=True, help_text="Demandes par personne et par jour ; vide : sans limite."
    )
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
    daily_limit = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=500
    )


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


# IA dans l'école (IA.3, IA.4, IA.5) : demande, puis état de l'appel et sa réponse.


class _CallSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    state = serializers.CharField(
        help_text="queued, running, done, error, refused, kept, abandoned."
    )
    refusal = serializers.CharField(allow_blank=True, help_text="Code du refus ou de l'erreur.")


class CourseGridAskSerializer(serializers.Serializer):
    request_id = serializers.UUIDField(help_text="Fabriqué par l'écran : un clic, un appel.")
    file = serializers.FileField(help_text="PDF (3 pages au plus) ou photo JPEG / PNG.")


class GridCourseSerializer(serializers.Serializer):
    name = serializers.CharField()
    domain = serializers.CharField(allow_blank=True)
    period_max = serializers.IntegerField()
    has_exam = serializers.BooleanField()
    category = serializers.CharField()
    doubtful = serializers.BooleanField(help_text="Peu lisible : à vérifier.")


class SkippedSerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True)
    reason = serializers.CharField(allow_blank=True)


class GridProposalSerializer(serializers.Serializer):
    courses = GridCourseSerializer(many=True)
    skipped = SkippedSerializer(many=True)


class CourseGridCallSerializer(_CallSerializer):
    proposal = GridProposalSerializer(allow_null=True)


class DraftAskSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=drafting.KINDS)
    tone = serializers.ChoiceField(choices=["formal", "simple"], default="formal")
    brief = serializers.CharField(max_length=600, trim_whitespace=True)


class AiDraftSerializer(serializers.Serializer):
    title = serializers.CharField(allow_blank=True)
    body = serializers.CharField(allow_blank=True)


class DraftCallSerializer(_CallSerializer):
    draft = AiDraftSerializer(allow_null=True)


class KeepSerializer(serializers.Serializer):
    kept = serializers.BooleanField(help_text="Vrai : mis dans l'écran ; faux : laissé.")


class QuestionAskSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    question = serializers.CharField(max_length=300, trim_whitespace=True)
    history = serializers.ListField(
        child=serializers.CharField(max_length=300),
        max_length=3,
        required=False,
        help_text="Les questions d'avant de la conversation (gardée dans le navigateur).",
    )


class AmountSerializer(serializers.Serializer):
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()


class LoadRowSerializer(serializers.Serializer):
    name = serializers.CharField()
    hours = serializers.IntegerField()
    courses = serializers.IntegerField()


class FiguresSerializer(serializers.Serializer):
    """Chiffres calculés par l'application ; seuls ceux de la requête sont présents."""

    class_group = serializers.CharField(allow_null=True, required=False)
    period = serializers.CharField(required=False)
    count = serializers.IntegerField(required=False)
    girls = serializers.IntegerField(required=False)
    boys = serializers.IntegerField(required=False)
    amounts = AmountSerializer(many=True, required=False)
    rows = LoadRowSerializer(many=True, required=False)
    link = serializers.CharField(help_text="Écran d'où vient la réponse.")


class AnswerSerializer(serializers.Serializer):
    intent = serializers.ChoiceField(
        choices=["unpaid", "collected", "headcount", "teacher_load", "unknown"]
    )
    status = serializers.ChoiceField(
        choices=["answered", "not_understood", "forbidden", "not_available"]
    )
    figures = FiguresSerializer(required=False)


class QuestionCallSerializer(_CallSerializer):
    answer = AnswerSerializer(allow_null=True)

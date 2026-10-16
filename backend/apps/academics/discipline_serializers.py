from rest_framework import serializers

from apps.academics import discipline
from apps.academics.models import (
    MAX_RULE_POINTS,
    ConductScale,
    DisciplineIncident,
    DisciplineRule,
)
from apps.schools.models import Term
from apps.students.models import Enrollment


class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisciplineRule
        fields = ["id", "label", "points", "is_active"]
        read_only_fields = ["id"]


class RuleCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=120)
    points = serializers.IntegerField(min_value=1, max_value=MAX_RULE_POINTS)


class RuleUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=120, required=False)
    points = serializers.IntegerField(min_value=1, max_value=MAX_RULE_POINTS, required=False)
    is_active = serializers.BooleanField(required=False)


class ScaleRowSerializer(serializers.Serializer):
    grade = serializers.ChoiceField(choices=discipline.GRADES)
    min_points = serializers.IntegerField(min_value=0, max_value=1000)


class ScaleSerializer(serializers.Serializer):
    scale = ScaleRowSerializer(many=True)

    def validate_scale(self, rows):
        if sorted(row["grade"] for row in rows) != sorted(discipline.GRADES):
            raise serializers.ValidationError("Les cinq cotes, une fois chacune.")
        return rows

    def minimums(self) -> dict[str, int]:
        return {row["grade"]: row["min_points"] for row in self.validated_data["scale"]}


class PickClassSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class PickStudentSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField(
        help_text="Inscription de l'élève (à envoyer avec l'incident)."
    )
    full_name = serializers.CharField()
    matricule = serializers.CharField(allow_blank=True)


class IncidentCreateSerializer(serializers.Serializer):
    enrollment = serializers.PrimaryKeyRelatedField(queryset=Enrollment.objects)
    rule = serializers.PrimaryKeyRelatedField(queryset=DisciplineRule.objects)
    occurred_on = serializers.DateField()
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    term = serializers.PrimaryKeyRelatedField(
        queryset=Term.objects,
        required=False,
        allow_null=True,
        help_text="Période ; sinon celle qui contient la date.",
    )


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class IncidentSerializer(serializers.ModelSerializer):
    offence = serializers.CharField(source="rule.label")
    term_name = serializers.CharField(source="term.__str__")
    recorded_by_name = serializers.SerializerMethodField()
    cancelled = serializers.SerializerMethodField()
    cancel_reason = serializers.SerializerMethodField()

    class Meta:
        model = DisciplineIncident
        fields = [
            "id",
            "offence",
            "points",
            "occurred_on",
            "term",
            "term_name",
            "note",
            "recorded_by_name",
            "cancelled",
            "cancel_reason",
        ]
        read_only_fields = fields

    def get_recorded_by_name(self, incident) -> str:
        return incident.recorded_by.get_full_name()

    def get_cancelled(self, incident) -> bool:
        return hasattr(incident, "cancellation")

    def get_cancel_reason(self, incident) -> str:
        return incident.cancellation.reason if hasattr(incident, "cancellation") else ""


class TermConductSerializer(serializers.Serializer):
    term = serializers.UUIDField(source="term.pk")
    term_name = serializers.CharField(source="label")
    points = serializers.IntegerField(help_text="Points des incidents non annulés.")
    calculated = serializers.CharField(
        help_text="Cote d'après les points et les seuils de l'école."
    )
    grade = serializers.CharField(help_text="Cote retenue : la correction si elle existe.")
    override_reason = serializers.SerializerMethodField()
    override_by = serializers.SerializerMethodField()

    def get_override_reason(self, conduct) -> str:
        return conduct.override.reason if conduct.override else ""

    def get_override_by(self, conduct) -> str:
        return conduct.override.overridden_by.get_full_name() if conduct.override else ""


class OverrideSerializer(serializers.Serializer):
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects)
    grade = serializers.ChoiceField(choices=ConductScale.Grade.choices)
    reason = serializers.CharField(max_length=300)


class ClearOverrideSerializer(serializers.Serializer):
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects)


class StudentIncidentsSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    class_name = serializers.CharField()
    incidents = IncidentSerializer(many=True)
    totals = TermConductSerializer(many=True)

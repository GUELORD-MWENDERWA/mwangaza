from rest_framework import serializers

from apps.timetable.models import ExamSchedule, ExamSitting


class ExamSittingSerializer(serializers.ModelSerializer):
    """Une épreuve ; la classe et le cours viennent du cours choisi."""

    class_group = serializers.UUIDField(source="course.class_group_id", read_only=True)
    class_name = serializers.CharField(source="course.class_group", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True, default=None)

    class Meta:
        model = ExamSitting
        fields = [
            "id",
            "course",
            "course_name",
            "class_group",
            "class_name",
            "kind",
            "date",
            "start",
            "end",
            "room",
            "room_name",
            "invigilator",
        ]


class ExamSittingWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSitting
        fields = ["course", "kind", "date", "start", "end", "room", "invigilator"]
        extra_kwargs = {"course": {"required": True}}

    def validate(self, attrs):
        start = attrs.get("start", getattr(self.instance, "start", None))
        end = attrs.get("end", getattr(self.instance, "end", None))
        if start and end and start >= end:
            raise serializers.ValidationError({"end": "L'épreuve finit après son début."})
        return attrs


class ExamIssueSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=["error", "warning"])
    code = serializers.CharField(help_text="Le contrôle (`class_overlap`, `outside_term`…).")
    sittings = serializers.ListField(child=serializers.UUIDField())
    values = serializers.DictField()


class ExamScheduleSerializer(serializers.Serializer):
    """Horaire d'une période : état, épreuves et contrôles. Sans geste encore, `status` est
    `draft` et `published_at` vide."""

    term = serializers.UUIDField(source="term.pk")
    status = serializers.ChoiceField(choices=ExamSchedule.Status.choices, source="schedule_status")
    published_at = serializers.DateTimeField(allow_null=True)
    published_by = serializers.CharField(allow_null=True)
    sittings = ExamSittingSerializer(many=True)
    errors = serializers.IntegerField(help_text="Conflits : bloquent la publication.")
    warnings = serializers.IntegerField()
    issues = ExamIssueSerializer(many=True)

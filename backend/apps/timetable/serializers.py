from rest_framework import serializers

from apps.timetable.checks import LEVELS
from apps.timetable.constraints import UnavailableSerializer, clean
from apps.timetable.models import (
    MAX_LESSON_MINUTES,
    MAX_LESSONS_PER_DAY,
    MAX_TEACHER_WEEK_HOURS,
    MAX_UNAVAILABLE,
    MIN_LESSON_MINUTES,
    Room,
    TimeGrid,
    TimeSlot,
    TimetableRule,
)

# 7 jours de 12 heures et 11 récréations au plus.
MAX_SLOTS = 7 * (2 * MAX_LESSONS_PER_DAY - 1)


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ["id", "weekday", "index", "kind", "start", "end"]


class TimeGridSerializer(serializers.ModelSerializer):
    slots = TimeSlotSerializer(many=True, read_only=True)
    lesson_count = serializers.IntegerField(help_text="Heures de cours par semaine (places).")
    class_count = serializers.IntegerField(help_text="Classes de l'année en cours qui la suivent.")

    class Meta:
        model = TimeGrid
        fields = [
            "id",
            "name",
            "lesson_minutes",
            "start_time",
            "is_default",
            "lesson_count",
            "class_count",
            "slots",
        ]


class TimeSlotInputSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=1, max_value=7)
    index = serializers.IntegerField(
        min_value=1,
        max_value=MAX_LESSONS_PER_DAY,
        allow_null=True,
        required=False,
        help_text="Numéro de l'heure dans le jour ; vide pour une récréation.",
    )
    kind = serializers.ChoiceField(choices=TimeSlot.Kind.choices)
    start = serializers.TimeField()
    end = serializers.TimeField()

    def validate(self, attrs: dict) -> dict:
        if attrs["kind"] == TimeSlot.Kind.BREAK:
            attrs["index"] = None
        elif attrs.get("index") is None:
            raise serializers.ValidationError({"index": "Une heure de cours a son numéro."})
        return attrs


class TimeGridWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    lesson_minutes = serializers.IntegerField(
        min_value=MIN_LESSON_MINUTES, max_value=MAX_LESSON_MINUTES
    )
    start_time = serializers.TimeField()
    is_default = serializers.BooleanField(default=False)
    slots = TimeSlotInputSerializer(many=True, max_length=MAX_SLOTS)


class TimeGridCreateSerializer(TimeGridWriteSerializer):
    # Sans valeur : celles de la grille proposée (`services.PRESET_*`, question Q16), posées par
    # la vue.
    lesson_minutes = serializers.IntegerField(
        min_value=MIN_LESSON_MINUTES, max_value=MAX_LESSON_MINUTES, required=False
    )
    start_time = serializers.TimeField(required=False)
    is_default = serializers.BooleanField(required=False)
    slots = TimeSlotInputSerializer(
        many=True,
        max_length=MAX_SLOTS,
        required=False,
        help_text="Sans cases : la semaine proposée, calculée avec cette durée et ce début.",
    )


class TimetableClassSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    time_grid = serializers.UUIDField(allow_null=True, help_text="Vide : grille par défaut.")
    home_room = serializers.UUIDField(allow_null=True)
    course_hours = serializers.IntegerField(help_text="Heures par semaine des cours enseignés.")
    missing_hours = serializers.IntegerField(help_text="Cours enseignés sans heures saisies.")
    capacity = serializers.IntegerField(
        allow_null=True, help_text="Heures de cours de sa grille ; vide sans grille."
    )


class TimetableClassUpdateSerializer(serializers.Serializer):
    time_grid = serializers.UUIDField(allow_null=True, required=False)
    home_room = serializers.UUIDField(allow_null=True, required=False)


class RoomSerializer(serializers.ModelSerializer):
    classes = serializers.SerializerMethodField(
        help_text="Classes de l'année en cours qui y ont leur salle habituelle."
    )

    class Meta:
        model = Room
        fields = ["id", "name", "kind", "capacity", "is_active", "classes"]

    def get_classes(self, room: Room) -> list[str]:
        return [group.name for group in room.current_classes]


class RoomCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    kind = serializers.ChoiceField(choices=Room.Kind.choices)
    capacity = serializers.IntegerField(min_value=1, max_value=500, allow_null=True, required=False)


class RoomUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False)
    kind = serializers.ChoiceField(choices=Room.Kind.choices, required=False)
    capacity = serializers.IntegerField(min_value=1, max_value=500, allow_null=True, required=False)
    is_active = serializers.BooleanField(required=False)


class TimetableRulesSerializer(serializers.Serializer):
    max_same_course_per_day = serializers.IntegerField(min_value=1, max_value=6)
    teacher_max_day_hours = serializers.IntegerField(min_value=1, max_value=MAX_LESSONS_PER_DAY)
    no_gaps = serializers.BooleanField()
    main_courses_early = serializers.BooleanField()


class TeacherProfileSerializer(serializers.Serializer):
    teacher = serializers.UUIDField(source="teacher_id", read_only=True)
    max_week_hours = serializers.IntegerField(
        min_value=1,
        max_value=MAX_TEACHER_WEEK_HOURS,
        allow_null=True,
        help_text="Charge au plus par semaine (contrat) ; vide : pas de limite.",
    )
    max_day_hours = serializers.IntegerField(
        min_value=1,
        max_value=MAX_LESSONS_PER_DAY,
        allow_null=True,
        help_text="Vide : règle de l'école.",
    )
    unavailable = UnavailableSerializer(many=True, max_length=MAX_UNAVAILABLE)


class CheckIssueSerializer(serializers.Serializer):
    check = serializers.IntegerField(
        help_text=(
            "1 classes, 2 enseignants, 3 cours, 4 salles, 5 cours incomplets, 6 verrous en "
            "conflit, 7 règles qui se contredisent ou sans objet."
        )
    )
    code = serializers.CharField(help_text="Ex. class_overloaded, teacher_over_max.")
    level = serializers.ChoiceField(choices=LEVELS, help_text="error : rouge ; warning : orange.")
    subject = serializers.CharField(
        help_text="Classe, enseignant, cours, salle, ou type de salle (code)."
    )
    values = serializers.DictField(help_text="Chiffres et noms de la phrase.")
    class_group = serializers.UUIDField(allow_null=True)
    teacher = serializers.UUIDField(allow_null=True)
    room = serializers.UUIDField(allow_null=True)
    rule = serializers.UUIDField(allow_null=True, help_text="La règle à modifier (contrôles 6, 7).")


class ChecksSerializer(serializers.Serializer):
    errors = serializers.IntegerField()
    warnings = serializers.IntegerField()
    classes = serializers.IntegerField()
    teachers = serializers.IntegerField()
    rooms = serializers.IntegerField()
    rules = serializers.IntegerField(help_text="Règles actives.")
    issues = CheckIssueSerializer(many=True)


class TimetableRuleSerializer(serializers.ModelSerializer):
    params = serializers.DictField(help_text="Paramètres, selon le kind (spec § 5).")

    class Meta:
        model = TimetableRule
        fields = [
            "id",
            "kind",
            "params",
            "strength",
            "weight",
            "active",
            "source",
            "text",
            "updated_at",
        ]


class TimetableRuleWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TimetableRule.Kind.choices)
    params = serializers.DictField(help_text="Vérifiés par le schéma du kind.")
    strength = serializers.ChoiceField(
        choices=TimetableRule.Strength.choices, required=False, help_text="Vide : celle du kind."
    )
    weight = serializers.IntegerField(
        min_value=1, max_value=10, required=False, help_text="Souhait : 1 à 10 ; vide : du kind."
    )
    active = serializers.BooleanField(default=True)

    def validate(self, attrs: dict) -> dict:
        return clean(attrs)


class RuleKindSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TimetableRule.Kind.choices)
    strengths = serializers.ListField(
        child=serializers.ChoiceField(choices=TimetableRule.Strength.choices)
    )
    strength = serializers.ChoiceField(choices=TimetableRule.Strength.choices)
    weight = serializers.IntegerField()


class RuleCourseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    category = serializers.CharField()
    class_group = serializers.UUIDField()
    class_name = serializers.CharField()
    teacher = serializers.UUIDField(allow_null=True)
    weekly_hours = serializers.IntegerField()
    sessions = serializers.ListField(child=serializers.IntegerField())


class RuleTeacherSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class RuleChoicesSerializer(serializers.Serializer):
    kinds = RuleKindSerializer(many=True)
    courses = RuleCourseSerializer(many=True)
    teachers = RuleTeacherSerializer(many=True)

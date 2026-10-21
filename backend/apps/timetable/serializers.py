from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.timetable.checks import LEVELS
from apps.timetable.models import (
    MAX_LESSON_MINUTES,
    MAX_LESSONS_PER_DAY,
    MAX_TEACHER_WEEK_HOURS,
    MAX_UNAVAILABLE,
    MIN_LESSON_MINUTES,
    Room,
    TimeGrid,
    TimeSlot,
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


class UnavailableSerializer(serializers.Serializer):
    """Une absence : un jour entier, ou une plage horaire de ce jour (début et fin)."""

    weekday = serializers.IntegerField(min_value=1, max_value=7, help_text="1 = lundi.")
    start = serializers.TimeField(required=False, format="%H:%M")
    end = serializers.TimeField(required=False, format="%H:%M")

    def validate(self, attrs: dict) -> dict:
        start, end = attrs.get("start"), attrs.get("end")
        if (start is None) != (end is None):
            raise serializers.ValidationError(
                _("Give both the start and the end, or neither for the whole day."),
                code="incomplete_range",
            )
        if start is not None and start >= end:
            raise serializers.ValidationError(_("The end comes after the start."), code="bad_range")
        row = {"weekday": attrs["weekday"]}
        if start is not None:
            row |= {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")}
        return row


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
        help_text="1 classes, 2 enseignants, 3 cours, 4 salles, 5 cours incomplets."
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


class ChecksSerializer(serializers.Serializer):
    errors = serializers.IntegerField()
    warnings = serializers.IntegerField()
    classes = serializers.IntegerField()
    teachers = serializers.IntegerField()
    rooms = serializers.IntegerField()
    issues = CheckIssueSerializer(many=True)

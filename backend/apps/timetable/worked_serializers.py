"""Heures prestées (EDT.6, `worked.py`) : entrées et sorties de l'API."""

from rest_framework import serializers

from apps.academics.models import Course
from apps.accounts.models import User
from apps.core.documents import PrintOptionsSerializer
from apps.timetable.models import LessonException


class MonthQuerySerializer(serializers.Serializer):
    month = serializers.DateField(
        input_formats=["%Y-%m"], help_text="Le mois, `AAAA-MM`.", required=True
    )


class SheetQuerySerializer(MonthQuerySerializer, PrintOptionsSerializer):
    teacher = serializers.UUIDField()
    output = serializers.ChoiceField(choices=["pdf", "html"], default="pdf")


class DayQuerySerializer(serializers.Serializer):
    date = serializers.DateField()
    teacher = serializers.UUIDField()


class ExceptionsQuerySerializer(MonthQuerySerializer):
    kind = serializers.ChoiceField(choices=LessonException.Kind.choices, required=False)


class WorkedLineSerializer(serializers.Serializer):
    teacher = serializers.UUIDField(source="teacher_id")
    name = serializers.CharField()
    planned = serializers.IntegerField(help_text="Heures prévues par l'horaire publié.")
    absent = serializers.IntegerField(help_text="Non données : absent, ou remplacé.")
    cancelled = serializers.IntegerField()
    replacements = serializers.IntegerField(help_text="Données à la place d'un autre.")
    extra = serializers.IntegerField(help_text="Heures en plus.")
    given = serializers.IntegerField(help_text="Prestées.")


class WorkedTotalsSerializer(serializers.Serializer):
    planned = serializers.IntegerField()
    missed = serializers.IntegerField()
    added = serializers.IntegerField()


class WorkedMonthSerializer(serializers.Serializer):
    month = serializers.DateField()
    school_days = serializers.IntegerField(help_text="Jours de cours du mois, jusqu'à aujourd'hui.")
    holidays = serializers.ListField(child=serializers.DateField(), help_text="Congés du mois.")
    totals = WorkedTotalsSerializer()
    teachers = WorkedLineSerializer(many=True)


class DayLessonSerializer(serializers.Serializer):
    entry = serializers.UUIDField(help_text="La séance à noter.")
    first = serializers.IntegerField()
    length = serializers.IntegerField()
    start = serializers.TimeField(allow_null=True, format="%H:%M")
    end = serializers.TimeField(allow_null=True, format="%H:%M")
    course = serializers.CharField()
    class_groups = serializers.ListField(child=serializers.CharField())
    recorded = serializers.CharField(allow_null=True, help_text="Exception déjà notée.")


def _name(user: User | None) -> str | None:
    return user.get_full_name() if user else None


class LessonExceptionSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    replacement_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LessonException
        fields = [
            "id",
            "date",
            "kind",
            "teacher",
            "teacher_name",
            "replacement",
            "replacement_name",
            "first",
            "hours",
            "label",
            "reason",
            "created_by_name",
            "created_at",
        ]

    def get_teacher_name(self, row: LessonException) -> str:
        return row.teacher.get_full_name()

    def get_replacement_name(self, row: LessonException) -> str | None:
        return _name(row.replacement)

    def get_created_by_name(self, row: LessonException) -> str | None:
        return _name(row.created_by)


class LessonExceptionWriteSerializer(serializers.Serializer):
    date = serializers.DateField()
    kind = serializers.ChoiceField(choices=LessonException.Kind.choices)
    teacher = serializers.PrimaryKeyRelatedField(queryset=User.objects)
    reason = serializers.CharField(max_length=200, trim_whitespace=True)
    entries = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        max_length=12,
        help_text="Heures de l'horaire (absence, remplacement, annulation).",
    )
    replacement = serializers.PrimaryKeyRelatedField(
        queryset=User.objects, required=False, allow_null=True
    )
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects, required=False, help_text="Heure en plus : le cours."
    )
    hours = serializers.IntegerField(
        min_value=1, max_value=8, required=False, help_text="Heure en plus : combien."
    )


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, trim_whitespace=True)

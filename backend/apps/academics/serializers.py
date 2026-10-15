from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.academics.courses import CourseInput
from apps.academics.grades import MAX_EVALUATIONS, EvaluationInput, GradeInput
from apps.academics.models import (
    MAX_PERIOD_MAX,
    MAX_WEEKLY_HOURS,
    SCORE_DECIMALS,
    SCORE_DIGITS,
    Course,
    Evaluation,
)
from apps.schools.models import AcademicYear, ClassGroup
from apps.schools.serializers import PersonSerializer, TermSerializer
from apps.students.models import Enrollment


class CourseSerializer(serializers.ModelSerializer):
    teacher = PersonSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Course
        fields = ["id", "name", "domain", "period_max", "has_exam", "weekly_hours", "teacher"]
        read_only_fields = fields


class CourseInputSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=False, allow_null=True, help_text="Cours de la classe à garder ; absent : nouveau."
    )
    name = serializers.CharField(max_length=100)
    domain = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    period_max = serializers.IntegerField(min_value=1, max_value=MAX_PERIOD_MAX)
    has_exam = serializers.BooleanField(default=True)
    weekly_hours = serializers.IntegerField(
        min_value=1, max_value=MAX_WEEKLY_HOURS, required=False, allow_null=True, default=None
    )
    teacher_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
        help_text="`id` du compte de l'enseignant : le personnel actif de l'école.",
    )


class CoursesUpdateSerializer(serializers.Serializer):
    """Toute la grille de la classe, dans l'ordre : ce qui n'y est plus est retiré."""

    courses = CourseInputSerializer(many=True, allow_empty=True)

    def items(self) -> list[CourseInput]:
        return [CourseInput(**row) for row in self.validated_data["courses"]]


class CoursesCopySerializer(serializers.Serializer):
    class_groups = serializers.PrimaryKeyRelatedField(
        queryset=ClassGroup.objects,
        many=True,
        allow_empty=False,
        help_text="Classes qui reçoivent la grille (et perdent leurs autres cours).",
    )


class CoursesCopiedSerializer(serializers.Serializer):
    copied = serializers.IntegerField(help_text="Classes qui ont reçu la grille.")


class OfficialCourseSerializer(serializers.Serializer):
    name = serializers.CharField()
    period_max = serializers.IntegerField()
    has_exam = serializers.BooleanField()
    weekly_hours = serializers.IntegerField(allow_null=True)


class OfficialGridSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="Nom traduit par l'interface.")
    reference = serializers.CharField(help_text="Référence du document officiel.")
    courses = serializers.SerializerMethodField()

    @extend_schema_field(OfficialCourseSerializer(many=True))
    def get_courses(self, grid) -> list[dict]:
        return OfficialCourseSerializer(
            [
                {"name": n, "period_max": m, "has_exam": e, "weekly_hours": h}
                for n, m, e, h in grid.courses
            ],
            many=True,
        ).data


class LoadCourseSerializer(serializers.ModelSerializer):
    class_group = serializers.UUIDField(source="class_group_id")
    class_name = serializers.CharField(source="class_group.name")

    class Meta:
        model = Course
        fields = ["id", "name", "class_group", "class_name", "weekly_hours"]


class TeachingLoadSerializer(serializers.Serializer):
    teacher = PersonSerializer()
    hours = serializers.IntegerField(help_text="Heures par semaine de ses cours de l'année.")
    courses = LoadCourseSerializer(many=True)


class TeachingLoadsSerializer(serializers.Serializer):
    loads = TeachingLoadSerializer(
        many=True, help_text="Tout le personnel actif, le plus chargé d'abord."
    )
    unassigned = LoadCourseSerializer(
        many=True, help_text="Les premiers cours sans enseignant (tous : classe par classe)."
    )
    unassigned_count = serializers.IntegerField(help_text="Tous les cours sans enseignant.")
    unassigned_hours = serializers.IntegerField(help_text="Leurs heures par semaine.")


class TeachingLoadsFilterSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects, required=False, help_text="Absent : l'année en cours."
    )


# Notes (8.2.1)


class GradingCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "name", "period_max", "has_exam"]
        read_only_fields = fields


class GradingClassSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField(help_text="« 3e Électricité A ».")
    courses = GradingCourseSerializer(many=True, help_text="Cours que le compte peut noter.")


class GradingSerializer(serializers.Serializer):
    academic_year = serializers.UUIDField(allow_null=True, help_text="Vide : aucune année.")
    terms = TermSerializer(
        many=True, help_text="Découpage de l'année : on note les périodes et les examens."
    )
    classes = GradingClassSerializer(many=True)


class GradingFilterSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects,
        required=False,
        help_text="Par défaut : l'année en cours.",
    )


class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = ["id", "name", "max_score"]
        read_only_fields = fields


class ScoreSerializer(serializers.Serializer):
    evaluation_id = serializers.UUIDField()
    score = serializers.DecimalField(max_digits=SCORE_DIGITS, decimal_places=SCORE_DECIMALS)


class SheetRowSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField(source="enrollment.pk")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    matricule = serializers.CharField(source="enrollment.student.matricule")
    status = serializers.ChoiceField(
        source="enrollment.status",
        choices=Enrollment.Status.choices,
        help_text="Un élève parti n'apparaît que s'il a déjà une note ici.",
    )
    scores = serializers.SerializerMethodField(help_text="Cases remplies seulement.")
    total = serializers.DecimalField(
        max_digits=SCORE_DIGITS + 2,
        decimal_places=SCORE_DECIMALS,
        allow_null=True,
        help_text="Note de la période (somme ramenée au maximum) ; vide tant qu'une case manque.",
    )

    @extend_schema_field(ScoreSerializer(many=True))
    def get_scores(self, row) -> list[dict]:
        return ScoreSerializer(
            [{"evaluation_id": pk, "score": score} for pk, score in row.scores.items()], many=True
        ).data


class SheetSerializer(serializers.Serializer):
    course = GradingCourseSerializer()
    class_group = serializers.CharField(source="course.class_group.name")
    term = serializers.UUIDField(source="term.pk")
    maximum = serializers.IntegerField(
        help_text="Maximum de la période (examens : deux fois celui du cours)."
    )
    evaluations = EvaluationSerializer(many=True)
    students = SheetRowSerializer(source="rows", many=True)


class EvaluationInputSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Évaluation de la feuille à garder, ou identifiant (UUID v7) d'une nouvelle "
        "donné par l'appareil ; absent : nouvelle.",
    )
    name = serializers.CharField(max_length=60)
    max_score = serializers.IntegerField(min_value=1, max_value=MAX_PERIOD_MAX)


class GradeInputSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField()
    evaluation_id = serializers.UUIDField()
    score = serializers.DecimalField(
        max_digits=SCORE_DIGITS,
        decimal_places=SCORE_DECIMALS,
        min_value=Decimal(0),
        allow_null=True,
        help_text="Vide : la case est vidée.",
    )


class SheetUpdateSerializer(serializers.Serializer):
    """Évaluations ajoutées ou modifiées (dans l'ordre ; les autres restent), retirées avec leurs
    notes, et les seules cases changées."""

    evaluations = EvaluationInputSerializer(many=True, required=False, default=list)
    removed_evaluations = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=MAX_EVALUATIONS
    )
    grades = GradeInputSerializer(many=True, required=False, default=list, max_length=6000)

    def inputs(self) -> dict:
        data = self.validated_data
        return {
            "evaluations": [EvaluationInput(**row) for row in data["evaluations"]],
            "removed": data["removed_evaluations"],
            "grades": [GradeInput(**row) for row in data["grades"]],
        }

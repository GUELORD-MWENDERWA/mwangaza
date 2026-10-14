from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.academics.courses import CourseInput
from apps.academics.models import MAX_PERIOD_MAX, MAX_WEEKLY_HOURS, Course
from apps.schools.models import AcademicYear, ClassGroup
from apps.schools.serializers import PersonSerializer


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

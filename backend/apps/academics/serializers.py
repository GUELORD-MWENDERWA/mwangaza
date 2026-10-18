from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.academics import gradebook
from apps.academics.courses import CourseInput
from apps.academics.grades import MAX_EVALUATIONS, EvaluationInput, GradeInput, term_label
from apps.academics.models import (
    MAX_PERIOD_MAX,
    MAX_WEEKLY_HOURS,
    SCORE_DECIMALS,
    SCORE_DIGITS,
    Course,
    Evaluation,
    GradeSheet,
)
from apps.core.documents import PrintOptionsSerializer
from apps.schools import grading
from apps.schools.models import AcademicYear, ClassGroup
from apps.schools.serializers import PersonSerializer, TermSerializer
from apps.students.models import Enrollment


class CourseSerializer(serializers.ModelSerializer):
    teacher = PersonSerializer(read_only=True, allow_null=True)
    grade_entry = serializers.ChoiceField(
        choices=grading.ENTRIES,
        allow_blank=True,
        read_only=True,
        help_text="Saisie des points de ce cours ; vide : réglage de l'école (8.4.0).",
    )

    class Meta:
        model = Course
        fields = [
            "id",
            "name",
            "domain",
            "period_max",
            "has_exam",
            "is_taught",
            "grade_entry",
            "resit_allowed",
            "weekly_hours",
            "teacher",
        ]
        read_only_fields = fields


class CourseInputSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=False, allow_null=True, help_text="Cours de la classe à garder ; absent : nouveau."
    )
    name = serializers.CharField(max_length=100)
    domain = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    period_max = serializers.IntegerField(min_value=1, max_value=MAX_PERIOD_MAX)
    has_exam = serializers.BooleanField(default=True)
    is_taught = serializers.BooleanField(
        default=True, help_text="Faux : cours du formulaire barré sur le bulletin, jamais noté."
    )
    grade_entry = serializers.ChoiceField(
        choices=grading.ENTRIES,
        allow_blank=True,
        required=False,
        default="",
        help_text="Saisie des points de ce cours ; vide : réglage de l'école (8.4.0).",
    )
    resit_allowed = serializers.BooleanField(
        default=True,
        help_text="Faux (atelier, laboratoire) : pas de seconde session, l'échec reprend l'année.",
    )
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
    is_taught = serializers.BooleanField()
    weekly_hours = serializers.IntegerField(allow_null=True)


class OfficialGridSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="Nom traduit par l'interface.")
    reference = serializers.CharField(help_text="Référence du document officiel.")
    courses = serializers.SerializerMethodField()

    @extend_schema_field(OfficialCourseSerializer(many=True))
    def get_courses(self, grid) -> list[dict]:
        return OfficialCourseSerializer(
            [
                {
                    "name": n,
                    "period_max": m,
                    "has_exam": e,
                    "is_taught": n not in grid.untaught,
                    "weekly_hours": h,
                }
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


class GradingListCourseSerializer(GradingCourseSerializer):
    teaches = serializers.BooleanField(
        help_text="Le compte donne ce cours : il tient son carnet (évaluations et notes, NB.1) ; "
        "sinon, fiche de cotes seulement, ou un total par élève avec `grades.enter_any`."
    )

    class Meta(GradingCourseSerializer.Meta):
        fields = [*GradingCourseSerializer.Meta.fields, "teaches"]
        read_only_fields = fields


class GradingClassSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField(help_text="« 3e Électricité A ».")
    courses = GradingListCourseSerializer(
        many=True,
        help_text="Cours qu'il donne, ceux de la classe dont il est titulaire, ou tous "
        "(`grades.enter_any`).",
    )
    is_homeroom = serializers.BooleanField(
        help_text="Le compte est titulaire de la classe (tableau de la classe, 8.3.6)."
    )


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


class HistoryEntrySerializer(serializers.Serializer):
    action = serializers.CharField(help_text="`grades.changed`, `grades.submitted`…")
    at = serializers.DateTimeField()
    by = serializers.CharField()
    reason = serializers.CharField(
        help_text="Motif d'une modification après envoi ou d'une réouverture."
    )
    changes = serializers.IntegerField(help_text="Cases et évaluations changées.")


class _SheetStateSerializer(serializers.Serializer):
    """État commun du carnet et de la fiche de cotes."""

    status = serializers.ChoiceField(choices=GradeSheet.Status.choices)
    reopened = serializers.BooleanField(
        help_text="Brouillon rouvert (renvoyé par le directeur des études) : la date limite ne le "
        "ferme plus."
    )
    due_on = serializers.DateField(
        allow_null=True, help_text="Dernier jour de saisie de la période ; vide : sans limite."
    )
    submitted_at = serializers.DateTimeField(allow_null=True)
    submitted_by = serializers.CharField(help_text="Qui l'a envoyée et signée.")
    validated_at = serializers.DateTimeField(allow_null=True)
    validated_by = serializers.CharField()
    returned = HistoryEntrySerializer(
        allow_null=True,
        help_text="Renvoyée avec remarques (`reason`) et pas encore renvoyée de nouveau ; vide "
        "sinon.",
    )
    history = HistoryEntrySerializer(many=True, help_text="Les plus récentes d'abord.")
    course = GradingCourseSerializer()
    class_group = serializers.CharField(source="course.class_group.name")
    term = serializers.UUIDField(source="term.pk")
    maximum = serializers.IntegerField(
        help_text="Maximum de la période (examens : deux fois celui du cours)."
    )


class TotalsRowSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField(source="enrollment.pk")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    matricule = serializers.CharField(source="enrollment.student.matricule")
    status = serializers.ChoiceField(source="enrollment.status", choices=Enrollment.Status.choices)
    total = serializers.DecimalField(
        max_digits=SCORE_DIGITS + 2, decimal_places=SCORE_DECIMALS, allow_null=True
    )


class TotalsSheetSerializer(_SheetStateSerializer):
    """Fiche de cotes (NB.1) : un total par élève, sans les évaluations."""

    term_label = serializers.SerializerMethodField(help_text="« 1re période », « Examens · S1 ».")
    students = TotalsRowSerializer(
        source="rows", many=True, help_text="Vide tant que la fiche n'est pas envoyée."
    )

    def get_term_label(self, sheet) -> str:
        return str(term_label(sheet.term))


class SheetSerializer(_SheetStateSerializer):
    entry = serializers.ChoiceField(
        choices=grading.ENTRIES,
        help_text="totals : une seule évaluation « Total » au maximum de la période (8.4.0) ; "
        "toujours pour `grades.enter_any` hors de ses cours (NB.1).",
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
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=300,
        help_text="Obligatoire si la feuille est déjà envoyée pour validation.",
    )

    def inputs(self) -> dict:
        data = self.validated_data
        return {
            "evaluations": [EvaluationInput(**row) for row in data["evaluations"]],
            "removed": data["removed_evaluations"],
            "grades": [GradeInput(**row) for row in data["grades"]],
            "reason": data["reason"],
        }


class ReopenSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=300)


class DeadlineSerializer(serializers.Serializer):
    due_on = serializers.DateField(allow_null=True, help_text="Vide : plus de limite.")


class PendingSheetSerializer(serializers.Serializer):
    course = serializers.UUIDField(source="course.pk")
    course_name = serializers.CharField(source="course.name")
    class_group = serializers.CharField(source="course.class_group.name")
    term = serializers.UUIDField(source="term.pk")
    submitted_at = serializers.DateTimeField()
    submitted_by = serializers.CharField()


class DeadlineRowSerializer(serializers.Serializer):
    term = serializers.UUIDField()
    due_on = serializers.DateField()


class ValidationSerializer(serializers.Serializer):
    academic_year = serializers.UUIDField(allow_null=True)
    terms = TermSerializer(many=True)
    deadlines = DeadlineRowSerializer(many=True)
    sheets = PendingSheetSerializer(many=True, help_text="Envoyées, les plus anciennes d'abord.")


class ReportCardSerializer(serializers.Serializer):
    """Bulletin (8.3.2) d'un élève de la classe."""

    enrollment = serializers.UUIDField(
        required=False,
        help_text="Inscription de l'élève dans cette classe ; absente : toute la classe, un élève "
        "par feuille (PDF seulement).",
    )
    output = serializers.ChoiceField(choices=["pdf", "html"], help_text="PDF, ou son aperçu HTML.")
    mode = serializers.ChoiceField(
        choices=["full", "grades_only"],
        default="full",
        help_text="`grades_only` : seules les valeurs, pour le formulaire pré-imprimé.",
    )
    dx = serializers.FloatField(
        min_value=-10, max_value=10, default=0, help_text="Décalage horizontal, en mm."
    )
    dy = serializers.FloatField(
        min_value=-10, max_value=10, default=0, help_text="Décalage vertical, en mm."
    )

    def validate(self, attrs):
        if not attrs.get("enrollment") and attrs["output"] != "pdf":
            raise serializers.ValidationError({"enrollment": "Required for the HTML preview."})
        return attrs


class MissingSheetSerializer(serializers.Serializer):
    course = serializers.CharField()
    term = serializers.CharField()


class ReportCardStatusSerializer(serializers.Serializer):
    """Le bulletin de la classe peut-il s'imprimer ? Feuilles de notes pas encore validées."""

    missing_count = serializers.IntegerField()
    missing = MissingSheetSerializer(many=True, help_text="Les premières seulement.")


class GradeSheetPrintSerializer(PrintOptionsSerializer):
    """Fiche de cotes (8.3.6) d'une classe : d'un cours, vierge, ou tableau de toute la classe."""

    kind = serializers.ChoiceField(choices=["course", "blank", "class"])
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects,
        required=False,
        help_text="Cours de la classe (`kind` : `course` ou `blank`).",
    )
    column = serializers.CharField(
        default="year",
        help_text="`kind=class` : `year`, ou l'identifiant d'une période, d'un examen ou d'un "
        "semestre de l'année.",
    )
    columns = serializers.MultipleChoiceField(
        choices=gradebook.COLUMNS,
        required=False,
        help_text="Colonnes en plus du N° et du nom (paramètre répété) : `matricule`, `totals` "
        "(totaux des semestres et de l'année, fiche d'un cours).",
    )
    blank_columns = serializers.IntegerField(
        min_value=1,
        max_value=gradebook.MAX_BLANK_COLUMNS,
        default=8,
        help_text="`kind=blank` : colonnes vides à remplir.",
    )
    output = serializers.ChoiceField(choices=["pdf", "html"], default="pdf")

    def validate(self, attrs):
        if attrs["kind"] != "class" and "course" not in attrs:
            raise serializers.ValidationError({"course": "Required for this kind of sheet."})
        return attrs

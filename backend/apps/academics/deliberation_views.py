"""API de la délibération d'une classe (8.4.2) : tableau (proposition, décision, écart), date,
décision d'un élève, application des propositions, proclamation et réouverture ; reprise des
résultats d'une année sans notes, importés d'un fichier (8.4.7). Droit : `grades.validate`
(direction des études) ; comme partout, le serveur vérifie."""

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import deliberation, prior_results
from apps.academics.models import DeliberationDecision
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import GRADES_VALIDATE
from apps.core.documents import XLSX, XLSX_RESPONSE, file_response
from apps.core.errors import ErrorSerializer
from apps.schools.models import AcademicYear, ClassGroup
from apps.students.models import Enrollment

ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}
DECISIONS = DeliberationDecision.Decision.values
OUTCOMES = [
    "passed",
    "resit",
    "failed",
    "incomplete",
    "unranked",
    "orient",
    "exclude",
]


class RowSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField(source="enrollment.pk")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    percent = serializers.DecimalField(
        max_digits=5, decimal_places=1, allow_null=True, help_text="Pourcentage de l'année."
    )
    outcome = serializers.ChoiceField(choices=OUTCOMES, help_text="Issue des règles (8.4.1).")
    proposed = serializers.CharField(
        help_text="Décision proposée (mêmes valeurs que `decision`) ; vide sans proposition."
    )
    decision = serializers.ChoiceField(
        choices=[*DECISIONS, ""], help_text="Vide : pas encore prise."
    )
    reason = serializers.CharField()
    deviates = serializers.BooleanField(help_text="La décision diffère de la proposition.")


class ProclamationSerializer(serializers.Serializer):
    version = serializers.IntegerField()
    held_on = serializers.DateField()
    proclaimed_at = serializers.DateTimeField()
    proclaimed_by = serializers.CharField(source="proclaimed_by.get_full_name")
    reason = serializers.CharField()


class ClassDeliberationSerializer(serializers.Serializer):
    class_name = serializers.CharField()
    status = serializers.ChoiceField(choices=["draft", "proclaimed"])
    held_on = serializers.DateField(allow_null=True)
    version = serializers.IntegerField(help_text="Dernière version proclamée (0 : aucune).")
    counts = serializers.DictField(child=serializers.IntegerField())
    deviations = serializers.IntegerField()
    latest = ProclamationSerializer(allow_null=True, help_text="Dernière proclamation figée.")
    students = RowSerializer(many=True)


def _answer(group: ClassGroup) -> Response:
    data = deliberation.overview(group)
    current = data.deliberation
    return Response(
        ClassDeliberationSerializer(
            {
                "class_name": group.name,
                "status": data.status,
                "held_on": current.held_on if current else None,
                "version": current.version if current else 0,
                "counts": data.counts,
                "deviations": data.deviations,
                "latest": data.latest,
                "students": data.rows,
            }
        ).data
    )


def _group(pk) -> ClassGroup:
    return get_object_or_404(ClassGroup.objects.select_related("school", "level"), pk=pk)


class _View(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = GRADES_VALIDATE


class DateSerializer(serializers.Serializer):
    held_on = serializers.DateField()


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=DECISIONS)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)
    percent = serializers.DecimalField(
        max_digits=4,
        decimal_places=1,
        required=False,
        allow_null=True,
        help_text="Pourcentage repris (8.4.7) : seulement pour un élève sans aucune note cette "
        "année (issue `unranked`) ; absent ou nul : aucun.",
    )


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


@extend_schema(tags=["deliberation"])
class ClassDeliberationView(_View):
    @extend_schema(responses={200: ClassDeliberationSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Tableau de la classe : pourcentage de l'année, décision proposée d'après les règles de
        l'école, décision prise, écart et motif ; statut, date et dernière version proclamée."""
        return _answer(_group(pk))

    @extend_schema(request=DateSerializer, responses={200: ClassDeliberationSerializer, **ERRORS})
    def put(self, request: Request, pk) -> Response:
        """Fixe la date de la délibération (classe non proclamée)."""
        group = _group(pk)
        data = DateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        deliberation.set_date(group, data.validated_data["held_on"], actor=request.user)
        return _answer(group)


@extend_schema(tags=["deliberation"])
class EnrollmentDecisionView(_View):
    @extend_schema(
        request=DecisionSerializer, responses={200: ClassDeliberationSerializer, **ERRORS}
    )
    def put(self, request: Request, pk) -> Response:
        """Décision prise pour un élève ; un écart avec la proposition demande un motif. Élève
        sans aucune note cette année : pourcentage repris, de 0 à 100 (8.4.7)."""
        enrollment = get_object_or_404(
            Enrollment.objects.select_related(
                "student", "class_group__school", "class_group__level"
            ),
            pk=pk,
        )
        data = DecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        deliberation.decide(
            enrollment,
            data.validated_data["decision"],
            data.validated_data.get("reason", ""),
            actor=request.user,
            percent=data.validated_data.get("percent"),
        )
        return _answer(enrollment.class_group)


@extend_schema(tags=["deliberation"])
class ApplyProposalsView(_View):
    @extend_schema(request=None, responses={200: ClassDeliberationSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Prend la proposition du système pour chaque élève qui n'a pas encore de décision."""
        group = _group(pk)
        deliberation.apply_proposals(group, actor=request.user)
        return _answer(group)


@extend_schema(tags=["deliberation"])
class ProclaimView(_View):
    @extend_schema(request=None, responses={200: ClassDeliberationSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Proclame les résultats et les fige : date posée, une décision par élève, un motif par
        écart. Une proclamation après correction crée la version suivante."""
        group = _group(pk)
        deliberation.proclaim(group, actor=request.user)
        return _answer(group)


@extend_schema(tags=["deliberation"])
class ReopenView(_View):
    @extend_schema(request=ReasonSerializer, responses={200: ClassDeliberationSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Rouvre une classe proclamée pour corriger (motif obligatoire). Les résultats figés
        restent ceux de la dernière proclamation jusqu'à la suivante."""
        group = _group(pk)
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        deliberation.reopen(group, data.validated_data["reason"], actor=request.user)
        return _answer(group)


# Reprise des résultats (8.4.7)

PRIOR_RESULT_ISSUES = [
    "missing_matricule",
    "unknown_student",
    "duplicate",
    "missing_decision",
    "unknown_decision",
    "invalid_percent",
    "has_grades",
    "class_proclaimed",
]


class PriorResultUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Excel (.xlsx) ou CSV, 5 Mo au plus.")
    academic_year = serializers.UUIDField(help_text="Année des résultats.")
    expected = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Nombre de lignes prêtes de l'aperçu : présent, le fichier est enregistré.",
    )
    held_on = serializers.DateField(
        required=False, help_text="Date de délibération des classes qui n'en ont pas."
    )

    def validate(self, attrs):
        if "expected" in attrs and "held_on" not in attrs:
            raise serializers.ValidationError({"held_on": deliberation.DATE_REQUIRED.detail})
        return attrs


class PriorResultIssueSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=PRIOR_RESULT_ISSUES)


class PriorResultLineSerializer(serializers.Serializer):
    line = serializers.IntegerField(source="number", help_text="Numéro de la ligne du fichier.")
    matricule = serializers.CharField()
    student = serializers.CharField(source="enrollment.student", allow_null=True)
    class_group = serializers.CharField(source="enrollment.class_group.name", allow_null=True)
    decision_text = serializers.CharField(help_text="Décision telle qu'elle est écrite.")
    decision = serializers.CharField(
        help_text="Décision reconnue (valeurs de `decision`), ou vide."
    )
    percent_text = serializers.CharField(help_text="Pourcentage tel qu'il est écrit.")
    percent = serializers.DecimalField(max_digits=4, decimal_places=1, allow_null=True)
    issues = PriorResultIssueSerializer(many=True)


class PriorResultPreviewSerializer(serializers.Serializer):
    """Aperçu d'un fichier de résultats repris, ou son résultat une fois enregistré."""

    recorded = serializers.BooleanField()
    ready_count = serializers.IntegerField(help_text="Lignes prêtes (ou enregistrées).")
    error_count = serializers.IntegerField(help_text="Lignes en erreur : jamais enregistrées.")
    empty_count = serializers.IntegerField(help_text="Lignes sans décision : ignorées.")
    class_count = serializers.IntegerField(help_text="Classes des lignes prêtes.")
    changed_count = serializers.IntegerField(
        help_text="Décisions écrites (0 : le fichier était déjà enregistré tel quel)."
    )
    errors = PriorResultLineSerializer(many=True, help_text="Les 300 premières.")
    ready = PriorResultLineSerializer(many=True, help_text="Les 20 premières.")


@extend_schema(tags=["deliberation"])
class PriorResultsView(_View):
    """Reprise des résultats d'une année sans notes dans Mwangaza (8.4.7) : décision finale et
    pourcentage de chaque élève, importés d'un fichier. Sans `expected` : aperçu (200), rien
    n'est écrit. Avec le nombre de lignes prêtes de l'aperçu et la date : décisions écrites dans
    la délibération de chaque classe, à proclamer ensuite (201) ; 409 `preview_outdated` si le
    résultat n'est plus celui de l'aperçu."""

    parser_classes = [MultiPartParser]

    @extend_schema(
        request={"multipart/form-data": PriorResultUploadSerializer},
        responses={
            200: PriorResultPreviewSerializer,
            201: PriorResultPreviewSerializer,
            409: ErrorSerializer,
            **ERRORS,
        },
    )
    def post(self, request: Request) -> Response:
        params = PriorResultUploadSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        year = get_object_or_404(AcademicYear, pk=data["academic_year"])
        expected = data.get("expected")
        if expected is None:
            preview = prior_results.check(data["file"], year)
        else:
            preview = prior_results.record(
                data["file"],
                actor=request.user,
                year=year,
                held_on=data["held_on"],
                expected=expected,
            )
        errors = preview.errors
        body = {
            "recorded": expected is not None,
            "ready_count": len(preview.ready),
            "error_count": len(errors),
            "empty_count": preview.empty,
            "class_count": preview.class_count,
            "changed_count": preview.changed,
            "errors": errors[: prior_results.MAX_ERRORS],
            "ready": preview.ready[: prior_results.MAX_READY],
        }
        return Response(
            PriorResultPreviewSerializer(body).data,
            status=status.HTTP_200_OK if expected is None else status.HTTP_201_CREATED,
        )


@extend_schema(tags=["deliberation"])
class PriorResultsTemplateView(_View):
    """Modèle Excel de la reprise des résultats, déjà garni : les élèves de l'année sans aucune
    note, dans une classe pas encore proclamée, avec ce qui est déjà repris."""

    @extend_schema(
        parameters=[OpenApiParameter("academic_year", str, required=True)],
        responses={**XLSX_RESPONSE, **ERRORS},
    )
    def get(self, request: Request) -> HttpResponse:
        year = get_object_or_404(AcademicYear, pk=_uuid(request.query_params.get("academic_year")))
        return file_response(
            prior_results.template_workbook(year), XLSX, f"resultats-{year.name}.xlsx"
        )


def _uuid(value):
    field = serializers.UUIDField()
    try:
        return field.to_internal_value(value)
    except serializers.ValidationError:
        raise Http404 from None

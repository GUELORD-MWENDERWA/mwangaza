"""API de la délibération d'une classe (8.4.2) : tableau (proposition, décision, écart), date,
décision d'un élève, application des propositions, proclamation et réouverture. Droit :
`grades.validate` (direction des études) ; comme partout, le serveur vérifie."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import deliberation
from apps.academics.models import DeliberationDecision
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import GRADES_VALIDATE
from apps.core.errors import ErrorSerializer
from apps.schools.models import ClassGroup
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
        """Décision prise pour un élève ; un écart avec la proposition demande un motif."""
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

"""API de la conduite (8.5.1a) : infractions, seuils des cotes, incidents des élèves. Module
`academics` ; en ligne seulement. Les listes d'élèves à choisir ne sortent que pour qui attribue
des infractions."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import discipline
from apps.academics.discipline_serializers import (
    CancelSerializer,
    ClearOverrideSerializer,
    IncidentCreateSerializer,
    IncidentSerializer,
    OverrideSerializer,
    PickClassSerializer,
    PickStudentSerializer,
    RuleCreateSerializer,
    RuleSerializer,
    RuleUpdateSerializer,
    ScaleSerializer,
    StudentIncidentsSerializer,
)
from apps.academics.models import DisciplineIncident, DisciplineRule
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import DISCIPLINE_CONFIGURE, DISCIPLINE_OVERRIDE, DISCIPLINE_RECORD
from apps.core.errors import ErrorSerializer
from apps.schools import organisation
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
READ = (DISCIPLINE_RECORD, DISCIPLINE_CONFIGURE, DISCIPLINE_OVERRIDE)
# Une liste de classe : ~60 élèves au plus, jamais assez pour paginer.
CLASS_STUDENTS_LIMIT = 200


class _DisciplineView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = READ


class _ConfigureView(_DisciplineView):
    required_permission = DISCIPLINE_CONFIGURE


@extend_schema(tags=["discipline"])
class RulesView(_DisciplineView):
    @property
    def required_permission(self):
        return DISCIPLINE_CONFIGURE if self.request.method == "POST" else READ

    @extend_schema(
        parameters=[OpenApiParameter("all", bool, description="Avec les infractions retirées.")],
        responses={200: RuleSerializer(many=True), **ERRORS},
    )
    def get(self, request: Request) -> Response:
        """Liste des infractions et leurs points ; les retirées seulement avec `?all=1`."""
        every = request.query_params.get("all") == "1"
        return Response(RuleSerializer(discipline.rules_of(only_active=not every), many=True).data)

    @extend_schema(
        request=RuleCreateSerializer,
        responses={201: RuleSerializer, 400: ErrorSerializer, 409: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Ajoute une infraction à la liste."""
        data = RuleCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rule = discipline.create_rule(actor=request.user, **data.validated_data)
        return Response(RuleSerializer(rule).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["discipline"])
class RuleView(_ConfigureView):
    @extend_schema(
        request=RuleUpdateSerializer,
        responses={200: RuleSerializer, 400: ErrorSerializer, 409: ErrorSerializer, **ERRORS},
    )
    def patch(self, request: Request, pk) -> Response:
        """Change le libellé ou les points, ou retire l'infraction de la liste (`is_active`)."""
        rule = get_object_or_404(DisciplineRule.objects, pk=pk)
        data = RuleUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rule = discipline.update_rule(rule, actor=request.user, **data.validated_data)
        return Response(RuleSerializer(rule).data)


@extend_schema(tags=["discipline"])
class DefaultRulesView(_ConfigureView):
    @extend_schema(
        request=None,
        responses={201: RuleSerializer(many=True), 409: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Charge la liste proposée, si la liste est encore vide."""
        rules = discipline.add_default_rules(actor=request.user)
        return Response(RuleSerializer(rules, many=True).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["discipline"])
class ScaleView(_DisciplineView):
    @property
    def required_permission(self):
        return DISCIPLINE_CONFIGURE if self.request.method == "PUT" else READ

    @extend_schema(responses={200: ScaleSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Points minimum de chaque cote de conduite (TB, B, AB, ME, MA)."""
        return Response({"scale": discipline.scale_of()})

    @extend_schema(
        request=ScaleSerializer,
        responses={200: ScaleSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def put(self, request: Request) -> Response:
        """Enregistre les cinq seuils."""
        data = ScaleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        scale = discipline.set_scale(data.minimums(), actor=request.user)
        return Response({"scale": scale})


@extend_schema(tags=["discipline"])
class ClassesView(_DisciplineView):
    required_permission = DISCIPLINE_RECORD

    @extend_schema(responses={200: PickClassSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Classes de l'année en cours, pour choisir l'élève."""
        year = organisation.current_year()
        groups = (
            ClassGroup.objects.filter(academic_year=year).select_related("level", "track")
            if year
            else ClassGroup.objects.none()
        )
        rows = [{"id": group.pk, "name": group.name} for group in groups]
        return Response(PickClassSerializer(sorted(rows, key=lambda r: r["name"]), many=True).data)


@extend_schema(tags=["discipline"])
class ClassStudentsView(_DisciplineView):
    required_permission = DISCIPLINE_RECORD

    @extend_schema(responses={200: PickStudentSerializer(many=True), **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Élèves inscrits dans la classe, avec l'inscription à envoyer."""
        group = get_object_or_404(ClassGroup.objects, pk=pk)
        enrollments = (
            Enrollment.objects.filter(class_group=group, status=Enrollment.Status.ACTIVE)
            .select_related("student")
            .order_by("student__last_name", "student__first_name")[:CLASS_STUDENTS_LIMIT]
        )
        rows = [
            {
                "enrollment": e.pk,
                "full_name": e.student.full_name,
                "matricule": e.student.matricule,
            }
            for e in enrollments
        ]
        return Response(PickStudentSerializer(rows, many=True).data)


@extend_schema(tags=["discipline"])
class IncidentsView(_DisciplineView):
    required_permission = DISCIPLINE_RECORD

    @extend_schema(
        request=IncidentCreateSerializer,
        responses={201: IncidentSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Attribue une infraction à un élève."""
        data = IncidentCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        incident = discipline.record_incident(
            actor=request.user,
            enrollment=data.validated_data["enrollment"],
            rule=data.validated_data["rule"],
            occurred_on=data.validated_data["occurred_on"],
            note=data.validated_data["note"],
            term=data.validated_data.get("term"),
        )
        return Response(IncidentSerializer(incident).data, status=status.HTTP_201_CREATED)


def _student_conduct(enrollment: Enrollment) -> dict:
    enrollment = Enrollment.objects.select_related(
        "student", "class_group__level", "class_group__track"
    ).get(pk=enrollment.pk)
    data = {
        "full_name": enrollment.student.full_name,
        "class_name": enrollment.class_group.name,
        "incidents": discipline.incidents_of(enrollment),
        "totals": discipline.totals_of(enrollment),
    }
    return StudentIncidentsSerializer(data).data


@extend_schema(tags=["discipline"])
class EnrollmentIncidentsView(_DisciplineView):
    @extend_schema(responses={200: StudentIncidentsSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Incidents d'un élève (annulés marqués) et points par période avec la cote proposée."""
        enrollment = get_object_or_404(
            Enrollment.objects.select_related(
                "student", "class_group__level", "class_group__track"
            ),
            pk=pk,
        )
        return Response(_student_conduct(enrollment))


@extend_schema(tags=["discipline"])
class GradeOverrideView(_DisciplineView):
    required_permission = DISCIPLINE_OVERRIDE

    @extend_schema(
        request=OverrideSerializer,
        responses={200: StudentIncidentsSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def put(self, request: Request, pk) -> Response:
        """Corrige la cote de conduite d'une période, avec un motif."""
        enrollment = get_object_or_404(Enrollment.objects.select_related("student"), pk=pk)
        data = OverrideSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        discipline.override_grade(
            enrollment,
            data.validated_data["term"],
            actor=request.user,
            grade=data.validated_data["grade"],
            reason=data.validated_data["reason"],
        )
        return Response(_student_conduct(enrollment))

    @extend_schema(
        parameters=[OpenApiParameter("term", str, required=True, description="Période.")],
        responses={200: StudentIncidentsSerializer, **ERRORS},
    )
    def delete(self, request: Request, pk) -> Response:
        """Reprend la cote donnée par les points."""
        enrollment = get_object_or_404(Enrollment.objects.select_related("student"), pk=pk)
        data = ClearOverrideSerializer(data=request.query_params)
        data.is_valid(raise_exception=True)
        discipline.clear_override(enrollment, data.validated_data["term"], actor=request.user)
        return Response(_student_conduct(enrollment))


@extend_schema(tags=["discipline"])
class IncidentCancelView(_ConfigureView):
    @extend_schema(
        request=CancelSerializer,
        responses={200: IncidentSerializer, 400: ErrorSerializer, 409: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request, pk) -> Response:
        """Annule l'incident, avec un motif ; il reste visible, ses points ne comptent plus."""
        incident = get_object_or_404(
            DisciplineIncident.objects.select_related("enrollment__student", "rule"), pk=pk
        )
        data = CancelSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        discipline.cancel_incident(
            incident, actor=request.user, reason=data.validated_data["reason"]
        )
        incident = discipline.incidents_of(incident.enrollment).get(pk=incident.pk)
        return Response(IncidentSerializer(incident).data)

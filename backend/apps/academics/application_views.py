"""API de l'Application (8.5.1c) : tableau de la classe et correction de la cote d'une période
par le titulaire (ou `grades.enter_any`)."""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import application, report_cards
from apps.academics.discipline_serializers import ClearOverrideSerializer
from apps.academics.models import ConductScale
from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE
from apps.core.errors import ErrorSerializer
from apps.schools.models import ClassGroup, Term
from apps.students.models import Enrollment

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}


class TermApplicationSerializer(serializers.Serializer):
    term = serializers.UUIDField(source="term.pk")
    term_name = serializers.SerializerMethodField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    proposed = serializers.CharField(help_text="Cote d'après le pourcentage ; vide sans note.")
    grade = serializers.CharField(help_text="Cote retenue : la correction si elle existe.")
    override_reason = serializers.SerializerMethodField()
    override_by = serializers.SerializerMethodField()

    def get_term_name(self, row) -> str:
        return row.term.name

    def get_override_reason(self, row) -> str:
        return row.override.reason if row.override else ""

    def get_override_by(self, row) -> str:
        return row.override.corrected_by.get_full_name() if row.override else ""


class StudentApplicationSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField()
    full_name = serializers.CharField()
    terms = TermApplicationSerializer(many=True)


class ClassApplicationSerializer(serializers.Serializer):
    class_name = serializers.CharField()
    may_correct = serializers.BooleanField()
    students = StudentApplicationSerializer(many=True)


class ApplicationOverrideSerializer(serializers.Serializer):
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects)
    grade = serializers.ChoiceField(choices=ConductScale.Grade.choices)
    reason = serializers.CharField(max_length=300)


class _ApplicationView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = (GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE)


def _class_data(group: ClassGroup, *, can: bool) -> dict:
    report = report_cards.class_report(group)
    return {
        "class_name": group.name,
        "may_correct": can,
        "students": [
            {
                "enrollment": enrollment.pk,
                "full_name": enrollment.student.full_name,
                "terms": rows,
            }
            for enrollment, rows in application.class_overview(report)
        ],
    }


@extend_schema(tags=["application"])
class ClassApplicationView(_ApplicationView):
    @extend_schema(responses={200: ClassApplicationSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Cote d'application de chaque élève de la classe, par période : pourcentage, cote
        proposée et cote retenue. `may_correct` : la personne peut la corriger."""
        group = get_object_or_404(ClassGroup, pk=pk)
        can = application.may_correct(request.user, school_access(request).permissions, group)
        if not can and GRADES_VALIDATE not in school_access(request).permissions:
            raise PermissionDenied(gettext("You cannot see the application grades of this class."))
        return Response(ClassApplicationSerializer(_class_data(group, can=can)).data)


@extend_schema(tags=["application"])
class ApplicationOverrideView(_ApplicationView):
    def _enrollment(self, request: Request, pk) -> Enrollment:
        enrollment = get_object_or_404(
            Enrollment.objects.select_related("student", "class_group"), pk=pk
        )
        permissions = school_access(request).permissions
        if not application.may_correct(request.user, permissions, enrollment.class_group):
            raise PermissionDenied(_("Only the homeroom teacher corrects the application grade."))
        return enrollment

    def _answer(self, enrollment: Enrollment) -> Response:
        data = _class_data(enrollment.class_group, can=True)
        student = next(s for s in data["students"] if s["enrollment"] == enrollment.pk)
        return Response(StudentApplicationSerializer(student).data)

    @extend_schema(
        request=ApplicationOverrideSerializer,
        responses={200: StudentApplicationSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def put(self, request: Request, pk) -> Response:
        """Corrige la cote d'une période, avec un motif (titulaire ou `grades.enter_any`)."""
        enrollment = self._enrollment(request, pk)
        data = ApplicationOverrideSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        application.override_grade(
            enrollment,
            data.validated_data["term"],
            actor=request.user,
            grade=data.validated_data["grade"],
            reason=data.validated_data["reason"],
        )
        return self._answer(enrollment)

    @extend_schema(
        parameters=[OpenApiParameter("term", str, required=True, description="Période.")],
        responses={200: StudentApplicationSerializer, **ERRORS},
    )
    def delete(self, request: Request, pk) -> Response:
        """Reprend la cote proposée par le pourcentage."""
        enrollment = self._enrollment(request, pk)
        data = ClearOverrideSerializer(data=request.query_params)
        data.is_valid(raise_exception=True)
        application.clear_override(enrollment, data.validated_data["term"], actor=request.user)
        return self._answer(enrollment)

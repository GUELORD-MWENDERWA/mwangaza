"""Remplaçants des cours (8.2.5) : le directeur des études (`grades.validate`) les désigne et les
retire ; le remplaçant saisit ensuite dans ses notes (`/api/grading/`)."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import substitutes
from apps.academics.models import Course, CourseSubstitute
from apps.academics.serializers import (
    CourseSubstituteCreateSerializer,
    CourseSubstituteFilterSerializer,
    CourseSubstituteSerializer,
)
from apps.academics.views import ERRORS
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import GRADES_VALIDATE
from apps.core.errors import ErrorSerializer


def _present(row: CourseSubstitute) -> CourseSubstitute:
    row.label = substitutes.label(row)
    row.teacher = substitutes.teacher_of(row)
    row.since = timezone.localdate(row.created_at)
    return row


class _SubstitutesView(APIView):
    permission_classes = [HasSchoolPermission]
    required_permission = GRADES_VALIDATE
    required_module = "academics"


@extend_schema(tags=["grades"])
class CourseSubstitutesView(_SubstitutesView):
    serializer_class = CourseSubstituteCreateSerializer

    @extend_schema(
        parameters=[CourseSubstituteFilterSerializer],
        responses={200: CourseSubstituteSerializer(many=True), **ERRORS},
    )
    def get(self, request: Request) -> Response:
        """Remplaçants en cours (date de fin pas encore passée), d'une année au choix."""
        params = CourseSubstituteFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        rows = substitutes.listing(params.validated_data.get("academic_year"))
        return Response(CourseSubstituteSerializer([_present(r) for r in rows], many=True).data)

    @extend_schema(
        request=CourseSubstituteCreateSerializer,
        responses={201: CourseSubstituteSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Désigne le remplaçant d'un cours (de tout son groupe s'il est commun), avec motif et
        date de fin facultative ; un remplaçant déjà en cours : 409 `substitute_exists`."""
        data = CourseSubstituteCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        # Manager de l'école : un cours d'une autre école est introuvable.
        course = get_object_or_404(
            Course.objects.select_related("course_group"), pk=data.validated_data["course"]
        )
        row = substitutes.designate(
            course,
            substitute_id=data.validated_data["substitute_id"],
            reason=data.validated_data["reason"],
            ends_on=data.validated_data["ends_on"],
            actor=request.user,
        )
        fresh = substitutes.with_details(CourseSubstitute.objects).get(pk=row.pk)
        return Response(
            CourseSubstituteSerializer(_present(fresh)).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["grades"])
class CourseSubstituteView(_SubstitutesView):
    @extend_schema(responses={204: None, **ERRORS})
    def delete(self, request: Request, pk) -> Response:
        """Retire le remplaçant : il perd l'accès au cours, les notes qu'il a saisies restent."""
        row = get_object_or_404(substitutes.with_details(CourseSubstitute.objects), pk=pk)
        substitutes.remove(row, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

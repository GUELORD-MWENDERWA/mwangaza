from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.academics import course_groups
from apps.academics.models import CourseGroup
from apps.academics.serializers import (
    CourseGroupCreateSerializer,
    CourseGroupFilterSerializer,
    CourseGroupRemoveClassSerializer,
    CourseGroupSerializer,
    CourseGroupUpdateSerializer,
)
from apps.academics.views import ERRORS, _CoursesView
from apps.core.errors import ErrorSerializer
from apps.schools.models import ClassGroup


def _one(group: CourseGroup) -> dict:
    fresh = course_groups.groups_of().get(pk=group.pk)
    return CourseGroupSerializer(course_groups.present([fresh])[0]).data


@extend_schema(tags=["courses"])
class CourseGroupsView(_CoursesView):
    serializer_class = CourseGroupCreateSerializer

    @extend_schema(
        parameters=[CourseGroupFilterSerializer],
        responses={200: CourseGroupSerializer(many=True), **ERRORS},
    )
    def get(self, request: Request) -> Response:
        """Cours communs de l'école, d'une année et d'un niveau au choix."""
        params = CourseGroupFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        groups = course_groups.groups_of(
            params.validated_data.get("academic_year"), params.validated_data.get("level")
        )
        return Response(CourseGroupSerializer(course_groups.present(list(groups)), many=True).data)

    @extend_schema(
        request=CourseGroupCreateSerializer,
        responses={201: CourseGroupSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Relie le cours de même nom de plusieurs classes d'un même niveau : un seul enseignant."""
        data = CourseGroupCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        found = {
            g.pk: g for g in ClassGroup.objects.filter(pk__in=data.validated_data["class_groups"])
        }
        if len(found) != len(set(data.validated_data["class_groups"])):
            # Classe inconnue ou d'une autre école : le manager de l'école ne la voit pas.
            raise Http404
        group = course_groups.create_group(
            name=data.validated_data["name"],
            class_groups=[found[pk] for pk in data.validated_data["class_groups"]],
            teacher_id=data.validated_data["teacher_id"],
            actor=request.user,
        )
        return Response(_one(group), status=status.HTTP_201_CREATED)


@extend_schema(tags=["courses"])
class CourseGroupView(_CoursesView):
    serializer_class = CourseGroupUpdateSerializer

    def object(self, pk) -> CourseGroup:
        return get_object_or_404(CourseGroup, pk=pk)

    @extend_schema(
        request=CourseGroupUpdateSerializer,
        responses={200: CourseGroupSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def patch(self, request: Request, pk) -> Response:
        """Change l'enseignant du groupe : il devient celui du cours de chaque classe."""
        group = self.object(pk)
        data = CourseGroupUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        course_groups.set_teacher(group, data.validated_data["teacher_id"], actor=request.user)
        return Response(_one(group))

    @extend_schema(responses={204: None, **ERRORS})
    def delete(self, request: Request, pk) -> Response:
        """Défait le cours commun : chaque classe garde son cours, ses notes et son enseignant."""
        course_groups.dissolve(self.object(pk), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["courses"])
class CourseGroupRemoveClassView(_CoursesView):
    serializer_class = CourseGroupRemoveClassSerializer

    @extend_schema(
        request=CourseGroupRemoveClassSerializer,
        responses={204: None, 400: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request, pk) -> Response:
        """Sort une classe du groupe sans perdre ses notes ; sous deux classes, il est défait."""
        group = get_object_or_404(CourseGroup, pk=pk)
        data = CourseGroupRemoveClassSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        class_group = get_object_or_404(ClassGroup, pk=data.validated_data["class_group"])
        course_groups.remove_class(group, class_group, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

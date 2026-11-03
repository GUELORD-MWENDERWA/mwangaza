"""API des dérogations de bulletin (8.4.6) : le préfet accorde ou lève une dérogation pour une
famille ou un élève dont les frais échus sont impayés (droit `grades.waive_fees`)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import waivers
from apps.academics.models import FeeWaiver
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import GRADES_WAIVE_FEES
from apps.core.errors import ErrorSerializer
from apps.students.models import Family, Student

ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer, 409: ErrorSerializer}


class FeeWaiverSerializer(serializers.ModelSerializer):
    target_name = serializers.SerializerMethodField(help_text="Élève ou famille concernée.")
    granted_by_name = serializers.CharField(source="granted_by.get_full_name", read_only=True)
    active = serializers.SerializerMethodField(help_text="Ni levée ni expirée.")

    class Meta:
        model = FeeWaiver
        fields = [
            "id",
            "family",
            "student",
            "target_name",
            "reason",
            "until",
            "granted_by_name",
            "created_at",
            "lifted_at",
            "active",
        ]
        read_only_fields = fields

    def get_target_name(self, waiver: FeeWaiver) -> str:
        return waiver.student.full_name if waiver.student_id else str(waiver.family)

    def get_active(self, waiver: FeeWaiver) -> bool:
        return waiver.lifted_at is None and waiver.until >= waivers.finance.today()


class FeeWaiverInputSerializer(serializers.Serializer):
    family = serializers.UUIDField(required=False, allow_null=True)
    student = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=300)
    until = serializers.DateField()


class _View:
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = GRADES_WAIVE_FEES


@extend_schema(tags=["waivers"])
class FeeWaiverListView(_View, ListCreateAPIView):
    serializer_class = FeeWaiverSerializer

    def get_queryset(self):
        return waivers.listing(only_active=self.request.query_params.get("active") == "1")

    @extend_schema(
        parameters=[OpenApiParameter("active", bool, description="1 : seulement les actives.")]
    )
    def get(self, request, *args, **kwargs):
        """Dérogations de l'école, la plus récente d'abord."""
        return super().get(request, *args, **kwargs)

    @extend_schema(request=FeeWaiverInputSerializer, responses={201: FeeWaiverSerializer, **ERRORS})
    def post(self, request: Request, *args, **kwargs) -> Response:
        """Accorde une dérogation à une famille **ou** un élève : motif et date de fin
        obligatoires ; la famille ou l'élève d'une autre école : 400."""
        data = FeeWaiverInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        # Le gestionnaire de l'école ne rend que ses propres familles et élèves : 404 sinon.
        family = (
            Family.objects.filter(pk=fields["family"]).first() if fields.get("family") else None
        )
        student = (
            Student.objects.filter(pk=fields["student"]).first() if fields.get("student") else None
        )
        if (fields.get("family") and not family) or (fields.get("student") and not student):
            raise NotFound()
        waiver = waivers.grant(
            actor=request.user,
            reason=fields["reason"],
            until=fields["until"],
            family=family,
            student=student,
        )
        return Response(self.get_serializer(waiver).data, status=201)


@extend_schema(tags=["waivers"])
class FeeWaiverLiftView(_View, APIView):
    @extend_schema(request=None, responses={200: FeeWaiverSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Lève une dérogation : le bulletin est de nouveau retenu s'il y a un retard."""
        waiver = get_object_or_404(FeeWaiver.objects.select_related("family", "student"), pk=pk)
        waiver = waivers.lift(waiver, actor=request.user)
        return Response(FeeWaiverSerializer(waiver).data)

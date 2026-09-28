from django.contrib.auth import logout
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import school_access
from apps.core.errors import SCHOOL_NOT_FOUND, ErrorSerializer
from apps.sync import services
from apps.sync.models import Device
from apps.sync.serializers import DeviceRegisterSerializer, DeviceSerializer

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}


class IsSchoolMember(BasePermission):
    """Tout compte qui a une appartenance active dans l'école de l'adresse (pas une session
    support) : chacun gère ses propres appareils."""

    def has_permission(self, request, view) -> bool:
        if request.school is None:
            raise NotFound(SCHOOL_NOT_FOUND.detail, code=SCHOOL_NOT_FOUND.code)
        access = school_access(request)
        return access is not None and access.membership is not None


@extend_schema_view(list=extend_schema(responses={200: DeviceSerializer(many=True), **ERRORS}))
@extend_schema(tags=["sync"])
class MyDeviceViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Mes appareils dans cette école (M4) : enregistrer, reprendre à la connexion, déconnecter."""

    permission_classes = [IsSchoolMember]
    serializer_class = DeviceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Device.all_schools.none()
        return Device.objects.filter(user=self.request.user, revoked_at__isnull=True)

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "current_device": services.session_device(self.request.session, self.request.school),
        }

    @extend_schema(
        request=DeviceRegisterSerializer,
        responses={201: DeviceSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def create(self, request: Request) -> Response:
        """« Se souvenir de cet appareil » : la paire de clés est créée dans le navigateur, seule
        la clé publique est envoyée."""
        serializer = DeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = services.register_device(
            request.school, request.user, request.session, **serializer.validated_data
        )
        return Response(self._data(device), status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: DeviceSerializer, 409: ErrorSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def resume(self, request: Request, pk=None) -> Response:
        """Appareil déjà enregistré : il reprend la session qui vient de s'ouvrir. Déconnecté
        entre-temps : 409 `device_revoked` (le navigateur efface ce qu'il en garde)."""
        device = self._own_device(pk)
        services.resume_device(device, request.school, request.session)
        return Response(self._data(device))

    @extend_schema(request=None, responses={204: None, **ERRORS})
    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk=None) -> Response:
        """« Déconnecter » un de ses appareils : sa session est fermée."""
        device = self.get_object()
        current = services.session_device(request.session, request.school) == str(device.pk)
        services.revoke_device(device, actor=request.user)
        if current:
            logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _own_device(self, pk) -> Device:
        # Révoqués compris : `resume` doit pouvoir répondre « déconnecté ».
        return get_object_or_404(Device.objects.filter(user=self.request.user), pk=pk)

    def _data(self, device: Device) -> dict:
        return DeviceSerializer(device, context=self.get_serializer_context()).data

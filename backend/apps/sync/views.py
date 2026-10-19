from django.contrib.auth import logout
from django.db.models import F, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts import platform_roles as team
from apps.accounts.permissions import (
    HasPlatformPermission,
    HasSchoolPermission,
    ensure_module,
    school_access,
)
from apps.accounts.roles import (
    FINANCE_COLLECT_PAYMENT,
    GRADES_ENTER,
    GRADES_ENTER_ANY,
    GRADES_VALIDATE,
    ROLES_MANAGE,
    STUDENTS_VIEW,
)
from apps.accounts.views import CONSOLE_ERRORS, SchoolViewSet
from apps.core.errors import SCHOOL_NOT_FOUND, ErrorSerializer
from apps.sync import operations, services
from apps.sync.models import Device
from apps.sync.serializers import (
    ConsoleDeviceSerializer,
    DeviceRegisterSerializer,
    DeviceSerializer,
    PullQuerySerializer,
    PullSerializer,
    PushResultSerializer,
    PushSerializer,
    SchoolDeviceSerializer,
    SnapshotQuerySerializer,
    SnapshotSerializer,
)

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
    required_module = "offline"
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
        ensure_module(request.school, self)
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
        return revoke(request, self.get_object())

    def _own_device(self, pk) -> Device:
        # Révoqués compris : `resume` doit pouvoir répondre « déconnecté ».
        return get_object_or_404(Device.objects.filter(user=self.request.user), pk=pk)

    def _data(self, device: Device) -> dict:
        return DeviceSerializer(device, context=self.get_serializer_context()).data


@extend_schema_view(
    list=extend_schema(responses={200: SchoolDeviceSerializer(many=True), **ERRORS})
)
@extend_schema(tags=["sync"])
class SchoolDeviceViewSet(mixins.ListModelMixin, SchoolViewSet):
    """Appareils de l'école (« Appareils et synchro ») : un responsable les voit et en révoque."""

    required_permission = ROLES_MANAGE
    serializer_class = SchoolDeviceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Device.all_schools.none()
        return (
            Device.objects.filter(revoked_at__isnull=True)
            .select_related("user")
            .order_by("-last_seen_at", "prefix")
        )

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "current_device": services.session_device(self.request.session, self.request.school),
        }

    @extend_schema(request=None, responses={204: None, **ERRORS})
    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk=None) -> Response:
        """Révoquer : sa session est fermée, il efface ses données au prochain contact."""
        return revoke(request, self.get_object())


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("search", str, description="Appareil, préfixe, compte ou école."),
            OpenApiParameter("state", str, enum=["active", "revoked"]),
        ],
        responses={200: ConsoleDeviceSerializer(many=True), **CONSOLE_ERRORS},
    )
)
class ConsoleDeviceViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Appareils enregistrés de toutes les écoles (5.4.2) : équipe selon ses droits, à l'adresse de
    la console ; les plus récemment vus d'abord."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.HEALTH_VIEW
    serializer_class = ConsoleDeviceSerializer

    def get_queryset(self):
        devices = Device.all_schools.select_related("school", "user").order_by(
            F("last_seen_at").desc(nulls_last=True), "-created_at"
        )
        if self.action != "list":
            return devices
        params = self.request.query_params
        for word in params.get("search", "").split():
            devices = devices.filter(
                Q(label__icontains=word)
                | Q(prefix__iexact=word)
                | Q(user__last_name__icontains=word)
                | Q(user__middle_name__icontains=word)
                | Q(user__first_name__icontains=word)
                | Q(school__name__icontains=word)
                | Q(school__code__iexact=word)
            )
        state = params.get("state")
        if state == "active":
            devices = devices.filter(revoked_at__isnull=True)
        elif state == "revoked":
            devices = devices.filter(revoked_at__isnull=False)
        return devices

    @extend_schema(request=None, responses={200: ConsoleDeviceSerializer, **CONSOLE_ERRORS})
    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk=None) -> Response:
        """Déconnecter : sa session est fermée, il efface ses données au prochain contact ; noté
        dans le journal de son école et dans celui de la plateforme."""
        device = services.support_revoke_device(self.get_object(), actor=request.user)
        return Response(ConsoleDeviceSerializer(device).data)


def revoke(request: Request, device: Device) -> Response:
    """Révoque l'appareil ; celui de la session en cours la ferme aussi ici."""
    current = services.session_device(request.session, request.school) == str(device.pk)
    services.revoke_device(device, actor=request.user)
    if current:
        logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["sync"])
class SyncViewSet(viewsets.ViewSet):
    """Synchronisation hors ligne (3.3.2), seulement depuis l'appareil enregistré de la session
    (sinon 403 `device_required` ; déconnecté : 409 `device_revoked`, il efface ses données).
    Élèves et, selon les droits, leurs finances (`services.Reader`) ; les notes (8.2.3) passent par
    des opérations seulement."""

    permission_classes = [HasSchoolPermission]
    required_permission = (
        STUDENTS_VIEW,
        FINANCE_COLLECT_PAYMENT,
        GRADES_ENTER,
        GRADES_ENTER_ANY,
        GRADES_VALIDATE,
    )
    required_module = "offline"

    @extend_schema(
        parameters=[SnapshotQuerySerializer],
        responses={200: SnapshotSerializer, 409: ErrorSerializer, **ERRORS},
    )
    @action(detail=False, methods=["get"])
    def snapshot(self, request: Request) -> Response:
        """Premier chargement, par pages d'inscriptions de l'année en cours."""
        device = self._device()
        params = SnapshotQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = services.snapshot(device, self._reader(), request.school, **params.validated_data)
        return Response(SnapshotSerializer(data).data)

    @extend_schema(
        parameters=[PullQuerySerializer],
        responses={200: PullSerializer, 409: ErrorSerializer, **ERRORS},
    )
    @action(detail=False, methods=["get"])
    def pull(self, request: Request) -> Response:
        """Changements depuis `since` ; 409 `snapshot_required` : reprendre un instantané."""
        self._device()
        params = PullQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = services.pull(self._reader(), request.school, **params.validated_data)
        return Response(PullSerializer(data).data)

    @extend_schema(
        request=PushSerializer,
        responses={200: PushResultSerializer, 400: ErrorSerializer, 409: ErrorSerializer, **ERRORS},
    )
    @action(detail=False, methods=["post"])
    def push(self, request: Request) -> Response:
        """Lot d'opérations de l'appareil, dans l'ordre : résultat de chacune par `op_id`."""
        device = self._device()
        body = PushSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        outcomes = operations.push(
            device,
            request.user,
            school_access(request).permissions,
            [operations.Incoming(**item) for item in body.validated_data["operations"]],
            receipt_seq=body.validated_data.get("receipt_seq"),
        )
        return Response(PushResultSerializer({"results": outcomes}).data)

    def _device(self) -> Device:
        return services.sync_device(self.request.session, self.request.school, self.request.user)

    def _reader(self) -> services.Reader:
        return services.Reader.of(self.request.user, school_access(self.request).permissions)

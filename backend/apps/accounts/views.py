from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import services
from apps.accounts.models import Membership, Role
from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import ROLES_MANAGE, sorted_permissions
from apps.accounts.serializers import (
    MeSerializer,
    RoleSerializer,
    StaffCreatedSerializer,
    StaffCreateSerializer,
    StaffSerializer,
    StaffUpdateSerializer,
)
from apps.core.errors import ErrorSerializer

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}


class MeView(APIView):
    """Le compte connecté, ses écoles (choix de l'école) et ses droits dans l'école de l'adresse
    (menu de la Gestion)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer, 403: ErrorSerializer}, tags=["accounts"])
    def get(self, request: Request) -> Response:
        user = request.user
        memberships = (
            Membership.objects.filter(user=user, is_active=True)
            .select_related("school")
            .order_by("school__name")
        )
        access = school_access(request)
        school = None
        if access is not None:
            school = {
                "code": request.school.code,
                "name": request.school.name,
                "roles": access.roles,
                "permissions": sorted_permissions(access.permissions),
            }
        me = {
            "id": user.id,
            "phone": user.phone,
            "last_name": user.last_name,
            "middle_name": user.middle_name,
            "first_name": user.first_name,
            "language": user.language,
            "must_change_password": user.must_change_password,
            "schools": [membership.school for membership in memberships],
            "school": school,
        }
        return Response(MeSerializer(me).data)


class SchoolViewSet(viewsets.GenericViewSet):
    """Point d'API d'une école : permission `required_permission` vérifiée par le serveur."""

    permission_classes = [HasSchoolPermission]
    required_permission: str
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]


@extend_schema_view(
    list=extend_schema(responses={200: RoleSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: RoleSerializer, **ERRORS}),
    create=extend_schema(responses={201: RoleSerializer, 409: ErrorSerializer, **ERRORS}),
    partial_update=extend_schema(responses={200: RoleSerializer, 409: ErrorSerializer, **ERRORS}),
    destroy=extend_schema(responses={204: None, 409: ErrorSerializer, **ERRORS}),
)
@extend_schema(tags=["accounts"])
class RoleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    SchoolViewSet,
):
    """Rôles de l'école : rôles système (renommables, permissions modifiables) et rôles créés par
    l'école (B1 à B2)."""

    serializer_class = RoleSerializer
    required_permission = ROLES_MANAGE

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Role.all_schools.none()
        # Le comptage (GROUP BY) fait oublier l'ordre du modèle : on le redonne.
        return Role.objects.annotate(
            active_member_count=Count("memberships", filter=Q(memberships__is_active=True))
        ).order_by("id")

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.create_role(
            actor=self.request.user,
            name=data.get("name", ""),
            permissions=data.get("permissions", []),
        )

    def perform_update(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.update_role(
            serializer.instance,
            actor=self.request.user,
            name=data.get("name"),
            permissions=data.get("permissions"),
        )

    def perform_destroy(self, instance):
        services.delete_role(instance, actor=self.request.user)


@extend_schema_view(
    list=extend_schema(responses={200: StaffSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: StaffSerializer, **ERRORS}),
)
@extend_schema(tags=["accounts"])
class StaffViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SchoolViewSet):
    """Comptes du personnel de l'école (M3). On ne supprime pas un compte : on le désactive."""

    serializer_class = StaffSerializer
    required_permission = ROLES_MANAGE

    def get_serializer_class(self):
        # Selon la méthode (et non l'action) : l'API navigable affiche ainsi le bon formulaire.
        return {"POST": StaffCreateSerializer, "PATCH": StaffUpdateSerializer}.get(
            self.request.method, StaffSerializer
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Membership.objects.none()
        return (
            Membership.objects.filter(school=self.request.school)
            .select_related("user")
            .prefetch_related("roles")
            .order_by("user__last_name", "user__middle_name", "user__first_name")
        )

    @extend_schema(
        request=StaffCreateSerializer,
        responses={
            201: StaffCreatedSerializer,
            400: ErrorSerializer,
            409: ErrorSerializer,
            **ERRORS,
        },
    )
    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership, temporary_password = services.add_staff_member(
            actor=request.user, **serializer.validated_data
        )
        data = {
            **StaffSerializer(membership).data,
            "existing_account": temporary_password is None,
            "temporary_password": temporary_password,
        }
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=StaffUpdateSerializer,
        responses={200: StaffSerializer, 409: ErrorSerializer, **ERRORS},
    )
    def partial_update(self, request: Request, pk=None) -> Response:
        membership = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_staff_member(membership, actor=request.user, **serializer.validated_data)
        return Response(StaffSerializer(self.get_object()).data)

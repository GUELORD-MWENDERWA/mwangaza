from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.roles import AUDIT_VIEW
from apps.accounts.views import ERRORS, SchoolViewSet
from apps.audit.models import AuditLog
from apps.audit.serializers import (
    AuditActorSerializer,
    AuditLogFilterSerializer,
    AuditLogSerializer,
)


@extend_schema_view(
    list=extend_schema(
        parameters=[AuditLogFilterSerializer],
        responses={200: AuditLogSerializer(many=True), **ERRORS},
    ),
    retrieve=extend_schema(
        description="Une entrée du journal d'audit de l'école.",
        responses={200: AuditLogSerializer, **ERRORS},
    ),
)
@extend_schema(tags=["audit"])
class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SchoolViewSet):
    """Journal d'audit de l'école (M6), le plus récent d'abord ; en lecture seule."""

    serializer_class = AuditLogSerializer
    required_permission = AUDIT_VIEW
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AuditLog.all_schools.none()
        queryset = AuditLog.objects.select_related("actor")
        if self.action == "list":
            queryset = self._filter(queryset)
        return queryset

    def _filter(self, queryset):
        params = AuditLogFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        if "actor" in data:
            queryset = queryset.filter(actor_id=data["actor"])
        if "action" in data:
            queryset = queryset.filter(action=data["action"])
        if "domain" in data:
            queryset = queryset.filter(action__startswith=f"{data['domain']}.")
        if "entity" in data:
            queryset = queryset.filter(entity_id=data["entity"])
        # `__date` : jour dans le fuseau du serveur (Goma, `TIME_ZONE`).
        if "since" in data:
            queryset = queryset.filter(created_at__date__gte=data["since"])
        if "until" in data:
            queryset = queryset.filter(created_at__date__lte=data["until"])
        if data.get("search"):
            queryset = queryset.filter(entity_label__icontains=data["search"])
        return queryset

    @extend_schema(responses={200: AuditActorSerializer(many=True), **ERRORS})
    @action(detail=False, methods=["get"], pagination_class=None)
    def actors(self, request: Request) -> Response:
        """Les personnes qui apparaissent dans le journal de l'école (filtre « Personne » de M6),
        sans le support Mwangaza."""
        logs = AuditLog.objects.filter(actor__isnull=False, impersonated_by__isnull=True)
        users = (
            User.objects.filter(pk__in=logs.values("actor"))
            .exclude(is_platform_admin=True)
            .order_by("last_name", "middle_name", "first_name")
        )
        return Response(AuditActorSerializer(users, many=True).data)

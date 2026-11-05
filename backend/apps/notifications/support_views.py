"""Demandes d'aide (SUP.1) : côté école, chaque membre écrit et lit **ses** demandes ; côté
console, l'équipe qui a le droit `platform.support.handle` répond."""

from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts import console_mode
from apps.accounts import platform_roles as team
from apps.accounts.models import User
from apps.accounts.permissions import HasPlatformPermission, HasSchoolAccess, school_access
from apps.core.errors import ErrorSerializer
from apps.notifications import support
from apps.notifications.models import SupportReply, SupportRequest

ERRORS = {
    400: ErrorSerializer,
    403: ErrorSerializer,
    404: ErrorSerializer,
    409: ErrorSerializer,
    429: ErrorSerializer,
}
Status = SupportRequest.Status


class SupportPagination(PageNumberPagination):
    page_size = 25


class SupportReplySerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportReply
        fields = ["id", "from_platform", "author_name", "body", "created_at"]
        read_only_fields = fields

    def get_author_name(self, reply: SupportReply) -> str:
        # La plateforme se présente par son prénom : « Patrick · Support ».
        return (
            reply.author.first_name or reply.author.last_name
            if reply.from_platform
            else (reply.author.get_full_name())
        )


class SupportRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportRequest
        fields = [
            "id",
            "number",
            "subject",
            "screen",
            "status",
            "last_activity_at",
            "created_at",
            "closed_at",
        ]
        read_only_fields = fields


class SupportRequestDetailSerializer(SupportRequestSerializer):
    app_version = serializers.CharField(read_only=True)
    device = serializers.CharField(read_only=True)
    replies = SupportReplySerializer(many=True, read_only=True)

    class Meta(SupportRequestSerializer.Meta):
        fields = [*SupportRequestSerializer.Meta.fields, "app_version", "device", "replies"]
        read_only_fields = fields


class SupportRequestCreateSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=120)
    body = serializers.CharField(max_length=5000)
    screen = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    app_version = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    device = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class SupportReplyCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)


@extend_schema(tags=["help"])
@extend_schema_view(
    list=extend_schema(responses={200: SupportRequestSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: SupportRequestDetailSerializer, **ERRORS}),
)
class SupportRequestViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Mes demandes d'aide à la plateforme, l'activité la plus récente d'abord (SUP.1). Tout
    membre du personnel écrit ; il ne voit jamais celles d'un collègue. Ouvert aussi quand
    l'école est en lecture seule (c'est justement là qu'on a besoin d'aide) ; fermé pendant une
    session support (aucun compte propre)."""

    permission_classes = [HasSchoolAccess]
    serializer_class = SupportRequestSerializer
    pagination_class = SupportPagination

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if school_access(request).membership is None:
            raise PermissionDenied

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SupportRequest.all_schools.none()
        return support.with_thread(support.mine(self.request.user))

    def get_serializer_class(self):
        return (
            SupportRequestDetailSerializer
            if self.action == "retrieve"
            else super().get_serializer_class()
        )

    @extend_schema(
        request=SupportRequestCreateSerializer,
        responses={201: SupportRequestDetailSerializer, **ERRORS},
    )
    def create(self, request: Request) -> Response:
        """Envoie une demande (10 par jour et par compte) ; la plateforme en est prévenue."""
        form = SupportRequestCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        created = support.open_request(request.school, user=request.user, **form.validated_data)
        created = support.with_thread(SupportRequest.objects.filter(pk=created.pk)).get()
        return Response(
            SupportRequestDetailSerializer(created).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=SupportReplyCreateSerializer, responses={201: SupportReplySerializer, **ERRORS}
    )
    @action(detail=True, methods=["post"])
    def reply(self, request: Request, pk=None) -> Response:
        """Répond dans le fil ; rouvre une demande fermée depuis moins de 30 jours."""
        form = SupportReplyCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        reply = support.reply_as_school(
            self.get_object(), user=request.user, body=form.validated_data["body"]
        )
        return Response(SupportReplySerializer(reply).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: SupportRequestSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk=None) -> Response:
        """« C'est réglé » : ferme la demande."""
        closed = support.close_as_school(self.get_object())
        return Response(SupportRequestSerializer(closed).data)


# --- Console --------------------------------------------------------------------------------


class ConsoleSupportRequestSerializer(SupportRequestSerializer):
    school = serializers.SlugRelatedField(slug_field="code", read_only=True)
    school_id = serializers.UUIDField(read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True)
    author_name = serializers.SerializerMethodField()
    assignee = serializers.UUIDField(source="assignee_id", allow_null=True, read_only=True)
    assignee_name = serializers.SerializerMethodField()

    class Meta(SupportRequestSerializer.Meta):
        fields = [
            *SupportRequestSerializer.Meta.fields,
            "school",
            "school_id",
            "school_name",
            "author_name",
            "assignee",
            "assignee_name",
        ]
        read_only_fields = fields

    def get_author_name(self, item: SupportRequest) -> str:
        return item.created_by.get_full_name() if item.created_by else ""

    def get_assignee_name(self, item: SupportRequest) -> str:
        return item.assignee.get_full_name() if item.assignee else ""


class ConsoleSupportRequestDetailSerializer(ConsoleSupportRequestSerializer):
    phone = serializers.CharField(read_only=True)
    app_version = serializers.CharField(read_only=True)
    device = serializers.CharField(read_only=True)
    replies = SupportReplySerializer(many=True, read_only=True)

    class Meta(ConsoleSupportRequestSerializer.Meta):
        fields = [
            *ConsoleSupportRequestSerializer.Meta.fields,
            "phone",
            "app_version",
            "device",
            "replies",
        ]
        read_only_fields = fields


class SupportCountsSerializer(serializers.Serializer):
    todo = serializers.IntegerField()
    waiting = serializers.IntegerField()
    closed = serializers.IntegerField()


class SupportAssignSerializer(serializers.Serializer):
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), allow_null=True)


class SupportAssigneeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField(source="get_full_name")


STATES = {"todo": Status.OPEN, "waiting": Status.ANSWERED, "closed": Status.CLOSED}


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("state", str, enum=[*STATES, "all"]),
            OpenApiParameter("school", str, description="Code de l'école."),
            OpenApiParameter("mine", bool, description="Seulement celles qui me sont confiées."),
            OpenApiParameter("q", str, description="Numéro, sujet ou école."),
        ],
        responses={200: ConsoleSupportRequestSerializer(many=True), **ERRORS},
    ),
    retrieve=extend_schema(responses={200: ConsoleSupportRequestDetailSerializer, **ERRORS}),
)
class ConsoleSupportRequestViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Demandes d'aide de toutes les écoles du mode de la console (réel : espaces réels et essais ;
    démonstration : démonstrations). « À traiter » : la plus ancienne en attente d'abord."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.SUPPORT_HANDLE
    serializer_class = ConsoleSupportRequestSerializer
    pagination_class = SupportPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SupportRequest.all_schools.none()
        items = support.queue(console_mode.list_environments(self.request))
        if self.action != "list":
            return items.prefetch_related(
                Prefetch("replies", queryset=SupportReply.all_schools.select_related("author"))
            )
        params = self.request.query_params
        state = params.get("state", "todo")
        if state in STATES:
            items = items.filter(status=STATES[state])
        if params.get("school"):
            items = items.filter(school__code=params["school"])
        if params.get("mine") in ("1", "true"):
            items = items.filter(assignee=self.request.user)
        if q := params.get("q", "").strip():
            query = Q(subject__icontains=q) | Q(school__name__icontains=q)
            if q.lstrip("#").isdigit():
                query |= Q(number=int(q.lstrip("#")))
            items = items.filter(query)
        # À traiter : la plus ancienne attente en tête ; le reste, l'activité la plus récente.
        return (
            items.order_by("last_activity_at")
            if state == "todo"
            else items.order_by("-last_activity_at")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ConsoleSupportRequestDetailSerializer
        return super().get_serializer_class()

    @extend_schema(responses={200: SupportCountsSerializer, **ERRORS})
    @action(detail=False, methods=["get"], pagination_class=None)
    def counts(self, request: Request) -> Response:
        """Nombre de demandes par état (compteur du menu et des onglets)."""
        items = support.queue(console_mode.list_environments(request))
        by_status = dict(items.values_list("status").annotate(n=Count("id")).order_by())
        return Response(
            {
                "todo": by_status.get(Status.OPEN, 0),
                "waiting": by_status.get(Status.ANSWERED, 0),
                "closed": by_status.get(Status.CLOSED, 0),
            }
        )

    @extend_schema(responses={200: SupportAssigneeSerializer(many=True), **ERRORS})
    @action(detail=False, methods=["get"], pagination_class=None)
    def assignees(self, request: Request) -> Response:
        """Membres de l'équipe à qui confier une demande."""
        return Response(SupportAssigneeSerializer(support.assignees(), many=True).data)

    @extend_schema(
        request=SupportReplyCreateSerializer, responses={201: SupportReplySerializer, **ERRORS}
    )
    @action(detail=True, methods=["post"])
    def reply(self, request: Request, pk=None) -> Response:
        """Répond à l'auteur : « en attente de l'école », avec une notification."""
        form = SupportReplyCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        reply = support.reply_as_platform(
            self.get_object(), actor=request.user, body=form.validated_data["body"]
        )
        return Response(SupportReplySerializer(reply).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: ConsoleSupportRequestSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk=None) -> Response:
        closed = support.close_as_platform(self.get_object(), actor=request.user)
        return Response(ConsoleSupportRequestSerializer(closed).data)

    @extend_schema(
        request=SupportAssignSerializer, responses={200: ConsoleSupportRequestSerializer, **ERRORS}
    )
    @action(detail=True, methods=["post"])
    def assign(self, request: Request, pk=None) -> Response:
        """Confie la demande à un membre de l'équipe (ou la libère avec `null`)."""
        form = SupportAssignSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        item = support.assign(
            self.get_object(), actor=request.user, assignee=form.validated_data["assignee"]
        )
        return Response(ConsoleSupportRequestSerializer(item).data)

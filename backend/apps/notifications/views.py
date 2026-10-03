from django.db.models import Count, Prefetch
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasSchoolAccess, IsPlatformAdmin, school_access
from apps.accounts.roles import ANNOUNCEMENTS_PUBLISH
from apps.accounts.views import SchoolViewSet
from apps.core.errors import ApiError, ErrorSerializer
from apps.notifications import platform, services
from apps.notifications.attachments import attachment_response
from apps.notifications.models import Announcement, PlatformAnnouncement
from apps.notifications.serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    ConsolePlatformAnnouncementCreateSerializer,
    ConsolePlatformAnnouncementSerializer,
    PlatformNewsReadSerializer,
    PlatformNewsSerializer,
    RecipientsQuerySerializer,
    RecipientsSerializer,
)
from apps.schools.models import ClassGroup, School

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
NO_ATTACHMENT = ApiError("no_attachment", _("This announcement has no attachment."), 404)


@extend_schema_view(
    list=extend_schema(responses={200: AnnouncementSerializer(many=True), **ERRORS}),
    create=extend_schema(
        request={"multipart/form-data": AnnouncementCreateSerializer},
        responses={201: AnnouncementSerializer, 400: ErrorSerializer, **ERRORS},
    ),
)
@extend_schema(tags=["announcements"])
class AnnouncementViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, SchoolViewSet):
    """Annonces de l'école aux familles (H4), les plus récentes d'abord : publiées tout de suite,
    jamais modifiées, seulement archivées (retirées du portail)."""

    required_permission = ANNOUNCEMENTS_PUBLISH
    serializer_class = AnnouncementSerializer
    http_method_names = ["get", "post", "head", "options"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Announcement.all_schools.none()
        groups = ClassGroup.objects.select_related("level", "track")
        return (
            Announcement.objects.select_related("created_by")
            .prefetch_related(Prefetch("class_groups", queryset=groups))
            .annotate(read_by=Count("reads"))
            .order_by("-published_at", "-id")  # GROUP BY : l'ordre du modèle ne compte plus
        )

    def get_serializer_class(self):
        if self.action == "create":
            return AnnouncementCreateSerializer
        return AnnouncementSerializer

    def _announcement(self, announcement: Announcement, code=status.HTTP_200_OK) -> Response:
        announcement = self.get_queryset().get(pk=announcement.pk)
        return Response(AnnouncementSerializer(announcement).data, status=code)

    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = services.publish(actor=request.user, **serializer.validated_data)
        return self._announcement(announcement, status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: AnnouncementSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk=None) -> Response:
        """Retire l'annonce du portail des familles."""
        announcement = services.archive(self.get_object(), actor=request.user)
        return self._announcement(announcement)

    @extend_schema(
        responses={
            (200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY, description="PDF."),
            **ERRORS,
        },
    )
    @action(detail=True, methods=["get"])
    def attachment(self, request: Request, pk=None):
        """PDF joint à l'annonce, jamais public."""
        response = attachment_response(self.get_object())
        if response is None:
            return Response(NO_ATTACHMENT.body(), status=NO_ATTACHMENT.status)
        return response

    @extend_schema(
        parameters=[RecipientsQuerySerializer],
        responses={200: RecipientsSerializer, 400: ErrorSerializer, **ERRORS},
    )
    @action(detail=False, methods=["get"])
    def recipients(self, request: Request) -> Response:
        """Nombre de familles qu'une annonce toucherait (« Publier pour 156 familles »)."""
        query = RecipientsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        families = services.recipient_families(
            query.validated_data["audience"], query.validated_data.get("class_groups", [])
        )
        return Response(RecipientsSerializer({"families": families.count()}).data)


CONSOLE_ERRORS = {400: ErrorSerializer, **ERRORS}


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(
        responses={200: ConsolePlatformAnnouncementSerializer(many=True), **CONSOLE_ERRORS}
    ),
    create=extend_schema(
        request=ConsolePlatformAnnouncementCreateSerializer,
        responses={201: ConsolePlatformAnnouncementSerializer, **CONSOLE_ERRORS},
    ),
)
class ConsolePlatformAnnouncementViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Annonces de la plateforme aux écoles (5.4.3), les plus récentes d'abord : super-admin
    seulement, à l'adresse de la console. Publiées tout de suite, jamais modifiées, seulement
    archivées ; chaque publication et archivage va dans le journal de la plateforme."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = ConsolePlatformAnnouncementSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        schools = Prefetch("schools", queryset=School.objects.order_by("name"))
        return (
            PlatformAnnouncement.objects.select_related("created_by")
            .prefetch_related(schools)
            .annotate(read_by=Count("reads"))
            .order_by("-published_at", "-id")  # GROUP BY : l'ordre du modèle ne compte plus
        )

    def _announcement(self, announcement, code=status.HTTP_200_OK) -> Response:
        announcement = self.get_queryset().get(pk=announcement.pk)
        return Response(ConsolePlatformAnnouncementSerializer(announcement).data, status=code)

    def create(self, request: Request) -> Response:
        serializer = ConsolePlatformAnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = platform.publish(actor=request.user, **serializer.validated_data)
        return self._announcement(announcement, status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: ConsolePlatformAnnouncementSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk=None) -> Response:
        """Retire l'annonce de la Gestion des écoles."""
        announcement = platform.archive(self.get_object(), actor=request.user)
        return self._announcement(announcement)


@extend_schema(tags=["announcements"])
@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("unread", bool, description="Seulement les non lues.")],
        responses={200: PlatformNewsSerializer(many=True), **ERRORS},
    )
)
class PlatformNewsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Annonces de la plateforme que lit le personnel de l'école (5.4.3) : bandeau et liste de la
    Gestion, les plus récentes d'abord. Tout compte de l'école les lit ; « lue » est noté par
    compte (rien pendant une session support)."""

    permission_classes = [HasSchoolAccess]
    serializer_class = PlatformNewsSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PlatformAnnouncement.objects.none()
        announcements = platform.for_school(self.request.school, self.request.user)
        if self.request.query_params.get("unread") in ("1", "true"):
            announcements = announcements.filter(is_read=False)
        return announcements

    @extend_schema(request=PlatformNewsReadSerializer, responses={204: None, **ERRORS})
    @action(detail=False, methods=["post"])
    def read(self, request: Request) -> Response:
        """Noter des annonces comme lues par ce compte (bandeau fermé, liste ouverte)."""
        serializer = PlatformNewsReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if school_access(request).membership is not None:
            platform.mark_read(request.school, request.user, serializer.validated_data["ids"])
        return Response(status=status.HTTP_204_NO_CONTENT)

from django.db.models import Prefetch
from django.http import FileResponse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.roles import ANNOUNCEMENTS_PUBLISH
from apps.accounts.views import SchoolViewSet
from apps.core.errors import ApiError, ErrorSerializer
from apps.notifications import services
from apps.notifications.models import Announcement
from apps.notifications.serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    RecipientsQuerySerializer,
    RecipientsSerializer,
)
from apps.schools.models import ClassGroup

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
        return Announcement.objects.select_related("created_by").prefetch_related(
            Prefetch("class_groups", queryset=groups)
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
        announcement = self.get_object()
        if not announcement.attachment:
            return Response(NO_ATTACHMENT.body(), status=NO_ATTACHMENT.status)
        try:
            file = announcement.attachment.open("rb")
        except FileNotFoundError:
            return Response(NO_ATTACHMENT.body(), status=NO_ATTACHMENT.status)
        filename = f"{slugify(announcement.title)[:60] or 'annonce'}.pdf"
        response = FileResponse(file, content_type="application/pdf", filename=filename)
        response["Content-Disposition"] = response["Content-Disposition"].replace(
            "attachment", "inline", 1
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=86400"
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

from pathlib import Path

from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import SCHOOL_CONFIGURE
from apps.core.errors import SCHOOL_NOT_FOUND, ApiError, ErrorSerializer
from apps.schools import services
from apps.schools.logos import CONTENT_TYPES
from apps.schools.models import School
from apps.schools.serializers import (
    CurrentSchoolSerializer,
    LogoUploadSerializer,
    SchoolSettingsSerializer,
)

NO_LOGO = ApiError("no_logo", _("This school has no logo."), 404)
ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}


@extend_schema(responses={200: CurrentSchoolSerializer, 404: ErrorSerializer}, tags=["schools"])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def current_school(request: Request) -> Response:
    """École du sous-domaine (public : l'écran de connexion affiche son nom, sa couleur, son
    logo)."""
    if request.school is None:
        return Response(SCHOOL_NOT_FOUND.body(), status=SCHOOL_NOT_FOUND.status)
    return Response(CurrentSchoolSerializer(request.school).data)


@require_GET
def school_logo(request: HttpRequest) -> HttpResponse:
    """Logo de l'école de l'adresse (public : écran de connexion). Hors de l'API typée : c'est
    une image. Un SVG ne peut rien exécuter, même ouvert seul dans le navigateur."""
    school = request.school
    if school is None:
        return JsonResponse(SCHOOL_NOT_FOUND.body(), status=SCHOOL_NOT_FOUND.status)
    if not school.logo:
        return JsonResponse(NO_LOGO.body(), status=NO_LOGO.status)
    try:
        file = school.logo.open("rb")
    except FileNotFoundError:
        return JsonResponse(NO_LOGO.body(), status=NO_LOGO.status)
    kind = Path(school.logo.name).suffix.removeprefix(".")
    response = FileResponse(file, content_type=CONTENT_TYPES.get(kind, "application/octet-stream"))
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    # L'adresse donnée par l'API change avec chaque logo.
    response["Cache-Control"] = "public, max-age=86400"
    return response


class _SchoolSettingsBase(APIView):
    permission_classes = [HasSchoolPermission]
    required_permission = SCHOOL_CONFIGURE

    def school(self) -> School:
        return School.objects.get(pk=self.request.school.pk)

    def settings_response(self, school: School) -> Response:
        return Response(SchoolSettingsSerializer(school).data)


@extend_schema(tags=["schools"])
class SchoolSettingsView(_SchoolSettingsBase):
    """Paramètres de l'école de l'adresse (M5) : nom, nom officiel, couleur (texte lisible
    vérifié, Q8), fuseau horaire, devises. Chaque changement va dans le journal de l'école."""

    serializer_class = SchoolSettingsSerializer

    @extend_schema(responses={200: SchoolSettingsSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        return self.settings_response(self.school())

    @extend_schema(
        request=SchoolSettingsSerializer,
        responses={200: SchoolSettingsSerializer, **ERRORS},
    )
    def patch(self, request: Request) -> Response:
        school = self.school()
        serializer = SchoolSettingsSerializer(school, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_school(school, actor=request.user, **serializer.validated_data)
        return self.settings_response(school)


@extend_schema(tags=["schools"])
class SchoolLogoView(_SchoolSettingsBase):
    """Logo de l'école (M5) : PNG, JPEG ou SVG, 1 Mo au plus."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = LogoUploadSerializer

    @extend_schema(
        request={"multipart/form-data": LogoUploadSerializer},
        responses={200: SchoolSettingsSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = LogoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = self.school()
        services.update_school(school, actor=request.user, logo=serializer.validated_data["logo"])
        return self.settings_response(school)

    @extend_schema(request=None, responses={200: SchoolSettingsSerializer, **ERRORS})
    def delete(self, request: Request) -> Response:
        school = self.school()
        services.update_school(school, actor=request.user, logo=None)
        return self.settings_response(school)

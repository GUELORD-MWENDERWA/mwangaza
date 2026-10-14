"""Identité de la plateforme (5.1), publique et lisible à toute adresse : école (même suspendue
ou inconnue : l'écran le dit avec le contact du support), portail, administration."""

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsPlatformAdmin
from apps.core import services
from apps.core.errors import ErrorSerializer
from apps.core.http import serve_image
from apps.core.models import PlatformSettings
from apps.core.platform import png_size
from apps.core.serializers import (
    ConsolePlatformSerializer,
    PlatformIconUploadSerializer,
    PlatformLogoUploadSerializer,
    PlatformSerializer,
)

# Application installable : adresse de départ, portée et icônes par défaut (le symbole, dans
# son build).
APPS = {
    "gestion": {"start_url": "/app/", "icons": "/app/icons/"},
    "portail": {"start_url": "/", "icons": "/icons/"},
}
# Couleurs du design (fond de l'écran de démarrage, barre du système) : pas celles de la plateforme.
BACKGROUND = "#F4F2EF"
THEME = "#2B2724"


@extend_schema(responses={200: PlatformSerializer}, tags=["platform"])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def platform_identity(request: Request) -> Response:
    """Nom, logo, couleurs, contact du support et mentions légales de la plateforme."""
    return Response(PlatformSerializer(PlatformSettings.load()).data)


def _image(field: str) -> HttpResponse:
    response = serve_image(getattr(PlatformSettings.load(), field))
    if response is None:
        raise Http404
    return response


@require_GET
def platform_logo(request: HttpRequest) -> HttpResponse:
    return _image("logo")


@require_GET
def platform_icon(request: HttpRequest) -> HttpResponse:
    """Icône téléversée par la plateforme ; sans elle, `?app=` renvoie vers l'icône par défaut
    de cette application (notifications envoyées au téléphone)."""
    app = APPS.get(request.GET.get("app", ""))
    if app and not PlatformSettings.load().icon:
        return HttpResponseRedirect(f"{app['icons']}icon-192.png")
    return _image("icon")


def _icons(platform: PlatformSettings, default: str) -> list[dict]:
    if platform.icon:
        try:
            with platform.icon.open("rb") as file:
                size = png_size(file)
        except OSError:
            size = None
        if size:
            sizes = f"{size[0]}x{size[1]}"
            return [{"src": platform.icon_url, "sizes": sizes, "type": "image/png"}]
    return [
        {"src": f"{default}icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": f"{default}icon-512.png", "sizes": "512x512", "type": "image/png"},
        {
            "src": f"{default}icon-maskable-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable",
        },
    ]


@require_GET
def platform_manifest(request: HttpRequest, app: str) -> HttpResponse:
    """Manifeste d'une application (`gestion`, `portail`) : son nom et son icône viennent des
    paramètres de la plateforme. Relu à chaque visite (le nom peut changer)."""
    if app not in APPS:
        raise Http404
    platform = PlatformSettings.load()
    name = platform.name
    if app == "portail":
        name = _("%(platform)s — Parents") % {"platform": platform.name}
    manifest = {
        "name": name,
        "short_name": platform.short_name,
        "lang": get_language(),
        "start_url": APPS[app]["start_url"],
        "scope": APPS[app]["start_url"],
        "display": "standalone",
        "background_color": BACKGROUND,
        "theme_color": THEME,
        "icons": _icons(platform, APPS[app]["icons"]),
    }
    response = JsonResponse(manifest, content_type="application/manifest+json")
    response["Cache-Control"] = "no-cache"
    return response


# Console de la plateforme (5.2.2) : super-admin seulement, à l'adresse de la console ; ailleurs,
# ces points d'API n'existent pas (404).
CONSOLE_ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


def _console_response() -> Response:
    return Response(ConsolePlatformSerializer(PlatformSettings.load()).data)


@extend_schema(tags=["console"])
class ConsolePlatformView(APIView):
    """Identité de la plateforme : nom, nom court, couleurs, support, mentions légales, et les
    dernières modifications. Chaque changement va dans le journal de la plateforme."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = ConsolePlatformSerializer

    @extend_schema(responses={200: ConsolePlatformSerializer, **CONSOLE_ERRORS})
    def get(self, request: Request) -> Response:
        return _console_response()

    @extend_schema(
        request=ConsolePlatformSerializer,
        responses={200: ConsolePlatformSerializer, **CONSOLE_ERRORS},
    )
    def patch(self, request: Request) -> Response:
        serializer = ConsolePlatformSerializer(
            PlatformSettings.load(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        services.update_platform(actor=request.user, **serializer.validated_data)
        return _console_response()


@extend_schema(tags=["console"])
class ConsolePlatformLogoView(APIView):
    """Logo de la plateforme : PNG ou JPEG (ré-encodé), ou SVG sans script, 1 Mo au plus ; sans
    lui, la lampe."""

    permission_classes = [IsPlatformAdmin]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = PlatformLogoUploadSerializer
    field = "logo"

    @extend_schema(
        request={"multipart/form-data": PlatformLogoUploadSerializer},
        responses={200: ConsolePlatformSerializer, **CONSOLE_ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_platform(actor=request.user, **serializer.validated_data)
        return _console_response()

    @extend_schema(request=None, responses={200: ConsolePlatformSerializer, **CONSOLE_ERRORS})
    def delete(self, request: Request) -> Response:
        services.update_platform(actor=request.user, **{self.field: None})
        return _console_response()


@extend_schema(tags=["console"])
class ConsolePlatformIconView(ConsolePlatformLogoView):
    """Icône des applications (écran d'accueil, onglet) : PNG carré de 512 à 2 048 pixels de
    côté, 1 Mo au plus ; sans elle, l'icône de la lampe."""

    serializer_class = PlatformIconUploadSerializer
    field = "icon"

    @extend_schema(
        request={"multipart/form-data": PlatformIconUploadSerializer},
        responses={200: ConsolePlatformSerializer, **CONSOLE_ERRORS},
    )
    def post(self, request: Request) -> Response:
        return super().post(request)

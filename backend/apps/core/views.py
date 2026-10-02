"""Identité de la plateforme (5.1), publique et lisible à toute adresse : école (même suspendue
ou inconnue : l'écran le dit avec le contact du support), portail, administration."""

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.http import serve_image
from apps.core.models import PlatformSettings
from apps.core.platform import png_size
from apps.core.serializers import PlatformSerializer

# Application installable : adresse de départ, portée et icônes par défaut (lampe, dans son build).
APPS = {
    "gestion": {"start_url": "/app/", "icons": "/app/icons/"},
    "portail": {"start_url": "/", "icons": "/icons/"},
}
# Couleurs du design (fond de l'écran de démarrage, barre du système) : pas celles de la plateforme.
BACKGROUND = "#F3F5F6"
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

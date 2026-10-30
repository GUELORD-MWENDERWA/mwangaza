"""Identité de la plateforme (5.1), publique et lisible à toute adresse : école (même suspendue
ou inconnue : l'écran le dit avec le contact du support), portail, administration."""

from pathlib import Path

from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import platform_roles as team
from apps.accounts.permissions import HasPlatformPermission
from apps.core import markdown, services, site_content
from apps.core.errors import ErrorSerializer
from apps.core.http import serve_image
from apps.core.images import PHOTO_WIDTHS
from apps.core.models import (
    Article,
    DemoRequest,
    Partner,
    PlatformSettings,
    ReferenceSchool,
    SiteBanner,
    SiteEntry,
    SitePage,
    SitePhoto,
    SitePlan,
    Testimonial,
)
from apps.core.platform import png_size
from apps.core.serializers import (
    ArticleCountsSerializer,
    ArticlePreviewSerializer,
    ConsoleArticleSerializer,
    ConsoleDemoRequestSerializer,
    ConsolePartnerSerializer,
    ConsolePlanSerializer,
    ConsolePlatformSerializer,
    ConsoleReferenceSchoolSerializer,
    ConsoleSiteBannerSerializer,
    ConsoleSiteEntrySerializer,
    ConsoleSitePageSerializer,
    ConsoleSitePhotoSerializer,
    ConsoleSocialLinksSerializer,
    ConsoleTestimonialSerializer,
    PlatformIconUploadSerializer,
    PlatformLogoUploadSerializer,
    PlatformSerializer,
    SiteEntryMoveSerializer,
)

# Application installable : adresse de départ, portée et icônes par défaut (le symbole, dans
# son build).
APPS = {
    "gestion": {"start_url": "/app/", "icons": "/app/icons/"},
    "portail": {"start_url": "/", "icons": "/icons/"},
}
# Fond de l'écran de démarrage (design) ; la barre du système prend la couleur principale de la
# plateforme, celle de ses barres (lot 1, marque).
BACKGROUND = "#F3F5F9"


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
        return HttpResponseRedirect(f"{app['icons']}symbole-192.png")
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
        {"src": f"{default}symbole-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": f"{default}symbole-512.png", "sizes": "512x512", "type": "image/png"},
        {
            "src": f"{default}symbole-maskable-512.png",
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
        "theme_color": platform.primary_color,
        "icons": _icons(platform, APPS[app]["icons"]),
    }
    response = JsonResponse(manifest, content_type="application/manifest+json")
    response["Cache-Control"] = "no-cache"
    return response


# Console de la plateforme (5.2.2) : équipe selon ses droits, à la console ; ailleurs,
# ces points d'API n'existent pas (404).
CONSOLE_ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


def _console_response() -> Response:
    return Response(ConsolePlatformSerializer(PlatformSettings.load()).data)


@extend_schema(tags=["console"])
class ConsolePlatformView(APIView):
    """Identité de la plateforme : nom, nom court, couleurs, support, mentions légales, et les
    dernières modifications. Chaque changement va dans le journal de la plateforme."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.IDENTITY_EDIT
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

    permission_classes = [HasPlatformPermission]
    platform_permission = team.IDENTITY_EDIT
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


class DemoRequestPagination(PageNumberPagination):
    page_size = 20


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("status", str, enum=DemoRequest.Status.values)],
        responses={200: ConsoleDemoRequestSerializer(many=True), **CONSOLE_ERRORS},
    ),
    partial_update=extend_schema(responses={200: ConsoleDemoRequestSerializer, **CONSOLE_ERRORS}),
    destroy=extend_schema(responses={204: None, **CONSOLE_ERRORS}),
)
class ConsoleDemoRequestViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Demandes de démonstration envoyées par le site public (WEB.1d), les plus récentes
    d'abord : équipe selon ses droits, à la console. On change le suivi et la note
    interne ; on efface une demande quand la personne le demande (sinon : seule après un an)."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.LEADS_MANAGE
    serializer_class = ConsoleDemoRequestSerializer
    pagination_class = DemoRequestPagination
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        requests = DemoRequest.objects.all()
        status = self.request.query_params.get("status")
        if self.action == "list" and status in DemoRequest.Status.values:
            requests = requests.filter(status=status)
        return requests


class OrderedSiteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Liste courte et ordonnée du site public (questions, témoignages, écoles de référence) :
    toute la liste en une page, brouillons compris, dans l'ordre du site. Chaque changement va
    au journal de la plateforme ; le site le montre tout de suite."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.SITE_EDIT
    pagination_class = None
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer) -> None:
        serializer.instance = services.create_ordered(
            self.queryset.model, actor=self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer) -> None:
        serializer.instance = services.update_ordered(
            serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance) -> None:
        services.delete_ordered(instance, actor=self.request.user)

    @action(detail=True, methods=["post"])
    def move(self, request: Request, pk=None) -> Response:
        """Monte ou descend d'un rang ; renvoie la liste dans le nouvel ordre."""
        item = self.get_object()
        serializer = SiteEntryMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.move_ordered(
            item, actor=request.user, up=serializer.validated_data["direction"] == "up"
        )
        return Response(self.get_serializer(services.ordered_siblings(item), many=True).data)


def _ordered_schema(serializer):
    return extend_schema_view(
        list=extend_schema(responses={200: serializer(many=True), **CONSOLE_ERRORS}),
        create=extend_schema(responses={201: serializer, **CONSOLE_ERRORS}),
        partial_update=extend_schema(responses={200: serializer, **CONSOLE_ERRORS}),
        destroy=extend_schema(responses={204: None, **CONSOLE_ERRORS}),
        move=extend_schema(
            request=SiteEntryMoveSerializer,
            responses={200: serializer(many=True), **CONSOLE_ERRORS},
        ),
    )


def _consent_response(file, name: str) -> HttpResponse:
    """Accord écrit, toujours téléchargé (jamais ouvert dans une page de la console)."""
    if not file:
        raise Http404
    try:
        content = file.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    extension = Path(file.name).suffix
    response = FileResponse(content, as_attachment=True, filename=f"{slugify(name)}{extension}")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


CONSENT_RESPONSE = {
    (200, "application/octet-stream"): OpenApiResponse(
        OpenApiTypes.BINARY, description="PDF, JPEG ou PNG."
    ),
    **CONSOLE_ERRORS,
}


@extend_schema(tags=["console"])
@_ordered_schema(ConsoleSiteEntrySerializer)
class ConsoleSiteEntryViewSet(OrderedSiteViewSet):
    """Contenus du site public (SITE.1a) : questions de l'accueil et des parents, « Prochainement »,
    brouillons compris, dans l'ordre du site (20 au plus par sorte)."""

    serializer_class = ConsoleSiteEntrySerializer
    queryset = SiteEntry.objects.all()
    parser_classes = [JSONParser]


@extend_schema(tags=["console"])
@_ordered_schema(ConsoleTestimonialSerializer)
class ConsoleTestimonialViewSet(OrderedSiteViewSet):
    """Témoignages du site public (SITE.1b), six au plus, dans l'ordre de l'accueil (le premier en
    grand). Envoyer l'accord écrit en `multipart/form-data` ; publié seulement avec lui."""

    serializer_class = ConsoleTestimonialSerializer
    queryset = Testimonial.objects.all()

    @extend_schema(responses=CONSENT_RESPONSE)
    @action(detail=True, methods=["get"])
    def consent(self, request: Request, pk=None) -> HttpResponse:
        """Télécharge l'accord écrit déposé."""
        testimonial = self.get_object()
        return _consent_response(testimonial.consent, f"accord-{testimonial.name}")


@extend_schema(tags=["console"])
@_ordered_schema(ConsoleReferenceSchoolSerializer)
class ConsoleReferenceSchoolViewSet(OrderedSiteViewSet):
    """Écoles de référence du site public (SITE.1b), huit au plus, dans l'ordre du site ;
    publiées seulement avec la date de l'accord de l'école."""

    serializer_class = ConsoleReferenceSchoolSerializer
    queryset = ReferenceSchool.objects.all()
    parser_classes = [JSONParser]


@extend_schema(tags=["console"])
@_ordered_schema(ConsolePlanSerializer)
class ConsolePlanViewSet(OrderedSiteViewSet):
    """Formules d'abonnement du site public (page des prix), quatre au plus, dans l'ordre de la
    page ; prix en entiers (centimes), vide : « sur devis »."""

    serializer_class = ConsolePlanSerializer
    queryset = SitePlan.objects.all()
    parser_classes = [JSONParser]


@extend_schema(tags=["console"])
@_ordered_schema(ConsolePartnerSerializer)
class ConsolePartnerViewSet(OrderedSiteViewSet):
    """Partenaires de la bande qui défile sur le site public, huit au plus, dans l'ordre du
    site ; logo choisi dans la photothèque."""

    serializer_class = ConsolePartnerSerializer
    queryset = Partner.objects.all()
    parser_classes = [JSONParser]


@extend_schema(tags=["console"])
class ConsoleSiteBannerView(APIView):
    """Bandeau d'annonce du site public (SITE.1a) : texte en français et en anglais, lien, dates
    facultatives, affiché ou caché. Chaque changement va au journal de la plateforme."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.SITE_EDIT
    serializer_class = ConsoleSiteBannerSerializer

    @extend_schema(responses={200: ConsoleSiteBannerSerializer, **CONSOLE_ERRORS})
    def get(self, request: Request) -> Response:
        return Response(ConsoleSiteBannerSerializer(SiteBanner.load()).data)

    @extend_schema(
        request=ConsoleSiteBannerSerializer,
        responses={200: ConsoleSiteBannerSerializer, **CONSOLE_ERRORS},
    )
    def patch(self, request: Request) -> Response:
        serializer = ConsoleSiteBannerSerializer(SiteBanner.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        banner = services.update_site_banner(actor=request.user, **serializer.validated_data)
        return Response(ConsoleSiteBannerSerializer(banner).data)


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(responses={200: ConsoleSitePageSerializer(many=True), **CONSOLE_ERRORS}),
    partial_update=extend_schema(responses={200: ConsoleSitePageSerializer, **CONSOLE_ERRORS}),
)
class ConsoleSitePageViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Réglages des pages publiques (SITE.1b, SITE.3) : titres et descriptions de recherche par
    langue, photo du haut de l'accueil, des écoles et des parents. Toutes les pages, réglées ou
    non, dans l'ordre du site."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.SITE_EDIT
    serializer_class = ConsoleSitePageSerializer
    pagination_class = None
    lookup_field = "key"
    lookup_value_regex = "|".join(SitePage.Key.values)
    http_method_names = ["get", "patch", "head", "options"]

    def list(self, request: Request) -> Response:
        saved = SitePage.objects.in_bulk()
        pages = [saved.get(key) or SitePage(key=key) for key in SitePage.Key.values]
        return Response(self.get_serializer(pages, many=True).data)

    def partial_update(self, request: Request, key: str) -> Response:
        page = SitePage.objects.filter(pk=key).first() or SitePage(key=key)
        serializer = self.get_serializer(page, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        page = services.update_site_page(key, actor=request.user, **serializer.validated_data)
        return Response(self.get_serializer(page).data)


class ArticlePagination(PageNumberPagination):
    page_size = 20


ARTICLE_FILTERS = [
    OpenApiParameter("state", str, enum=["draft", "scheduled", "published"]),
    OpenApiParameter("language", str, enum=Article.Language.values),
]


def _article_states(now) -> dict[str, Q]:
    published = Q(status=Article.Status.PUBLISHED)
    return {
        "draft": Q(status=Article.Status.DRAFT),
        "scheduled": published & Q(published_at__gt=now),
        "published": published & Q(published_at__lte=now),
    }


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(parameters=ARTICLE_FILTERS),
    create=extend_schema(responses={201: ConsoleArticleSerializer, **CONSOLE_ERRORS}),
    partial_update=extend_schema(responses={200: ConsoleArticleSerializer, **CONSOLE_ERRORS}),
    destroy=extend_schema(responses={204: None, **CONSOLE_ERRORS}),
)
class ConsoleArticleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Actualités du site public (SITE.2), 20 par page : brouillons et programmés d'abord (sans
    date ou à venir), puis les plus récentes. Chaque changement va au journal ; le site le montre
    tout de suite, un article programmé à sa date."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.SITE_EDIT
    serializer_class = ConsoleArticleSerializer
    pagination_class = ArticlePagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        articles = Article.objects.select_related("updated_by")
        if self.action != "list":
            return articles
        params = self.request.query_params
        state = _article_states(timezone.now()).get(params.get("state", ""))
        if state is not None:
            articles = articles.filter(state)
        if params.get("language") in Article.Language.values:
            articles = articles.filter(language=params["language"])
        return articles

    def perform_create(self, serializer) -> None:
        serializer.instance = services.create_article(
            actor=self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer) -> None:
        serializer.instance = services.update_article(
            serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance: Article) -> None:
        services.delete_article(instance, actor=self.request.user)

    @extend_schema(responses={200: ArticleCountsSerializer, **CONSOLE_ERRORS})
    @action(detail=False, methods=["get"])
    def counts(self, request: Request) -> Response:
        """Nombre d'articles de chaque état (onglets de la liste), en une requête."""
        states = _article_states(timezone.now())
        counts = Article.objects.aggregate(
            all=Count("pk"), **{name: Count("pk", filter=q) for name, q in states.items()}
        )
        return Response(ArticleCountsSerializer(counts).data)

    @extend_schema(
        request=ArticlePreviewSerializer,
        responses={200: ArticlePreviewSerializer, **CONSOLE_ERRORS},
    )
    @action(detail=False, methods=["post"])
    def preview(self, request: Request) -> Response:
        """Le texte mis en forme comme sur le site (même code), pour l'aperçu de l'éditeur."""
        serializer = ArticlePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data["body"]
        return Response(
            {
                "body": body,
                "html": site_content.body_html(body, get_language() or "fr"),
                "minutes": markdown.reading_minutes(body),
            }
        )


class PhotoPagination(PageNumberPagination):
    page_size = 24


def _uses(model, field: str):
    """Nombre de lignes de `model` qui montrent la photo (sous-requête : pas de jointures
    multipliées)."""
    rows = (
        model.objects.filter(**{field: OuterRef("pk")})
        .order_by()
        .values(field)
        .annotate(n=Count("pk"))
        .values("n")
    )
    return Coalesce(Subquery(rows), 0)


@extend_schema(tags=["console"])
@extend_schema_view(
    create=extend_schema(
        request={"multipart/form-data": ConsoleSitePhotoSerializer},
        responses={201: ConsoleSitePhotoSerializer, **CONSOLE_ERRORS},
    ),
    partial_update=extend_schema(responses={200: ConsoleSitePhotoSerializer, **CONSOLE_ERRORS}),
    destroy=extend_schema(responses={204: None, **CONSOLE_ERRORS}),
)
class ConsoleSitePhotoViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Photothèque du site public (SITE.3), 24 par page, les plus récentes d'abord, avec le nombre
    de pages, articles, témoignages et écoles qui montrent chacune. Envoi en
    `multipart/form-data` ; suppression refusée tant qu'une photo est montrée."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.SITE_EDIT
    serializer_class = ConsoleSitePhotoSerializer
    pagination_class = PhotoPagination
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return SitePhoto.objects.annotate(
            uses=_uses(SitePage, "photo")
            + _uses(Article, "photo")
            + _uses(Testimonial, "logo")
            + _uses(ReferenceSchool, "logo")
            + _uses(Partner, "logo")
        )

    def perform_create(self, serializer) -> None:
        data = dict(serializer.validated_data)
        sizes, size = data.pop("image")
        serializer.instance = services.add_site_photo(
            actor=self.request.user, sizes=sizes, size=size, **data
        )

    def perform_update(self, serializer) -> None:
        serializer.instance = services.update_site_photo(
            serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    def destroy(self, request: Request, pk=None) -> Response:
        try:
            services.delete_site_photo(self.get_object(), actor=request.user)
        except services.PhotoInUse:
            return Response(
                {"detail": _("This photo is shown on the site: choose another one first.")},
                status=400,
            )
        return Response(status=204)

    @extend_schema(responses=CONSENT_RESPONSE)
    @action(detail=True, methods=["get"])
    def consent(self, request: Request, pk=None) -> HttpResponse:
        """Télécharge l'accord écrit déposé avec la photo."""
        photo = self.get_object()
        return _consent_response(photo.consent, f"accord-photo-{photo.pk}")


@extend_schema(tags=["console"])
class ConsoleSocialLinksView(APIView):
    """Réseaux sociaux de la plateforme (SITE.5), tenus par la communication : mêmes champs que
    l'identité. Un lien vide n'apparaît pas sur le site ; chaque changement au journal."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.SITE_EDIT
    serializer_class = ConsoleSocialLinksSerializer

    @extend_schema(responses={200: ConsoleSocialLinksSerializer, **CONSOLE_ERRORS})
    def get(self, request: Request) -> Response:
        return Response(ConsoleSocialLinksSerializer(PlatformSettings.load()).data)

    @extend_schema(
        request=ConsoleSocialLinksSerializer,
        responses={200: ConsoleSocialLinksSerializer, **CONSOLE_ERRORS},
    )
    def patch(self, request: Request) -> Response:
        serializer = ConsoleSocialLinksSerializer(
            PlatformSettings.load(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        platform = services.update_platform(actor=request.user, **serializer.validated_data)
        return Response(ConsoleSocialLinksSerializer(platform).data)


@require_GET
def site_photo(request: HttpRequest, pk: str, width: str) -> HttpResponse:
    """Photo de la photothèque (SITE.3), lue sur le disque sans requête en base. Gardée un jour
    par les caches (pas plus : une photo retirée, accord repris, doit disparaître vite)."""
    if int(width) not in PHOTO_WIDTHS:
        raise Http404
    storage = SitePhoto._meta.get_field("large").storage
    try:
        content = storage.open(f"site/photos/{pk}-{width}.webp", "rb")
    except FileNotFoundError:
        raise Http404 from None
    response = FileResponse(content, content_type="image/webp")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "public, max-age=86400"
    return response

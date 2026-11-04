"""Centre d'aide (AIDE.1) : ses pages du site public (`/aide/`, `/en/help/`), sans compte ni
cookie, et l'API du panneau « Aide » des applications (`/api/help/`, publique comme le site ; la
console a la sienne, réservée à son équipe). Textes : `help_center.py`. Rien n'est lu en base,
sauf l'identité de la plateforme (pages du site) et l'école du sous-domaine (middleware)."""

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils import translation
from django.utils.cache import patch_cache_control
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasPlatformPermission
from apps.accounts.platform_roles import PLATFORM_PERMISSIONS
from apps.core import help_center, site
from apps.core.help_center import Article

NEWS_PER_PAGE = 12
API_CACHE = 3600


def _paths(found: Article) -> dict[str, str]:
    other = help_center.counterpart(found)
    return {found.lang: found.path, **({other.lang: other.path} if other else {})}


def _common(lang: str) -> dict:
    return {
        "help_home": help_center.HOME[lang],
        "help_search": help_center.SEARCH[lang],
        "help_news": help_center.NEWS[lang],
    }


@require_GET
@site.public
def home(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    """Accueil : la recherche, « Souvent cherché », les rubriques, la dernière nouveauté."""
    news = help_center.entries(lang)
    return site._render(
        request,
        "help",
        lang,
        lambda *_args: {
            **_common(lang),
            "groups": help_center.groups(lang),
            "popular": help_center.popular(lang),
            "latest": news[0] if news else None,
        },
    )


@require_GET
@site.public
def search(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    """Résultats (formulaire GET, sans JavaScript) ; aucun : les articles « Premiers pas »."""
    query = request.GET.get("q", "").strip()[:100]
    if not help_center.words(query):
        return redirect(help_center.HOME[lang])
    results = help_center.search(lang, query)
    start = next((g for g in help_center.groups(lang) if g["key"] == "start"), None)
    other = "en" if lang == "fr" else "fr"
    return site._render(
        request,
        "help",
        lang,
        lambda *_args: {
            **_common(lang),
            "query": query,
            "results": results,
            "start": start["articles"] if start and not results else [],
            "other_url": f"{help_center.SEARCH[other]}?{urlencode({'q': query})}",
            "title": _("Search the help: %(query)s") % {"query": query},
        },
        template="help_search",
        path=help_center.SEARCH[lang],
    )


@require_GET
@site.public
def article(request: HttpRequest, slug: str, lang: str = "fr") -> HttpResponse:
    """Un article de la Gestion ou du Portail, avec le sommaire de sa rubrique."""
    found = help_center.by_slug(lang, slug)
    if found is None:
        raise Http404
    paths = _paths(found)
    other = "en" if lang == "fr" else "fr"
    toc = [a for a in help_center.articles(lang) if found.group in a.groups]
    return site._render(
        request,
        "help",
        lang,
        lambda platform, _context: {
            **_common(lang),
            "article": found,
            "html": help_center.render(found, help_center.site_links(lang)),
            "group_label": help_center.group_label(found.group),
            "toc": toc,
            "related": [a for a in toc if a.key != found.key][:6],
            "alternates": paths,
            "other_url": paths.get(other, help_center.HOME[other]),
            "title": f"{found.title} | {platform.site_name}",
            "description": found.summary,
        },
        template="help_article",
        path=found.path,
    )


@require_GET
@site.public
def news(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    """Quoi de neuf : les 12 dernières mises en ligne, les plus anciennes sur les suivantes."""
    page = Paginator(help_center.entries(lang), NEWS_PER_PAGE).get_page(request.GET.get("page"))
    other = "en" if lang == "fr" else "fr"
    return site._render(
        request,
        "help",
        lang,
        lambda platform, _context: {
            **_common(lang),
            "page_obj": page,
            "entries": [
                {
                    "day": entry.day,
                    "sections": [
                        (help_center.APPS[app], entry.html(app))
                        for app in help_center.PUBLIC_APPS
                        if app in entry.sections
                    ],
                }
                for entry in page
            ],
            "alternates": help_center.NEWS,
            "other_url": help_center.NEWS[other],
            "title": _("What's new | %(name)s") % {"name": platform.site_name},
        },
        template="help_news",
        path=help_center.NEWS[lang],
    )


# API du panneau « Aide » (AIDE.2). Le HTML est écrit par le serveur (`markdown.py`) : jamais de
# HTML de l'auteur ; les mots cherchés sont dans `<mark>`.


class HelpItemSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    summary = serializers.CharField()
    group = serializers.CharField()
    group_label = serializers.CharField()
    title_html = serializers.CharField(help_text="Titre échappé, mots cherchés dans <mark>.")
    excerpt_html = serializers.CharField(help_text="Résumé ou passage du texte, échappé.")
    url = serializers.CharField(help_text="Adresse sur le site ; vide pour la console.")


class HelpListSerializer(serializers.Serializer):
    articles = HelpItemSerializer(many=True)


class HelpArticleSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    summary = serializers.CharField()
    group = serializers.CharField()
    group_label = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())
    minutes = serializers.IntegerField()
    updated = serializers.DateField(allow_null=True)
    html = serializers.CharField(help_text="Texte de l'article, rendu par le serveur.")
    url = serializers.CharField()
    related = HelpItemSerializer(many=True)


class WhatsNewSerializer(serializers.Serializer):
    day = serializers.DateField()
    summary = serializers.CharField()
    html = serializers.CharField(help_text="Liste des nouveautés de cette application.")
    url = serializers.CharField(help_text="Page « Quoi de neuf » du centre d'aide.")


def _lang(request: Request) -> str:
    lang = request.query_params.get("lang") or translation.get_language() or "fr"
    return lang[:2] if lang[:2] in help_center.LANGS else "fr"


def _links(lang: str, app: str) -> dict[str, str]:
    """Liens entre articles : le site pour la Gestion et le Portail, le panneau pour la console."""
    if app == "console":
        return {a.key: "#" for a in help_center.articles(lang, ("console",))}
    return help_center.site_links(lang, absolute=True)


def _url(found: Article) -> str:
    return help_center.site_url() + found.path if found.public else ""


def _item(found: Article, title_html=None, excerpt_html=None) -> dict:
    return {
        "key": found.key,
        "title": found.title,
        "summary": found.summary,
        "group": found.group,
        "group_label": help_center.group_label(found.group),
        "title_html": title_html or help_center.highlight(found.title, []),
        "excerpt_html": excerpt_html or help_center.highlight(found.summary, []),
        "url": _url(found),
    }


def _list(request: Request, app: str) -> dict:
    lang, query = _lang(request), request.query_params.get("search", "")[:100]
    with translation.override(lang):
        if help_center.words(query):
            rows = help_center.search(lang, query, (app,))
            return {"articles": [_item(r["article"], r["title"], r["excerpt"]) for r in rows]}
        return {"articles": [_item(a) for a in help_center.articles(lang, (app,))]}


def _article(request: Request, app: str, key: str) -> dict:
    lang = _lang(request)
    found = help_center.article(lang, key)
    if found is None or found.app != app:
        raise Http404
    with translation.override(lang):
        related = [
            a
            for a in help_center.articles(lang, (app,))
            if found.group in a.groups and a.key != found.key
        ]
        return {
            **_item(found),
            "roles": found.role_labels(),
            "minutes": found.minutes,
            "updated": found.updated,
            "html": help_center.render(found, _links(lang, app)),
            "related": [_item(a) for a in related[:6]],
        }


def _public(response: Response) -> Response:
    patch_cache_control(response, public=True, max_age=API_CACHE)
    return response


LANG = OpenApiParameter("lang", str, enum=list(help_center.LANGS), required=False)
SEARCH = OpenApiParameter("search", str, required=False, description="Deux lettres au moins.")


@extend_schema(
    operation_id="help_list",
    responses={200: HelpListSerializer},
    parameters=[LANG, SEARCH],
    tags=["help"],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def help_list(request: Request, app: str) -> Response:
    """Articles d'aide de la Gestion ou du Portail ; avec `search`, ceux qui contiennent tous les
    mots (20 au plus, titre d'abord)."""
    return _public(Response(HelpListSerializer(_list(request, app)).data))


@extend_schema(
    operation_id="help_article",
    responses={200: HelpArticleSerializer},
    parameters=[LANG],
    tags=["help"],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def help_article(request: Request, app: str, key: str) -> Response:
    """Un article d'aide (clé commune aux deux langues), son texte et ceux de sa rubrique."""
    return _public(Response(HelpArticleSerializer(_article(request, app, key)).data))


APP = OpenApiParameter("app", str, enum=list(help_center.PUBLIC_APPS), required=True)


@extend_schema(responses={200: WhatsNewSerializer}, parameters=[LANG, APP], tags=["help"])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def whats_new(request: Request) -> Response:
    """La dernière mise en ligne qui a des nouveautés pour cette application ; aucune : 404."""
    lang, app = _lang(request), request.query_params.get("app", "")
    rows = help_center.entries(lang, app) if app in help_center.PUBLIC_APPS else []
    if not rows:
        raise Http404
    entry = rows[0]
    data = {
        "day": entry.day,
        "summary": entry.summary,
        "html": entry.html(app),
        "url": help_center.site_url() + help_center.NEWS[lang],
    }
    return _public(Response(WhatsNewSerializer(data).data))


class _ConsoleHelp(APIView):
    """Aide de la console : tout membre de l'équipe qui a au moins un droit."""

    permission_classes = [HasPlatformPermission]
    platform_permission = tuple(PLATFORM_PERMISSIONS)


class ConsoleHelpListView(_ConsoleHelp):
    @extend_schema(
        operation_id="console_help_list",
        responses={200: HelpListSerializer},
        parameters=[LANG, SEARCH],
        tags=["help"],
    )
    def get(self, request: Request) -> Response:
        """Articles d'aide de la console ; avec `search`, ceux qui contiennent tous les mots."""
        return Response(HelpListSerializer(_list(request, "console")).data)


class ConsoleHelpArticleView(_ConsoleHelp):
    @extend_schema(
        operation_id="console_help_article",
        responses={200: HelpArticleSerializer},
        parameters=[LANG],
        tags=["help"],
    )
    def get(self, request: Request, key: str) -> Response:
        """Un article d'aide de la console."""
        return Response(HelpArticleSerializer(_article(request, "console", key)).data)

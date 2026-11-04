from django.urls import path, re_path
from rest_framework.routers import SimpleRouter

from apps.core import help_views, views

urlpatterns = [
    path("", views.platform_identity, name="platform"),
    path("logo/", views.platform_logo, name="platform-logo"),
    path("icon/", views.platform_icon, name="platform-icon"),
    path("manifest/<str:app>/", views.platform_manifest, name="platform-manifest"),
    # Photothèque du site (SITE.3) : `site_content.photo_url`.
    re_path(
        r"^photos/(?P<pk>[0-9a-f-]{36})-(?P<width>1600|600)\.webp$",
        views.site_photo,
        name="platform-photo",
    ),
]

# Console de la plateforme (5.2.2), sous `/api/console/platform/`.
console_urlpatterns = [
    path("", views.ConsolePlatformView.as_view(), name="console-platform"),
    path("logo/", views.ConsolePlatformLogoView.as_view(), name="console-platform-logo"),
    path("icon/", views.ConsolePlatformIconView.as_view(), name="console-platform-icon"),
]

# Demandes de démonstration du site (WEB.1d), sous `/api/console/demo-requests/`.
router = SimpleRouter()
router.register("console/demo-requests", views.ConsoleDemoRequestViewSet, basename="console-demo")
# Contenus du site public (SITE.1a), sous `/api/console/site/`.
router.register("console/site/entries", views.ConsoleSiteEntryViewSet, basename="console-site")
# Témoignages, écoles de référence, pages, actualités, photothèque (SITE.1b à SITE.3).
router.register(
    "console/site/testimonials", views.ConsoleTestimonialViewSet, basename="console-testimonial"
)
router.register(
    "console/site/references", views.ConsoleReferenceSchoolViewSet, basename="console-reference"
)
router.register("console/site/plans", views.ConsolePlanViewSet, basename="console-plan")
router.register("console/site/partners", views.ConsolePartnerViewSet, basename="console-partner")
router.register("console/site/pages", views.ConsoleSitePageViewSet, basename="console-site-page")
router.register("console/site/articles", views.ConsoleArticleViewSet, basename="console-article")
router.register("console/site/photos", views.ConsoleSitePhotoViewSet, basename="console-photo")
api_urlpatterns = [
    *router.urls,
    # Centre d'aide (AIDE.1, AIDE.2) : panneau « Aide » des applications.
    path("help/whats-new/", help_views.whats_new, name="help-whats-new"),
    re_path(r"^help/(?P<app>gestion|portail)/$", help_views.help_list, name="help-list"),
    re_path(
        r"^help/(?P<app>gestion|portail)/(?P<key>[a-z0-9-]+)/$",
        help_views.help_article,
        name="help-article",
    ),
    path("console/help/", help_views.ConsoleHelpListView.as_view(), name="console-help"),
    path(
        "console/help/<slug:key>/",
        help_views.ConsoleHelpArticleView.as_view(),
        name="console-help-article",
    ),
    path("console/site/banner/", views.ConsoleSiteBannerView.as_view(), name="console-site-banner"),
    path("console/site/social/", views.ConsoleSocialLinksView.as_view(), name="console-social"),
]

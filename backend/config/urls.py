from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core import site
from apps.core import urls as core_urls
from apps.finance.verification import verify_receipt, verify_statement
from apps.schools.views import (
    MemberSignatureView,
    SchoolHeadSignatureView,
    SchoolLogoView,
    SchoolMonochromeLogoView,
    SchoolSettingsView,
    SchoolSetupFinishView,
    SchoolSetupView,
    SchoolSignatureImageView,
    SchoolStampView,
    current_school,
    school_logo,
    school_logo_monochrome,
)
from config.views import health

urlpatterns = [
    # Site public de la plateforme (domaine nu, `apps/core/site.py`).
    path("", site.home, name="site-home"),
    path("en/", site.home, {"lang": "en"}, name="site-home-en"),
    path("ecole/", site.school_space, name="site-school"),
    path("robots.txt", site.robots_txt, name="site-robots"),
    path("sitemap.xml", site.sitemap_xml, name="site-sitemap"),
    path("llms.txt", site.llms_txt, name="site-llms"),
    path("favicon.ico", site.favicon, name="site-favicon"),
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/platform/", include("apps.core.urls")),
    path("api/console/platform/", include(core_urls.console_urlpatterns)),
    path("api/school/", current_school, name="current-school"),
    path("api/school/logo/", school_logo, name="school-logo"),
    path("api/school/logo-monochrome/", school_logo_monochrome, name="school-logo-monochrome"),
    path("api/school/settings/", SchoolSettingsView.as_view(), name="school-settings"),
    path("api/school/setup/", SchoolSetupView.as_view(), name="school-setup"),
    path("api/school/setup/finish/", SchoolSetupFinishView.as_view(), name="school-setup-finish"),
    path("api/school/settings/logo/", SchoolLogoView.as_view(), name="school-settings-logo"),
    path(
        "api/school/settings/logo-monochrome/",
        SchoolMonochromeLogoView.as_view(),
        name="school-settings-logo-monochrome",
    ),
    # Cachet et signatures (DOC.1) : au personnel connecté de l'école seulement.
    path("api/school/stamp/", SchoolSignatureImageView.as_view(), name="school-stamp"),
    path(
        "api/school/head-signature/",
        SchoolSignatureImageView.as_view(field="head_signature"),
        name="school-head-signature",
    ),
    path(
        "api/school/signatures/<uuid:user_id>/",
        MemberSignatureView.as_view(),
        name="school-member-signature",
    ),
    path("api/school/settings/stamp/", SchoolStampView.as_view(), name="school-settings-stamp"),
    path(
        "api/school/settings/head-signature/",
        SchoolHeadSignatureView.as_view(),
        name="school-settings-head-signature",
    ),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.audit.urls")),
    path("api/", include("apps.schools.urls")),
    path("api/", include("apps.students.urls")),
    path("api/", include("apps.finance.urls")),
    path("api/", include("apps.sync.urls")),
    path("api/", include("apps.notifications.urls")),
    path("api/", include("apps.academics.urls")),
    path("api/portal/", include("apps.portal.urls")),
    # Vérification publique d'un reçu (QR code du reçu), sur l'adresse de l'école.
    path("v/<uuid:payment_id>", verify_receipt, name="receipt-verification"),
    # Vérification publique d'une situation financière imprimée (son QR code).
    path("v/s/<str:token>", verify_statement, name="statement-verification"),
]

if settings.DEBUG:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    ]

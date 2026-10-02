from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.finance.verification import verify_receipt, verify_statement
from apps.schools.views import (
    SchoolLogoView,
    SchoolMonochromeLogoView,
    SchoolSettingsView,
    current_school,
    school_logo,
    school_logo_monochrome,
)
from config.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/school/", current_school, name="current-school"),
    path("api/school/logo/", school_logo, name="school-logo"),
    path("api/school/logo-monochrome/", school_logo_monochrome, name="school-logo-monochrome"),
    path("api/school/settings/", SchoolSettingsView.as_view(), name="school-settings"),
    path("api/school/settings/logo/", SchoolLogoView.as_view(), name="school-settings-logo"),
    path(
        "api/school/settings/logo-monochrome/",
        SchoolMonochromeLogoView.as_view(),
        name="school-settings-logo-monochrome",
    ),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.audit.urls")),
    path("api/", include("apps.schools.urls")),
    path("api/", include("apps.students.urls")),
    path("api/", include("apps.finance.urls")),
    path("api/", include("apps.sync.urls")),
    path("api/", include("apps.notifications.urls")),
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

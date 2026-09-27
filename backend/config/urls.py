from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.schools.views import SchoolLogoView, SchoolSettingsView, current_school, school_logo
from config.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/school/", current_school, name="current-school"),
    path("api/school/logo/", school_logo, name="school-logo"),
    path("api/school/settings/", SchoolSettingsView.as_view(), name="school-settings"),
    path("api/school/settings/logo/", SchoolLogoView.as_view(), name="school-settings-logo"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.audit.urls")),
    path("api/", include("apps.schools.urls")),
]

if settings.DEBUG:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    ]

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.core import views

urlpatterns = [
    path("", views.platform_identity, name="platform"),
    path("logo/", views.platform_logo, name="platform-logo"),
    path("icon/", views.platform_icon, name="platform-icon"),
    path("manifest/<str:app>/", views.platform_manifest, name="platform-manifest"),
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

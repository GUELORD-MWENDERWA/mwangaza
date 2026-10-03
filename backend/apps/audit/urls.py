from rest_framework.routers import SimpleRouter

from apps.audit import views

router = SimpleRouter()
router.register("audit", views.AuditLogViewSet, basename="audit")
router.register("console/audit", views.ConsolePlatformLogViewSet, basename="console-audit")

urlpatterns = router.urls

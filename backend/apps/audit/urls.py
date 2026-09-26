from rest_framework.routers import SimpleRouter

from apps.audit import views

router = SimpleRouter()
router.register("audit", views.AuditLogViewSet, basename="audit")

urlpatterns = router.urls

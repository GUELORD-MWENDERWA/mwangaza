from rest_framework.routers import SimpleRouter

from apps.notifications.views import AnnouncementViewSet

router = SimpleRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = router.urls

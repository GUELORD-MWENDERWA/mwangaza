from rest_framework.routers import SimpleRouter

from apps.notifications.views import (
    AnnouncementViewSet,
    ConsolePlatformAnnouncementViewSet,
    PlatformNewsViewSet,
)

router = SimpleRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register(
    "console/announcements", ConsolePlatformAnnouncementViewSet, basename="console-announcement"
)
router.register("platform-announcements", PlatformNewsViewSet, basename="platform-announcement")

urlpatterns = router.urls

from rest_framework.routers import SimpleRouter

from apps.notifications.views import (
    AnnouncementViewSet,
    ConsoleAlertViewSet,
    ConsolePlatformAnnouncementViewSet,
    NotificationViewSet,
    PlatformNewsViewSet,
    SchoolEventViewSet,
    StaffAnnouncementViewSet,
    SummonsViewSet,
)

router = SimpleRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register(
    "console/announcements", ConsolePlatformAnnouncementViewSet, basename="console-announcement"
)
router.register("console/alerts", ConsoleAlertViewSet, basename="console-alert")
router.register("calendar-events", SchoolEventViewSet, basename="calendar-event")
router.register("staff-announcements", StaffAnnouncementViewSet, basename="staff-announcement")
router.register("summons", SummonsViewSet, basename="summons")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("platform-announcements", PlatformNewsViewSet, basename="platform-announcement")

urlpatterns = router.urls

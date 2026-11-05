from rest_framework.routers import SimpleRouter

from apps.notifications.support_views import ConsoleSupportRequestViewSet, SupportRequestViewSet
from apps.notifications.thread_views import ParentThreadViewSet
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
router.register("parent-threads", ParentThreadViewSet, basename="parent-thread")
router.register("help/requests", SupportRequestViewSet, basename="support-request")
router.register("console/support", ConsoleSupportRequestViewSet, basename="console-support-request")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("platform-announcements", PlatformNewsViewSet, basename="platform-announcement")

urlpatterns = router.urls

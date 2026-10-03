from rest_framework.routers import SimpleRouter

from apps.sync import views

router = SimpleRouter()
router.register("me/devices", views.MyDeviceViewSet, basename="my-device")
router.register("devices", views.SchoolDeviceViewSet, basename="device")
router.register("console/devices", views.ConsoleDeviceViewSet, basename="console-device")
router.register("sync", views.SyncViewSet, basename="sync")

urlpatterns = router.urls

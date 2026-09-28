from rest_framework.routers import SimpleRouter

from apps.sync import views

router = SimpleRouter()
router.register("me/devices", views.MyDeviceViewSet, basename="my-device")
router.register("sync", views.SyncViewSet, basename="sync")

urlpatterns = router.urls

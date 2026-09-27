from rest_framework.routers import SimpleRouter

from apps.finance import views

router = SimpleRouter()
router.register("fee-types", views.FeeTypeViewSet, basename="fee-type")
router.register("fee-rules", views.FeeRuleViewSet, basename="fee-rule")
router.register("exchange-rates", views.ExchangeRateViewSet, basename="exchange-rate")
router.register("student-charges", views.StudentChargeViewSet, basename="student-charge")

urlpatterns = router.urls

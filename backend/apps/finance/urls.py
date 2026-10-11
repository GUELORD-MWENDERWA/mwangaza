from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.finance import views

router = SimpleRouter()
router.register("fee-types", views.FeeTypeViewSet, basename="fee-type")
router.register("fee-rules", views.FeeRuleViewSet, basename="fee-rule")
router.register("exchange-rates", views.ExchangeRateViewSet, basename="exchange-rate")
router.register("discounts", views.DiscountViewSet, basename="discount")
router.register("student-charges", views.StudentChargeViewSet, basename="student-charge")
router.register("cash-registers", views.CashRegisterViewSet, basename="cash-register")
router.register("cash-sessions", views.CashSessionViewSet, basename="cash-session")
router.register("cash-closings", views.CashClosingViewSet, basename="cash-closing")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("cancellations", views.CancellationViewSet, basename="cancellation")
router.register("student-credits", views.StudentCreditViewSet, basename="student-credit")
router.register("unpaid", views.UnpaidViewSet, basename="unpaid")

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("prior-payments/", views.PriorPaymentsView.as_view(), name="prior-payments"),
    path(
        "prior-payments/template/",
        views.PriorPaymentsTemplateView.as_view(),
        name="prior-payments-template",
    ),
    *router.urls,
]

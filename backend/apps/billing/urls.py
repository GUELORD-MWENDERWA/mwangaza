from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.billing import views

router = SimpleRouter()
router.register("console/billing/plans", views.ConsolePlanViewSet, basename="console-plan")
router.register(
    "console/billing/contracts", views.ConsoleContractViewSet, basename="console-contract"
)
router.register("console/billing/invoices", views.ConsoleInvoiceViewSet, basename="console-invoice")
router.register("console/billing/legal", views.ConsoleLegalViewSet, basename="console-legal")

urlpatterns = [
    path("legal/current/", views.LegalCurrentView.as_view(), name="legal-current"),
    path("legal/pending/", views.LegalPendingView.as_view(), name="legal-pending"),
    path("legal/accept/", views.LegalAcceptView.as_view(), name="legal-accept"),
    path(
        "console/billing/statement/<slug:code>/",
        views.ConsoleStatementView.as_view(),
        name="console-statement",
    ),
    *router.urls,
]

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
router.register(
    "console/billing/module-requests",
    views.ConsoleModuleRequestViewSet,
    basename="console-module-request",
)
router.register(
    "subscription/invoices", views.SubscriptionInvoiceViewSet, basename="subscription-invoice"
)

urlpatterns = [
    path("legal/current/", views.LegalCurrentView.as_view(), name="legal-current"),
    path("legal/pending/", views.LegalPendingView.as_view(), name="legal-pending"),
    path("legal/accept/", views.LegalAcceptView.as_view(), name="legal-accept"),
    path(
        "console/billing/statement/<slug:code>/",
        views.ConsoleStatementView.as_view(),
        name="console-statement",
    ),
    path("subscription/", views.SubscriptionView.as_view(), name="subscription"),
    path(
        "subscription/contract/pdf/",
        views.SubscriptionContractPdfView.as_view(),
        name="subscription-contract-pdf",
    ),
    path("subscription/module-requests/", views.ModuleRequestView.as_view(), name="module-request"),
    *router.urls,
]

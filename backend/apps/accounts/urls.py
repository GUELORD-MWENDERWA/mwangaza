from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.accounts import views

router = SimpleRouter()
router.register("roles", views.RoleViewSet, basename="role")
router.register("staff", views.StaffViewSet, basename="staff")
router.register("console/accounts", views.ConsoleAccountViewSet, basename="console-account")

urlpatterns = [
    path("me/", views.MeView.as_view(), name="me"),
    path("auth/csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/login/totp/", views.LoginCodeView.as_view(), name="auth-login-totp"),
    path("auth/password/", views.PasswordView.as_view(), name="auth-password"),
    path("auth/totp/setup/", views.TotpSetupView.as_view(), name="auth-totp-setup"),
    path("auth/totp/activate/", views.TotpActivateView.as_view(), name="auth-totp-activate"),
    path(
        "auth/totp/recovery-codes/",
        views.RecoveryCodesView.as_view(),
        name="auth-totp-recovery-codes",
    ),
    path("auth/totp/disable/", views.TotpDisableView.as_view(), name="auth-totp-disable"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("support/", views.SupportView.as_view(), name="support"),
    *router.urls,
]

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.accounts.views import MeView, RoleViewSet, StaffViewSet

router = SimpleRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("staff", StaffViewSet, basename="staff")

urlpatterns = [path("me/", MeView.as_view(), name="me"), *router.urls]

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.schools import views

router = SimpleRouter()
router.register("academic-years", views.AcademicYearViewSet, basename="academic-year")
router.register("levels", views.LevelViewSet, basename="level")
router.register("tracks", views.TrackViewSet, basename="track")
router.register("class-groups", views.ClassGroupViewSet, basename="class-group")

urlpatterns = [
    path("console/dashboard/", views.ConsoleDashboardView.as_view(), name="console-dashboard"),
    path("matricule-format/", views.MatriculeFormatView.as_view(), name="matricule-format"),
    path(
        "matricule-format/preview/",
        views.MatriculePreviewView.as_view(),
        name="matricule-format-preview",
    ),
    *router.urls,
]

from django.urls import path

from apps.academics import views

urlpatterns = [
    path("class-groups/<uuid:pk>/courses/", views.ClassCoursesView.as_view(), name="class-courses"),
    path(
        "class-groups/<uuid:pk>/courses/copy/",
        views.ClassCoursesCopyView.as_view(),
        name="class-courses-copy",
    ),
    path("course-templates/", views.OfficialGridsView.as_view(), name="course-templates"),
    path("teaching-loads/", views.TeachingLoadsView.as_view(), name="teaching-loads"),
]

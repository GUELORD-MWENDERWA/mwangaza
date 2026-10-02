from rest_framework.routers import SimpleRouter

from apps.students import views

router = SimpleRouter()
router.register("students", views.StudentViewSet, basename="student")
router.register("families", views.FamilyViewSet, basename="family")
router.register("enrollments", views.EnrollmentViewSet, basename="enrollment")
router.register("student-imports", views.StudentImportViewSet, basename="student-import")
router.register("contact-changes", views.ContactChangeViewSet, basename="contact-change")

urlpatterns = router.urls

from django.urls import path

from apps.academics import application_views as application
from apps.academics import discipline_views as conduct
from apps.academics import views

urlpatterns = [
    path("class-groups/<uuid:pk>/courses/", views.ClassCoursesView.as_view(), name="class-courses"),
    path(
        "class-groups/<uuid:pk>/courses/copy/",
        views.ClassCoursesCopyView.as_view(),
        name="class-courses-copy",
    ),
    path(
        "class-groups/<uuid:pk>/report-card/",
        views.ReportCardView.as_view(),
        name="report-card",
    ),
    path(
        "class-groups/<uuid:pk>/report-card-status/",
        views.ReportCardStatusView.as_view(),
        name="report-card-status",
    ),
    path(
        "class-groups/<uuid:pk>/grade-sheet/",
        views.GradeSheetPrintView.as_view(),
        name="grade-sheet-print",
    ),
    path("course-templates/", views.OfficialGridsView.as_view(), name="course-templates"),
    path("teaching-loads/", views.TeachingLoadsView.as_view(), name="teaching-loads"),
    path("grading/", views.GradingView.as_view(), name="grading"),
    path("grading/validation/", views.GradingValidationView.as_view(), name="grading-validation"),
    path(
        "terms/<uuid:term>/grades-deadline/",
        views.GradeDeadlineView.as_view(),
        name="grade-deadline",
    ),
    path(
        "courses/<uuid:pk>/terms/<uuid:term>/grades/submit/",
        views.GradeSubmitView.as_view(),
        name="grade-submit",
    ),
    path(
        "courses/<uuid:pk>/terms/<uuid:term>/grades/validate/",
        views.GradeValidateView.as_view(),
        name="grade-validate",
    ),
    path(
        "courses/<uuid:pk>/terms/<uuid:term>/grades/reopen/",
        views.GradeReopenView.as_view(),
        name="grade-reopen",
    ),
    path(
        "courses/<uuid:pk>/terms/<uuid:term>/grades/",
        views.GradeSheetView.as_view(),
        name="grade-sheet",
    ),
    path("discipline/rules/", conduct.RulesView.as_view(), name="discipline-rules"),
    path(
        "discipline/rules/defaults/", conduct.DefaultRulesView.as_view(), name="discipline-defaults"
    ),
    path("discipline/rules/<uuid:pk>/", conduct.RuleView.as_view(), name="discipline-rule"),
    path("discipline/scale/", conduct.ScaleView.as_view(), name="discipline-scale"),
    path("discipline/classes/", conduct.ClassesView.as_view(), name="discipline-classes"),
    path(
        "discipline/classes/<uuid:pk>/students/",
        conduct.ClassStudentsView.as_view(),
        name="discipline-class-students",
    ),
    path("discipline/incidents/", conduct.IncidentsView.as_view(), name="discipline-incidents"),
    path(
        "discipline/incidents/<uuid:pk>/cancel/",
        conduct.IncidentCancelView.as_view(),
        name="discipline-incident-cancel",
    ),
    path(
        "discipline/enrollments/<uuid:pk>/",
        conduct.EnrollmentIncidentsView.as_view(),
        name="discipline-enrollment",
    ),
    path(
        "discipline/enrollments/<uuid:pk>/grade/",
        conduct.GradeOverrideView.as_view(),
        name="discipline-grade",
    ),
    path(
        "class-groups/<uuid:pk>/application/",
        application.ClassApplicationView.as_view(),
        name="class-application",
    ),
    path(
        "application/enrollments/<uuid:pk>/",
        application.ApplicationOverrideView.as_view(),
        name="application-grade",
    ),
]

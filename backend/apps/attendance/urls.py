from django.urls import path

from apps.attendance import views

urlpatterns = [
    path("attendance/cards/students/", views.CardStudentsView.as_view()),
    path("attendance/cards/staff/", views.CardStaffView.as_view()),
    path("attendance/cards/summary/", views.CardSummaryView.as_view()),
    path("attendance/cards/print/", views.CardPrintView.as_view()),
    path("attendance/cards/print/<uuid:batch>/", views.CardPrintFileView.as_view()),
    path("attendance/cards/<uuid:pk>/revoke/", views.CardRevokeView.as_view()),
    path("attendance/roster/", views.RosterView.as_view()),
    path("attendance/day/", views.DayView.as_view()),
    path("attendance/absences/", views.AbsencesView.as_view()),
    path("attendance/staff/", views.StaffDayView.as_view()),
    path("attendance/corrections/", views.CorrectionsView.as_view()),
    path("attendance/justifications/", views.JustificationsView.as_view()),
    path("attendance/justifications/<uuid:pk>/decide/", views.JustificationDecideView.as_view()),
    path(
        "attendance/justifications/<uuid:pk>/document/", views.JustificationDocumentView.as_view()
    ),
    path("attendance/export/", views.ExportView.as_view()),
]

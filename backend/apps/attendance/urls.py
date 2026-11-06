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
]

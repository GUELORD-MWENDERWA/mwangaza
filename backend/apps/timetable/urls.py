from django.urls import path

from apps.timetable import views

urlpatterns = [
    path("timetable/grids/", views.GridsView.as_view()),
    path("timetable/grids/<uuid:pk>/", views.GridView.as_view()),
    path("timetable/classes/", views.ClassesView.as_view()),
    path("timetable/classes/<uuid:pk>/", views.ClassView.as_view()),
    path("timetable/rooms/", views.RoomsView.as_view()),
    path("timetable/rooms/<uuid:pk>/", views.RoomView.as_view()),
    path("timetable/rules/", views.RulesView.as_view()),
    path("timetable/teachers/", views.TeachersView.as_view()),
    path("timetable/teachers/<uuid:pk>/", views.TeacherView.as_view()),
    path("timetable/checks/", views.ChecksView.as_view()),
    path("timetable/constraints/", views.ConstraintsView.as_view()),
    path("timetable/constraints/choices/", views.ConstraintChoicesView.as_view()),
    path("timetable/constraints/<uuid:pk>/", views.ConstraintView.as_view()),
    path("timetable/courses/", views.TimetableCoursesView.as_view()),
    path("timetable/drafts/", views.DraftsView.as_view()),
    path("timetable/drafts/<uuid:pk>/", views.DraftView.as_view()),
    path("timetable/drafts/<uuid:pk>/entries/", views.DraftEntriesView.as_view()),
    path("timetable/drafts/<uuid:pk>/entries/<uuid:entry>/", views.DraftEntryView.as_view()),
    path("timetable/drafts/<uuid:pk>/swap/", views.DraftSwapView.as_view()),
    path("timetable/drafts/<uuid:pk>/undo/", views.DraftUndoView.as_view()),
]

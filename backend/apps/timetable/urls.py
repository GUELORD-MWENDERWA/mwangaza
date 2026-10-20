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
]

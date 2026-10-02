from django.urls import path

from apps.portal import views

app_name = "portal"

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/activate/", views.ActivateView.as_view(), name="activate"),
    path("auth/reset/", views.ResetView.as_view(), name="reset"),
    path("me/", views.MeView.as_view(), name="me"),
    path("families/", views.FamiliesView.as_view(), name="families"),
    path("families/link/", views.LinkView.as_view(), name="link"),
    path("children/<uuid:pk>/", views.ChildView.as_view(), name="child"),
    path("children/<uuid:pk>/photo/", views.ChildPhotoView.as_view(), name="child-photo"),
    path("payments/<uuid:pk>/receipt/", views.ReceiptView.as_view(), name="receipt"),
    path("announcements/", views.AnnouncementsView.as_view(), name="announcements"),
    path("announcements/read/", views.AnnouncementsReadView.as_view(), name="announcements-read"),
    path(
        "announcements/<uuid:pk>/attachment/",
        views.AnnouncementAttachmentView.as_view(),
        name="announcement-attachment",
    ),
]

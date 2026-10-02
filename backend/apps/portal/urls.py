from django.urls import path

from apps.portal import views

app_name = "portal"

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/activate/", views.ActivateView.as_view(), name="activate"),
    path("auth/reset/", views.ResetView.as_view(), name="reset"),
    path("me/", views.MeView.as_view(), name="me"),
]

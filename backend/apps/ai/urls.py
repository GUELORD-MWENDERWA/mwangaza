from django.urls import path

from apps.ai import views

urlpatterns = [
    path("ai/credits/", views.AiCreditsView.as_view(), name="ai-credits"),
    path("console/ai/", views.ConsoleAiView.as_view(), name="console-ai"),
    path(
        "console/ai/prices/<str:model>/",
        views.ConsoleAiPriceView.as_view(),
        name="console-ai-price",
    ),
    path("console/ai/uses/<str:code>/", views.ConsoleAiUseView.as_view(), name="console-ai-use"),
    path(
        "console/ai/schools/<uuid:pk>/",
        views.ConsoleAiSchoolView.as_view(),
        name="console-ai-school",
    ),
    path(
        "console/ai/schools/<uuid:pk>/top-up/",
        views.ConsoleAiTopUpView.as_view(),
        name="console-ai-top-up",
    ),
]

from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("library/books/", views.BooksView.as_view()),
    path("library/books/<uuid:pk>/", views.BookView.as_view()),
    path("library/books/<uuid:pk>/copies/", views.BookCopiesView.as_view()),
    path("library/import/", views.ImportView.as_view()),
    path("library/import/template/", views.ImportTemplateView.as_view()),
    path("library/rules/", views.RulesView.as_view()),
    path("library/loans/", views.LoansView.as_view()),
    path("library/loans/<uuid:pk>/extend/", views.LoanExtendView.as_view()),
    path("library/reports/", views.ReportsView.as_view()),
    path("library/reports/<uuid:pk>/correct/", views.ReportCorrectView.as_view()),
    path("library/desk/", views.DeskView.as_view()),
]

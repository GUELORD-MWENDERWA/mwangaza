from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class StudentsConfig(AppConfig):
    """Élèves, familles, tuteurs et inscriptions (D1-D5)."""

    name = "apps.students"
    label = "students"
    verbose_name = _("Students")

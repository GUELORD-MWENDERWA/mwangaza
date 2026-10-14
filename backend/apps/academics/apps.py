from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AcademicsConfig(AppConfig):
    """Enseignement (`01` § 8.6) : cours de chaque classe et enseignants (8.1), puis notes,
    bulletins et délibération (8.2 à 8.4)."""

    name = "apps.academics"
    label = "academics"
    verbose_name = _("Courses and grades")

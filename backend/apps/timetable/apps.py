from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TimetableConfig(AppConfig):
    """Emploi du temps (bloc EDT, `docs/specs/emploi-du-temps.md`) : grilles horaires, salles."""

    name = "apps.timetable"
    label = "timetable"
    verbose_name = _("Timetable")

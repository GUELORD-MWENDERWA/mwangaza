from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AttendanceConfig(AppConfig):
    """Cartes et présences (lot 10) : cartes d'élève et du personnel, pointage à l'entrée, suivi,
    justifications. Les lecteurs et l'appel en classe (lot 16) écrivent dans les mêmes tables."""

    name = "apps.attendance"
    label = "attendance"
    verbose_name = _("Attendance")

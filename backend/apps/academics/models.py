from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.schools.models import ClassGroup

# Bornes de saisie : un maximum de bulletin va de 10 à 100 (rarement plus), une semaine compte
# 36 à 41 heures de cours au secondaire.
MAX_PERIOD_MAX = 1000
MAX_WEEKLY_HOURS = 40


class Course(TenantModel):
    """Cours (branche) d'une classe [T] : maximum par période, examen ou non, heures par semaine,
    enseignant (8.1). Examen = deux fois le maximum de la période ; le total de l'année (T.G.) se
    calcule d'après le découpage de l'année, jamais stocké. La grille d'une classe s'enregistre
    d'un seul bloc (`courses.set_courses`). Pas de catalogue de matières : le nom relie les
    classes."""

    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.CASCADE, related_name="courses", verbose_name=_("class")
    )
    name = models.CharField(_("name"), max_length=100)
    # Domaine du programme (« Sciences », « Langues »), facultatif : regroupe les cours du
    # bulletin de l'éducation de base.
    domain = models.CharField(_("domain"), max_length=100, blank=True)
    period_max = models.PositiveSmallIntegerField(
        _("maximum per period"),
        validators=[MinValueValidator(1), MaxValueValidator(MAX_PERIOD_MAX)],
    )
    # Atelier, laboratoire, pratique professionnelle : pas d'examen.
    has_exam = models.BooleanField(_("with exam"), default=True)
    # Vide tant que l'école ne l'a pas saisi ; servira à l'emploi du temps (EDT).
    weekly_hours = models.PositiveSmallIntegerField(
        _("hours per week"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_WEEKLY_HOURS)],
    )
    # Une personne du personnel actif de l'école (vérifié par `courses.py`).
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("teacher"),
    )
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["class_group", "order"]
        verbose_name = _("course")
        verbose_name_plural = _("courses")
        constraints = [
            # Sans tenir compte des majuscules : vérifié par `courses.py`. Différée : deux cours
            # peuvent échanger leurs noms dans un même envoi.
            models.UniqueConstraint(
                fields=["class_group", "name"],
                name="course_name_unique_per_class",
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.CheckConstraint(
                condition=models.Q(period_max__gte=1, period_max__lte=MAX_PERIOD_MAX),
                name="course_period_max_range",
            ),
            models.CheckConstraint(
                condition=models.Q(weekly_hours__isnull=True)
                | models.Q(weekly_hours__gte=1, weekly_hours__lte=MAX_WEEKLY_HOURS),
                name="course_weekly_hours_range",
            ),
        ]
        indexes = [models.Index(fields=["school", "teacher"], name="course_school_teacher")]

    def __str__(self) -> str:
        return self.name

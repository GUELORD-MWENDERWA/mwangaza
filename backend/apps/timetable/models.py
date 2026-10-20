"""Emploi du temps (bloc EDT, `docs/specs/emploi-du-temps.md` § 13). EDT.1a : grilles horaires,
leurs cases (heures de cours et récréations) et les salles. Une classe suit une grille
(`ClassGroup.time_grid`, vide = grille par défaut) et peut avoir une salle habituelle
(`ClassGroup.home_room`)."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel

MIN_LESSON_MINUTES = 30
MAX_LESSON_MINUTES = 90
# Une case corrigée à la main (récréation plus longue, heure raccourcie).
MIN_SLOT_MINUTES = 5
MAX_SLOT_MINUTES = 240
MAX_LESSONS_PER_DAY = 12
# 1 = lundi … 7 = dimanche (ISO 8601).
WEEKDAYS = range(1, 8)


class TimeGrid(TenantModel):
    """Grille horaire [T] : une par école au départ, une par vacation pour une école qui en a
    deux. Durée d'une heure et heure de début servent à calculer les cases ; une case peut
    ensuite être corrigée à la main. Une seule grille par défaut par école."""

    name = models.CharField(_("name"), max_length=60)
    lesson_minutes = models.PositiveSmallIntegerField(
        _("lesson length (minutes)"),
        validators=[MinValueValidator(MIN_LESSON_MINUTES), MaxValueValidator(MAX_LESSON_MINUTES)],
    )
    start_time = models.TimeField(_("start of the first lesson"))
    is_default = models.BooleanField(_("default grid"), default=False)

    class Meta:
        ordering = ["-is_default", "name"]
        verbose_name = _("time grid")
        verbose_name_plural = _("time grids")
        constraints = [
            models.UniqueConstraint(
                "school", Lower("name"), name="time_grid_name_unique_per_school"
            ),
            models.UniqueConstraint(
                fields=["school"],
                condition=models.Q(is_default=True),
                name="one_default_time_grid_per_school",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class TimeSlot(TenantModel):
    """Case d'une grille [T] : une heure de cours (numérotée dans le jour) ou une récréation.
    Les cases d'un jour se suivent sans trou ; une récréation est toujours entre deux heures
    (`services.check_slots`). Une heure garde son identifiant (grille, jour, numéro) d'un
    enregistrement à l'autre : l'horaire (EDT.2) s'y réfère."""

    class Kind(models.TextChoices):
        LESSON = "lesson", _("Lesson")
        BREAK = "break", _("Break")

    grid = models.ForeignKey(
        TimeGrid, on_delete=models.CASCADE, related_name="slots", verbose_name=_("time grid")
    )
    weekday = models.PositiveSmallIntegerField(
        _("day"), validators=[MinValueValidator(1), MaxValueValidator(7)]
    )
    # 1re heure, 2e heure… ; vide pour une récréation.
    index = models.PositiveSmallIntegerField(_("lesson number"), null=True, blank=True)
    start = models.TimeField(_("start"))
    end = models.TimeField(_("end"))
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)

    class Meta:
        ordering = ["grid", "weekday", "start"]
        verbose_name = _("time slot")
        verbose_name_plural = _("time slots")
        constraints = [
            models.UniqueConstraint(
                fields=["grid", "weekday", "index"],
                condition=models.Q(index__isnull=False),
                name="time_slot_lesson_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")), name="slot_ends_after_start"
            ),
            models.CheckConstraint(
                condition=models.Q(kind="lesson", index__isnull=False)
                | models.Q(kind="break", index__isnull=True),
                name="slot_lesson_has_number",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.weekday} {self.start:%H:%M}-{self.end:%H:%M}"


class Room(TenantModel):
    """Salle, atelier ou laboratoire [T]. Jamais supprimée : on la retire (`is_active`), l'horaire
    s'y réfère."""

    class Kind(models.TextChoices):
        CLASSROOM = "classroom", _("Classroom")
        WORKSHOP = "workshop", _("Workshop")
        LAB = "lab", _("Laboratory")
        COMPUTER = "computer", _("Computer room")
        SPORTS = "sports", _("Sports ground")
        OTHER = "other", _("Other")

    name = models.CharField(_("name"), max_length=80)
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices, default=Kind.CLASSROOM)
    capacity = models.PositiveSmallIntegerField(
        _("places"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    is_active = models.BooleanField(_("in use"), default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("room")
        verbose_name_plural = _("rooms")
        constraints = [
            models.UniqueConstraint("school", Lower("name"), name="room_name_unique_per_school"),
        ]

    def __str__(self) -> str:
        return self.name

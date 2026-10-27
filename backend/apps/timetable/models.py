"""Emploi du temps (bloc EDT, `docs/specs/emploi-du-temps.md` § 13). EDT.1a : grilles horaires,
leurs cases (heures de cours et récréations) et les salles ; EDT.1b : disponibilité des
enseignants. Une classe suit une grille
(`ClassGroup.time_grid`, vide = grille par défaut) et peut avoir une salle habituelle
(`ClassGroup.home_room`)."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.timetable.limits import MAX_RUN_SECONDS, MIN_RUN_SECONDS, RUN_SECONDS

MIN_LESSON_MINUTES = 30
MAX_LESSON_MINUTES = 90
# Une case corrigée à la main (récréation plus longue, heure raccourcie).
MIN_SLOT_MINUTES = 5
MAX_SLOT_MINUTES = 240
MAX_LESSONS_PER_DAY = 12
MAX_TEACHER_WEEK_HOURS = 60
# Au-delà, c'est une erreur de saisie.
MAX_UNAVAILABLE = 60
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


class TeacherTimetableProfile(TenantModel):
    """Disponibilité d'un enseignant pour l'horaire (EDT.1b) [T] : charge au plus par semaine
    (contrat), heures au plus par jour, absences. Une absence est un jour entier (`{"weekday":
    5}`) ou une plage horaire (`{"weekday": 2, "start": "07:30", "end": "10:00"}`) : en heures et
    non en numéros d'heure, elle vaut pour toutes les grilles (deux vacations). Un enseignant
    partagé avec une autre école se règle ici : on ne lit jamais l'horaire de l'autre école."""

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("teacher"),
    )
    max_week_hours = models.PositiveSmallIntegerField(
        _("hours per week at most"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TEACHER_WEEK_HOURS)],
    )
    max_day_hours = models.PositiveSmallIntegerField(
        _("hours per day at most"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_LESSONS_PER_DAY)],
    )
    unavailable = models.JSONField(_("unavailable"), default=list, blank=True)

    class Meta:
        verbose_name = _("teacher timetable profile")
        verbose_name_plural = _("teacher timetable profiles")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "teacher"], name="teacher_profile_unique_per_school"
            ),
        ]

    def __str__(self) -> str:
        return str(self.teacher)


MAX_WEIGHT = 10


class TimetableRule(TenantModel):
    """Règle de l'horaire (EDT.1c, spec § 5) [T] : un kind de la liste fermée, ses paramètres
    (vérifiés par le schéma de ce kind, `constraints.py`), obligatoire ou souhait avec un poids.
    Les cours, enseignants et salles sont nommés par leur identifiant dans `params` : une règle
    dont l'objet a disparu reste, signalée par les contrôles (« sans objet »)."""

    class Kind(models.TextChoices):
        FIXED_LESSON = "fixed_lesson", _("Locked hours")
        COURSE_NOT_SLOT = "course_not_slot", _("Course kept away from some hours")
        COURSE_PART_OF_DAY = "course_part_of_day", _("Part of the day")
        PARALLEL_COURSES = "parallel_courses", _("Parallel groups")
        JOINT_COURSES = "joint_courses", _("Joint course")
        ROOM_UNAVAILABLE = "room_unavailable", _("Room closed")
        SPREAD_OVER_WEEK = "spread_over_week", _("Spread over the week")
        TEACHER_COMPACT = "teacher_compact", _("Compact day for teachers")
        TEACHER_FREE_DAY = "teacher_free_day", _("Free day")

    class Strength(models.TextChoices):
        HARD = "hard", _("Required")
        SOFT = "soft", _("Wish")

    class Source(models.TextChoices):
        MANUAL = "manual", _("Entered by hand")
        AI = "ai", _("Proposed by the assistant")

    kind = models.CharField(_("kind"), max_length=30, choices=Kind.choices)
    params = models.JSONField(_("parameters"), default=dict)
    strength = models.CharField(_("strength"), max_length=4, choices=Strength.choices)
    weight = models.PositiveSmallIntegerField(
        _("weight"), default=5, validators=[MinValueValidator(1), MaxValueValidator(MAX_WEIGHT)]
    )
    active = models.BooleanField(_("active"), default=True)
    source = models.CharField(
        _("source"), max_length=6, choices=Source.choices, default=Source.MANUAL
    )
    # La phrase d'origine, quand l'assistant l'a traduite en règle (IA.2a).
    text = models.CharField(_("original sentence"), max_length=500, blank=True)

    class Meta:
        ordering = ["-active", "created_at"]
        verbose_name = _("timetable rule")
        verbose_name_plural = _("timetable rules")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight__gte=1, weight__lte=MAX_WEIGHT),
                name="timetable_rule_weight_1_to_10",
            ),
        ]

    def __str__(self) -> str:
        return self.get_kind_display()


# Gestes gardés pour « Annuler » (EDT.2a).
HISTORY_LIMIT = 50


class Timetable(TenantModel):
    """Version de l'horaire d'une année (EDT.2a, spec § 10) [T] : brouillon, publiée ou archivée.
    Un brouillon se modifie geste par geste ; `history` garde, pour chacun des derniers gestes,
    l'état d'avant des heures touchées (« Annuler »). Publication : EDT.4."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")
        ARCHIVED = "archived", _("Archived")

    academic_year = models.ForeignKey(
        "schools.AcademicYear",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("school year"),
    )
    name = models.CharField(_("name"), max_length=80)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    valid_from = models.DateField(_("in force from"), null=True, blank=True)
    published_at = models.DateTimeField(_("published on"), null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("published by"),
    )
    based_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("copied from"),
    )
    history = models.JSONField(_("undo history"), default=list, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = _("timetable")
        verbose_name_plural = _("timetables")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year"],
                condition=models.Q(status="published"),
                name="one_published_timetable_per_year",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class TimetableEntry(TenantModel):
    """Une séance placée (EDT.2a) [T] : le cours, le jour, sa 1re heure (numéro dans la grille de
    la classe) et sa longueur. Pas de clé vers `TimeSlot` : l'enregistrement d'une grille réécrit
    ses cases ; une séance qui n'y tient plus est un conflit, pas une perte. Salle vide : à
    choisir (type exigé par le cours). Verrouillée : ne bouge plus, ni à la main ni au calcul."""

    timetable = models.ForeignKey(
        Timetable, on_delete=models.CASCADE, related_name="entries", verbose_name=_("timetable")
    )
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="+", verbose_name=_("course")
    )
    weekday = models.PositiveSmallIntegerField(
        _("day"), validators=[MinValueValidator(1), MaxValueValidator(7)]
    )
    first = models.PositiveSmallIntegerField(
        _("first lesson"), validators=[MinValueValidator(1), MaxValueValidator(MAX_LESSONS_PER_DAY)]
    )
    length = models.PositiveSmallIntegerField(
        _("hours"), validators=[MinValueValidator(1), MaxValueValidator(MAX_LESSONS_PER_DAY)]
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("room"),
    )
    locked = models.BooleanField(_("locked"), default=False)

    class Meta:
        ordering = ["weekday", "first"]
        verbose_name = _("timetable entry")
        verbose_name_plural = _("timetable entries")
        indexes = [models.Index(fields=["school", "timetable"], name="timetable_entry_by_version")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekday__gte=1, weekday__lte=7, first__gte=1, length__gte=1),
                name="timetable_entry_position",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.weekday} {self.first}+{self.length}"


class TimetableRun(TenantModel):
    """Calcul automatique d'un brouillon (EDT.3a, spec § 7) [T] : demandé une seule fois (la même
    demande renvoyée, même `request_id`, ne relance rien), fait par la file `heavy`, résultat
    écrit dans un nouveau brouillon (`result`) ; le brouillon de départ ne change pas. Impossible :
    `blocking` nomme les règles qui suffisent à le rendre impossible."""

    class Status(models.TextChoices):
        QUEUED = "queued", _("Waiting")
        RUNNING = "running", _("Calculating")
        DONE = "done", _("Done")
        INFEASIBLE = "infeasible", _("Impossible")
        TIMEOUT = "timeout", _("Not found in time")
        ERROR = "error", _("Failed")
        CANCELLED = "cancelled", _("Cancelled")

    class Scope(models.TextChoices):
        ALL = "all", _("Whole timetable")
        CLASS = "class", _("One class")
        TEACHER = "teacher", _("One teacher")

    request_id = models.UUIDField(_("request"))
    timetable = models.ForeignKey(
        Timetable, on_delete=models.CASCADE, related_name="runs", verbose_name=_("draft")
    )
    result = models.ForeignKey(
        Timetable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("calculated draft"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.QUEUED
    )
    scope = models.CharField(_("scope"), max_length=7, choices=Scope.choices, default=Scope.ALL)
    # La classe ou l'enseignant recalculé ; le reste de l'horaire ne bouge pas.
    target = models.UUIDField(_("class or teacher"), null=True, blank=True)
    time_limit = models.PositiveSmallIntegerField(
        _("time limit (seconds)"),
        default=RUN_SECONDS,
        validators=[MinValueValidator(MIN_RUN_SECONDS), MaxValueValidator(MAX_RUN_SECONDS)],
    )
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    duration_ms = models.PositiveIntegerField(_("duration (ms)"), null=True, blank=True)
    score = models.IntegerField(_("penalty"), null=True, blank=True)
    unmet = models.JSONField(_("wishes not kept"), default=list, blank=True)
    blocking = models.JSONField(_("blocking rules"), default=list, blank=True)
    peak_mb = models.PositiveIntegerField(_("memory peak (MB)"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("timetable calculation")
        verbose_name_plural = _("timetable calculations")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "request_id"], name="timetable_run_request_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.timetable} · {self.status}"


class ExamSchedule(TenantModel):
    """Horaire des interrogations ou des examens d'une période (EDT.5, spec § 11.6) [T] : une par
    période, fait par le directeur des études. Brouillon tant qu'il se règle ; publié, il ne se
    modifie plus (le rouvrir est un geste du journal)."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")

    term = models.ForeignKey(
        "schools.Term",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("period"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    published_at = models.DateTimeField(_("published on"), null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("published by"),
    )

    class Meta:
        verbose_name = _("exam timetable")
        verbose_name_plural = _("exam timetables")
        constraints = [
            models.UniqueConstraint(fields=["school", "term"], name="exam_schedule_one_per_term"),
        ]

    def __str__(self) -> str:
        return str(self.term)


class ExamSitting(TenantModel):
    """Une épreuve de l'horaire (EDT.5) [T] : le cours (donc la classe), le jour, l'heure de début
    et de fin, la salle et le surveillant. Pas de clé vers `Evaluation` : l'épreuve annonce le
    jour, la note se saisit à part (8.2)."""

    class Kind(models.TextChoices):
        QUIZ = "quiz", _("Test")
        EXAM = "exam", _("Exam")

    schedule = models.ForeignKey(
        ExamSchedule, on_delete=models.CASCADE, related_name="sittings", verbose_name=_("timetable")
    )
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="+", verbose_name=_("course")
    )
    kind = models.CharField(_("kind"), max_length=5, choices=Kind.choices, default=Kind.EXAM)
    date = models.DateField(_("date"))
    start = models.TimeField(_("start"))
    end = models.TimeField(_("end"))
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("room"),
    )
    invigilator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("invigilator"),
    )

    class Meta:
        ordering = ["date", "start"]
        verbose_name = _("exam sitting")
        verbose_name_plural = _("exam sittings")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start__lt=models.F("end")), name="sitting_ends_after_start"
            ),
        ]
        indexes = [models.Index(fields=["school", "schedule"], name="sitting_school_schedule")]

    def __str__(self) -> str:
        return f"{self.course} · {self.date}"

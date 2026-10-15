from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.schools.models import ClassGroup, Term
from apps.students.models import Enrollment

# Bornes de saisie : un maximum de bulletin va de 10 à 100 (rarement plus), une semaine compte
# 36 à 41 heures de cours au secondaire.
MAX_PERIOD_MAX = 1000
MAX_WEEKLY_HOURS = 40
# Une note : une décimale (7,5), de 0 au maximum de son évaluation (décision du 2026-10-15).
SCORE_DIGITS, SCORE_DECIMALS = 5, 1


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
    # Cours du formulaire que la classe ne suit pas (autre option) : barré sur le bulletin (tirets),
    # ni noté ni compté dans les maxima.
    is_taught = models.BooleanField(_("taught in this class"), default=True)
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


class Evaluation(TenantModel):
    """Interrogation, devoir, travail pratique ou examen d'un cours dans une période ou des
    examens [T] (8.2.1), avec son maximum, libre : la note de la période est la somme des notes
    ramenée au maximum de la période (règle de trois, `grades.period_score`), jamais stockée.
    Identifiant donné par l'appareil possible (saisie hors ligne, 8.2.3)."""

    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="evaluations", verbose_name=_("course")
    )
    # Une période ou des examens de l'année de la classe (vérifié par `grades.py`).
    term = models.ForeignKey(
        Term, on_delete=models.PROTECT, related_name="evaluations", verbose_name=_("term")
    )
    name = models.CharField(_("name"), max_length=60)
    max_score = models.PositiveSmallIntegerField(
        _("maximum"), validators=[MinValueValidator(1), MaxValueValidator(MAX_PERIOD_MAX)]
    )
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["course", "term", "order", "created_at"]
        verbose_name = _("evaluation")
        verbose_name_plural = _("evaluations")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_score__gte=1, max_score__lte=MAX_PERIOD_MAX),
                name="evaluation_max_score_range",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "course", "term"], name="evaluation_school_sheet")
        ]

    def __str__(self) -> str:
        return self.name


class Grade(TenantModel):
    """Note d'un élève à une évaluation [T] (8.2.1). Pas de ligne : pas encore notée ; une case
    vidée efface la ligne. Chaque enregistrement va au journal de l'école (`grades.py`)."""

    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="grades", verbose_name=_("evaluation")
    )
    # Un élève noté reste : l'annulation d'un import le garde (`import_cancellation.py`).
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.PROTECT, related_name="grades", verbose_name=_("enrollment")
    )
    score = models.DecimalField(_("score"), max_digits=SCORE_DIGITS, decimal_places=SCORE_DECIMALS)

    class Meta:
        verbose_name = _("grade")
        verbose_name_plural = _("grades")
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "enrollment"], name="grade_unique_per_student"
            ),
            models.CheckConstraint(condition=models.Q(score__gte=0), name="grade_not_negative"),
        ]
        indexes = [models.Index(fields=["school", "enrollment"], name="grade_school_enrollment")]

    def __str__(self) -> str:
        return str(self.score)


class GradeSheet(TenantModel):
    """État de la feuille d'un cours dans une période ou des examens [T] (8.2.2) : brouillon, puis
    envoyée au directeur des études, puis validée. Créée au premier enregistrement qui change
    quelque chose ; toute l'histoire de la feuille est dans le journal (`grades.py`)."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        SUBMITTED = "submitted", _("Sent for validation")
        VALIDATED = "validated", _("Validated")

    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="sheets", verbose_name=_("course")
    )
    term = models.ForeignKey(
        Term, on_delete=models.PROTECT, related_name="sheets", verbose_name=_("term")
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    submitted_at = models.DateTimeField(_("sent on"), null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("sent by"),
    )
    validated_at = models.DateTimeField(_("validated on"), null=True, blank=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("validated by"),
    )
    # Rouverte par le directeur des études : la date limite ne la ferme plus.
    reopened = models.BooleanField(_("reopened"), default=False)

    class Meta:
        verbose_name = _("grade sheet")
        verbose_name_plural = _("grade sheets")
        constraints = [models.UniqueConstraint(fields=["course", "term"], name="gradesheet_unique")]
        indexes = [models.Index(fields=["school", "status"], name="gradesheet_school_status")]

    def __str__(self) -> str:
        return f"{self.course} · {self.term}"


class GradeDeadline(TenantModel):
    """Date limite de saisie des notes d'une période ou des examens [T] (8.2.2), posée par le
    directeur des études ; sans ligne, pas de limite. Dernier jour de saisie compris."""

    term = models.OneToOneField(
        Term, on_delete=models.CASCADE, related_name="grade_deadline", verbose_name=_("term")
    )
    due_on = models.DateField(_("deadline"))

    class Meta:
        verbose_name = _("grade deadline")
        verbose_name_plural = _("grade deadlines")

    def __str__(self) -> str:
        return f"{self.term} · {self.due_on}"

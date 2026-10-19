from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.schools.grading import DETAILED, TOTALS
from apps.schools.models import ClassGroup, Term
from apps.students.models import Enrollment

# Bornes de saisie : un maximum de bulletin va de 10 à 100 (rarement plus), une semaine compte
# 36 à 41 heures de cours au secondaire.
MAX_PERIOD_MAX = 1000
MAX_WEEKLY_HOURS = 40
# Une note : une décimale (7,5), de 0 au maximum de son évaluation (décision du 2026-10-15).
SCORE_DIGITS, SCORE_DECIMALS = 5, 1
# Points d'une infraction : de 1 à 100 (l'exclusion se décide autrement qu'avec des points).
MAX_RULE_POINTS = 100


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
    # Saisie des points de ce cours (8.4.0) : vide = réglage de l'école (`grading.py`).
    grade_entry = models.CharField(
        _("grade entry"),
        max_length=10,
        choices=[(DETAILED, _("Detailed")), (TOTALS, _("Period total only"))],
        blank=True,
    )
    # Atelier, laboratoire : pas de seconde session. Cours échoué = reprise de la classe (8.4.1).
    resit_allowed = models.BooleanField(_("resit allowed"), default=True)
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


class DisciplineRule(TenantModel):
    """Infraction de la liste du directeur de discipline [T] (8.5.1a) : un libellé et des points.
    Une infraction retirée de la liste est désactivée, jamais effacée : les incidents passés la
    gardent."""

    label = models.CharField(_("offence"), max_length=120)
    points = models.PositiveSmallIntegerField(
        _("points"), validators=[MinValueValidator(1), MaxValueValidator(MAX_RULE_POINTS)]
    )
    is_active = models.BooleanField(_("in the list"), default=True)
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["order", "label"]
        verbose_name = _("offence")
        verbose_name_plural = _("offences")

    def __str__(self) -> str:
        return self.label


class ConductScale(TenantModel):
    """Seuil d'une cote de conduite [T] : points minimum à partir desquels la cote s'applique
    (TB, B, AB, ME, MA). Sans ligne, l'école a les seuils de départ (`discipline.DEFAULT_SCALE`)."""

    class Grade(models.TextChoices):
        TB = "TB", _("Very good")
        B = "B", _("Good")
        AB = "AB", _("Fairly good")
        ME = "ME", _("Mediocre")
        MA = "MA", _("Poor")

    grade = models.CharField(_("grade"), max_length=2, choices=Grade.choices)
    min_points = models.PositiveSmallIntegerField(_("from points"))

    class Meta:
        ordering = ["min_points"]
        constraints = [
            models.UniqueConstraint(fields=["school", "grade"], name="conduct_scale_grade_unique")
        ]

    def __str__(self) -> str:
        return f"{self.grade} ≥ {self.min_points}"


class DisciplineIncident(TenantModel):
    """Faute d'un élève [T] : les points sont copiés de l'infraction à cet instant (changer la
    liste ne réécrit pas le passé). Jamais modifié ni effacé : une annulation est un
    enregistrement lié (`IncidentCancellation`), avec motif."""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="incidents",
        verbose_name=_("enrolment"),
    )
    term = models.ForeignKey(
        Term, on_delete=models.PROTECT, related_name="incidents", verbose_name=_("term")
    )
    rule = models.ForeignKey(
        DisciplineRule,
        on_delete=models.PROTECT,
        related_name="incidents",
        verbose_name=_("offence"),
    )
    points = models.PositiveSmallIntegerField(_("points"))
    occurred_on = models.DateField(_("date"))
    note = models.CharField(_("note"), max_length=300, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("recorded by"),
    )

    class Meta:
        ordering = ["-occurred_on", "-created_at"]
        indexes = [
            models.Index(fields=["school", "enrollment", "term"], name="incident_enrollment_term")
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.rule} · {self.occurred_on}"


class IncidentCancellation(TenantModel):
    """Annulation d'un incident [T] : l'incident reste, sa ligne dit qui l'a annulé et pourquoi ;
    ses points ne comptent plus."""

    incident = models.OneToOneField(
        DisciplineIncident,
        on_delete=models.PROTECT,
        related_name="cancellation",
        verbose_name=_("incident"),
    )
    reason = models.CharField(_("reason"), max_length=300)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("cancelled by"),
    )


class ConductGrade(TenantModel):
    """Correction de la cote de conduite d'une inscription pour une période [T] (8.5.1b). Seule la
    correction est gardée : sans ligne, la cote est celle que donnent les points (elle suit donc
    une annulation d'incident). Le directeur de discipline ou la délibération (8.4) la pose avec
    un motif ; la reprendre la supprime, le journal d'audit garde chaque étape."""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="conduct_grades",
        verbose_name=_("enrolment"),
    )
    term = models.ForeignKey(
        Term, on_delete=models.PROTECT, related_name="conduct_grades", verbose_name=_("term")
    )
    grade = models.CharField(_("grade"), max_length=2, choices=ConductScale.Grade.choices)
    reason = models.CharField(_("reason"), max_length=300)
    overridden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("corrected by"),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "term"], name="conduct_grade_enrollment_term_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.term} · {self.grade}"


class ApplicationGrade(TenantModel):
    """Correction de la cote d'application d'une inscription pour une période [T] (8.5.1c). Même
    forme que `ConductGrade` : sans ligne, la cote est celle que propose le pourcentage de la
    période (elle suit donc une note changée). Le titulaire (ou la délibération, 8.4) la pose avec
    un motif ; la reprendre la supprime, le journal d'audit garde chaque étape."""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="application_grades",
        verbose_name=_("enrolment"),
    )
    term = models.ForeignKey(
        Term, on_delete=models.PROTECT, related_name="application_grades", verbose_name=_("term")
    )
    grade = models.CharField(_("grade"), max_length=2, choices=ConductScale.Grade.choices)
    reason = models.CharField(_("reason"), max_length=300)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("corrected by"),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "term"], name="application_grade_enrollment_term_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.term} · {self.grade}"


class ReportCardsReady(TenantModel):
    """« Bulletins prêts » [T] (NB.3) : le titulaire d'une classe déclare les bulletins d'une
    période (ou des examens) prêts, une fois toutes les fiches de cotes validées. Valable tant
    qu'aucune fiche de la période n'est validée après `declared_at` (renvoi puis nouvelle
    validation) : calculé à la lecture (`homeroom.ready_state`). Retirer la déclaration supprime la
    ligne ; le journal d'audit garde chaque étape."""

    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.CASCADE, related_name="+", verbose_name=_("class")
    )
    term = models.ForeignKey(
        Term, on_delete=models.PROTECT, related_name="+", verbose_name=_("term")
    )
    declared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("declared by"),
    )
    declared_at = models.DateTimeField(_("declared on"))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["class_group", "term"], name="report_cards_ready_class_term_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.class_group} · {self.term}"


class ResitGrade(TenantModel):
    """Note de repêchage d'un cours échoué [T] (8.4.1) : pourcentage obtenu à l'examen de
    repêchage, saisi par l'enseignant du cours, qui la signe (son nom et l'heure restent). Elle
    remplit la colonne « Examen de repêchage » du bulletin ; la reprendre la supprime, le journal
    d'audit garde chaque étape."""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="resit_grades",
        verbose_name=_("enrolment"),
    )
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="resit_grades", verbose_name=_("course")
    )
    percent = models.DecimalField(
        _("percentage"),
        max_digits=4,
        decimal_places=SCORE_DECIMALS,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("signed by"),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "course"], name="resit_grade_enrollment_course_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(percent__gte=0, percent__lte=100),
                name="resit_grade_percent_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.course} · {self.percent} %"


class Deliberation(TenantModel):
    """Délibération d'une classe [T] (8.4.2) : une par section de classe. Brouillon tant que les
    décisions se prennent ; « proclamée » après validation : les résultats sont alors figés dans un
    `DeliberationSnapshot`. La rouvrir (motif obligatoire) puis la proclamer de nouveau crée la
    version suivante ; les anciennes restent."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("In progress")
        PROCLAIMED = "proclaimed", _("Proclaimed")

    class_group = models.OneToOneField(
        ClassGroup,
        on_delete=models.PROTECT,
        related_name="deliberation",
        verbose_name=_("class"),
    )
    held_on = models.DateField(_("deliberation date"), null=True, blank=True)
    status = models.CharField(
        _("status"), max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    version = models.PositiveIntegerField(_("version"), default=0)
    # Motif donné en rouvrant la classe ; repris par la proclamation suivante.
    correction_reason = models.CharField(_("correction reason"), max_length=300, blank=True)

    def __str__(self) -> str:
        return f"{self.class_group} · v{self.version}"


class DeliberationDecision(TenantModel):
    """Décision prise pour un élève [T] : issue choisie, issue que le système proposait quand elle
    a été prise, et motif quand les deux diffèrent (écart signalé, compté à part)."""

    class Decision(models.TextChoices):
        PASS = "pass", _("Admitted")
        REPEAT = "repeat", _("Repeats the year")
        RESIT = "resit", _("Resit exam")
        ORIENT = "orient", _("Reoriented")
        EXCLUDE = "exclude", _("Excluded")
        DROPPED = "dropped", _("Dropped out")

    deliberation = models.ForeignKey(
        Deliberation, on_delete=models.CASCADE, related_name="decisions"
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="deliberation_decisions",
        verbose_name=_("enrolment"),
    )
    decision = models.CharField(_("decision"), max_length=10, choices=Decision.choices)
    proposed = models.CharField(_("proposed decision"), max_length=10, blank=True)
    reason = models.CharField(_("reason"), max_length=300, blank=True)
    # Reprise (8.4.7) : pourcentage obtenu hors de Mwangaza, seulement pour un élève sans aucune
    # note cette année ; dès qu'une note existe, le pourcentage calculé reprend la main.
    prior_percent = models.DecimalField(
        _("prior percentage"), max_digits=4, decimal_places=1, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["deliberation", "enrollment"], name="deliberation_decision_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(prior_percent__gte=0, prior_percent__lte=100)
                | models.Q(prior_percent__isnull=True),
                name="deliberation_prior_percent_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.decision}"


class DeliberationSnapshot(TenantModel):
    """Résultats proclamés, figés [T] : une ligne par proclamation. `rows` garde, pour chaque
    élève, le pourcentage, l'issue proposée, la décision, le motif et l'écart au moment de la
    proclamation. Le bulletin et les situations lisent la dernière version ; une correction
    ensuite n'en modifie aucune ancienne."""

    deliberation = models.ForeignKey(
        Deliberation, on_delete=models.CASCADE, related_name="snapshots"
    )
    version = models.PositiveIntegerField(_("version"))
    held_on = models.DateField(_("deliberation date"))
    proclaimed_at = models.DateTimeField(_("proclaimed at"))
    proclaimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("proclaimed by"),
    )
    reason = models.CharField(_("correction reason"), max_length=300, blank=True)
    rows = models.JSONField(_("results"), default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["deliberation", "version"], name="deliberation_snapshot_version_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.deliberation} · v{self.version}"


class PlaceConfirmation(TenantModel):
    """Place de l'année suivante proposée à un ancien [T] (8.4.5), d'après la décision proclamée :
    le parent répond au Portail (revient ou non), puis l'école inscrit. Rien n'est inscrit sans
    l'école ; la réponse se change tant qu'elle n'a pas inscrit."""

    class Status(models.TextChoices):
        OFFERED = "offered", _("Offered")
        ENROLLED = "enrolled", _("Enrolled next year")
        WITHDRAWN = "withdrawn", _("Withdrawn")

    class Answer(models.TextChoices):
        YES = "yes", _("Coming back")
        NO = "no", _("Not coming back")

    # Inscription de l'année finie : une place au plus par ancien.
    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="place_confirmation",
        verbose_name=_("enrolment"),
    )
    # Classe de l'année suivante.
    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.PROTECT,
        related_name="place_confirmations",
        verbose_name=_("class"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.OFFERED
    )
    answer = models.CharField(_("answer"), max_length=3, choices=Answer.choices, blank=True)
    answered_at = models.DateTimeField(_("answered at"), null=True, blank=True)
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("answered by"),
    )

    class Meta:
        verbose_name = _("place confirmation")
        verbose_name_plural = _("place confirmations")
        indexes = [
            models.Index(fields=["school", "class_group"], name="place_school_class"),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} → {self.class_group}"

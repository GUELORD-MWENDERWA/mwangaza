import zoneinfo
from contextlib import suppress
from functools import cache

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, TenantModel
from apps.core.money import Currency
from apps.core.tenancy import RESERVED_SUBDOMAINS
from apps.schools import (
    alerts,
    colors,
    grading,
    matricule,
    pass_rules,
    portal,
    receipts,
    reminders,
)
from apps.schools.logos import logo_path, monochrome_logo_path, validate_logo
from apps.schools.signatures import head_signature_path, stamp_path

# Le code est le sous-domaine de l'école : 2 à 30 caractères, minuscules, chiffres, tirets.
CODE_PATTERN = r"^[a-z0-9][a-z0-9-]{0,28}[a-z0-9]$"
# Goma est en UTC+2 ; Kinshasa (UTC+1) : `Africa/Kinshasa`.
DEFAULT_TIMEZONE = "Africa/Lubumbashi"


def validate_not_reserved(value: str) -> None:
    if value in RESERVED_SUBDOMAINS:
        raise ValidationError(_("This code is reserved by the platform."), code="reserved")


@cache
def _timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def validate_timezone(value: str) -> None:
    if value not in _timezones():
        raise ValidationError(
            _("Unknown time zone, e.g. Africa/Lubumbashi."), code="invalid_timezone"
        )


def default_currencies() -> list[str]:
    return [Currency.USD, Currency.CDF]


def sorted_currencies(currencies) -> list[str]:
    """Sans doublon, dans l'ordre de `Currency` (USD, puis CDF)."""
    return [currency for currency in Currency.values if currency in set(currencies)]


class School(BaseModel):
    """École [G]. Tout ce qui est propre à une école se règle ici, jamais dans le code.
    Champs de `docs/04-modele-de-donnees.md` § 1 ajoutés avec leur tâche (1.7, 3.2…)."""

    class Environment(models.TextChoices):
        """Type d'espace (`03` § 4 bis), choisi à la création et jamais changé."""

        LIVE = "live", _("Live")
        TEST = "test", _("Sandbox")
        DEMO = "demo", _("Demonstration")

    class Regime(models.TextChoices):
        PUBLIC = "public", _("Public")
        CONVENTION = "convention", _("Public, under convention")
        PRIVATE = "private", _("Private, approved")

    class Status(models.TextChoices):
        TRIAL = "trial", _("Free trial")
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")
        STOPPED = "stopped", _("Stopped")
        # Espace d'essai ou de démonstration que la tâche de fond est en train d'effacer (4.16).
        DELETING = "deleting", _("Being deleted")

    # Plus personne n'y entre ; les données restent (sauf « suppression en cours »).
    CLOSED_STATUSES = (Status.SUSPENDED, Status.STOPPED, Status.DELETING)

    code = models.CharField(
        _("code"),
        max_length=30,
        unique=True,
        validators=[
            RegexValidator(
                CODE_PATTERN,
                _("2 to 30 characters: lowercase letters, digits and hyphens (not at the ends)."),
            ),
            validate_not_reserved,
        ],
        help_text=_(
            "Subdomain of the school: {code}.mwangaza.school. Changed by the platform only: "
            "the old address stops working."
        ),
    )
    # Nom court : menu, reçu thermique, portail (M5).
    name = models.CharField(_("name"), max_length=200)
    # Reçus A4, fiches, bulletins (M5).
    official_name = models.CharField(_("official name"), max_length=255, blank=True)
    logo = models.FileField(
        _("logo"),
        upload_to=logo_path,
        blank=True,
        validators=[validate_logo],
        help_text=_("PNG or JPEG, 1 MB at most."),
    )
    # Reçus thermiques (M5) ; sans lui, le logo s'imprime en niveaux de gris.
    logo_monochrome = models.FileField(
        _("black and white logo"),
        upload_to=monochrome_logo_path,
        blank=True,
        validators=[validate_logo],
        help_text=_("For thermal receipts. PNG or JPEG, 1 MB at most."),
    )
    # Documents signés (DOC.1) : envoyés par l'API seulement (image détourée, `signatures.py`).
    stamp = models.FileField(_("school stamp"), upload_to=stamp_path, blank=True, editable=False)
    head_name = models.CharField(_("name of the head"), max_length=150, blank=True)
    head_title = models.CharField(
        _("title of the head"),
        max_length=100,
        blank=True,
        help_text=_("Under the signature, e.g. Préfet des études."),
    )
    head_signature = models.FileField(
        _("signature of the head"), upload_to=head_signature_path, blank=True, editable=False
    )
    # Code de l'école (7 chiffres) imprimé sur les bulletins (8.3.1, M5) ; vide : case à remplir
    # à la main.
    epst_code = models.CharField(
        _("EPST school code"),
        max_length=7,
        blank=True,
        validators=[RegexValidator(r"^\d{7}$", _("7 digits."))],
        help_text=_("Official code of the school, printed on report cards."),
    )
    # Lieu de l'école, en tête du bulletin (8.3.3).
    province = models.CharField(_("province"), max_length=60, blank=True)
    city = models.CharField(_("town"), max_length=80, blank=True)
    commune = models.CharField(_("commune or territory"), max_length=80, blank=True)
    # Régime de l'école (M5) : mentionné sur le bulletin.
    regime = models.CharField(_("school regime"), max_length=12, choices=Regime.choices, blank=True)
    # Q8 : choisie par l'école ; texte blanc ou encre choisi pour rester lisible (`colors.py`).
    primary_color = models.CharField(
        _("colour"),
        max_length=7,
        default=colors.DEFAULT_COLOR,
        validators=[colors.validate_school_color],
        help_text=_("Printed documents and the school badge, e.g. #0B5FCC."),
    )
    timezone = models.CharField(
        _("time zone"),
        max_length=64,
        default=DEFAULT_TIMEZONE,
        validators=[validate_timezone],
        help_text=_("Dates and times of the school, e.g. Africa/Lubumbashi (Goma)."),
    )
    enabled_currencies = ArrayField(
        models.CharField(max_length=3, choices=Currency.choices),
        verbose_name=_("currencies"),
        default=default_currencies,
    )
    # Fonctions données par la plateforme (`accounts/modules.py`, M.1) ; socle toujours actif.
    modules = ArrayField(
        models.CharField(max_length=30),
        verbose_name=_("modules"),
        default=list,
        blank=True,
    )
    default_currency = models.CharField(
        _("main currency"),
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
        help_text=_("Currency of the reports."),
    )
    # C3 : `ITIG-{AAAA}-{0000}` ; rempli à la création avec le code de l'école (`matricule.py`).
    matricule_format = models.CharField(
        _("student number format"),
        max_length=matricule.MAX_LENGTH,
        blank=True,
        validators=[matricule.validate_matricule_format],
        help_text=_("e.g. ABC-{AAAA}-{0000}: year, number, option code {OPT}."),
    )
    # C5 : sur non, ni l'inscription ni l'import ne donnent de matricule (l'école garde les siens,
    # saisis ou importés, ou n'en a pas).
    auto_matricule = models.BooleanField(_("give student numbers automatically"), default=True)
    # Réel : vraie école, jamais supprimée. Essai et démonstration : hors des chiffres de la
    # plateforme, supprimables (4.16).
    environment = models.CharField(
        _("kind of space"),
        max_length=10,
        choices=Environment.choices,
        default=Environment.LIVE,
        editable=False,
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.TRIAL
    )
    # Abonnement, saisi à la main par le super-admin en V1.0 (A2) ; facturation : 7.2.
    plan = models.CharField(
        _("plan"), max_length=50, blank=True, help_text=_("e.g. Discovery, Standard.")
    )
    trial_ends_on = models.DateField(_("end of the trial"), null=True, blank=True)
    paid_until = models.DateField(_("paid until"), null=True, blank=True)
    # Règles réglées par l'école : `receipt` (M5, `receipts.py`), plus tard les alertes (4.2).
    settings = models.JSONField(_("settings"), default=dict, blank=True)
    # Fin de la liste « Mise en route » (C4, `setup.py`) : ensuite elle n'est plus calculée.
    setup_completed_at = models.DateTimeField(
        _("setup finished at"), null=True, blank=True, editable=False
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("school")
        verbose_name_plural = _("schools")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__regex=CODE_PATTERN), name="school_code_format"
            ),
            models.CheckConstraint(
                condition=models.Q(primary_color__regex=r"^#[0-9A-F]{6}$"),
                name="school_color_format",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.matricule_format:
            self.matricule_format = matricule.default_format(self.code)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        with suppress(ValueError):  # message du validateur du champ
            self.primary_color = colors.normalize(self.primary_color)
        self.enabled_currencies = sorted_currencies(self.enabled_currencies or [])
        if not self.enabled_currencies:
            raise ValidationError(
                {"enabled_currencies": _("Choose at least one currency.")}, code="no_currency"
            )
        if self.default_currency not in self.enabled_currencies:
            message = _("The main currency must be one of the school's currencies.")
            raise ValidationError({"default_currency": message}, code="default_currency_disabled")
        if not self._state.adding:
            # Une devise utilisée par un barème (plus tard : un paiement) reste (M5).
            from apps.finance.services import currencies_in_use

            if currencies_in_use(self) - set(self.enabled_currencies):
                message = _("A currency used by a fee rule cannot be removed.")
                raise ValidationError(
                    {"enabled_currencies": ValidationError(message, code="currency_in_use")}
                )

    @property
    def is_closed(self) -> bool:
        """Suspendue, arrêtée ou en cours de suppression : ni connexion, ni portail, ni session
        support."""
        return self.status in self.CLOSED_STATUSES

    def has_module(self, code: str) -> bool:
        """L'école a ce module (`accounts/modules.py`) ; le socle est toujours actif."""
        return code in self.modules

    @staticmethod
    def portal_closed(prefix: str = "") -> Q:
        """Écoles que le portail ne sert pas : fermées, ou sans le module `portal`. `prefix` :
        chemin vers l'école (`school__`), à passer à `.exclude(...)`."""
        return Q(**{f"{prefix}status__in": School.CLOSED_STATUSES}) | ~Q(
            **{f"{prefix}modules__contains": ["portal"]}
        )

    @property
    def is_demo(self) -> bool:
        """Espace de démonstration : données fictives, comptes de la plage réservée, pas de
        double authentification (`03` § 4 bis)."""
        return self.environment == self.Environment.DEMO

    @property
    def url(self) -> str:
        """Adresse de l'école : https://{code}.mwangaza.school (`SCHOOL_URL`)."""
        return settings.SCHOOL_URL.format(code=self.code)

    @property
    def receipt(self) -> dict:
        """Réglages du reçu, valeurs par défaut comprises (`receipts.py`)."""
        return receipts.receipt_settings(self.settings)

    @property
    def alerts(self) -> dict:
        """Seuils d'alerte au directeur, valeurs par défaut comprises (`alerts.py`)."""
        return alerts.alert_settings(self.settings)

    @property
    def reminders(self) -> dict:
        """Relances aux parents, valeurs par défaut comprises (`reminders.py`)."""
        return reminders.reminder_settings(self.settings)

    @property
    def grading(self) -> dict:
        """Saisie des points : devoirs détaillés ou total de la période (`grading.py`)."""
        return grading.grading_settings(self.settings)

    @property
    def pass_rules(self) -> dict:
        """Règles de réussite et de repêchage (`pass_rules.py`)."""
        return pass_rules.pass_rules_settings(self.settings)

    @property
    def portal(self) -> dict:
        """Ce que le portail montre aux parents, valeurs par défaut comprises (`portal.py`)."""
        return portal.portal_settings(self.settings)

    @property
    def text_color(self) -> str:
        """Couleur du texte posé sur `primary_color` : blanc ou encre."""
        return colors.text_color(self.primary_color) or colors.WHITE


class Demonstration(BaseModel):
    """Espace de démonstration créé depuis la console [G] (4.17.2, `03` § 4 bis) : de quoi le
    remplir, montrer sa fiche d'accès et le remettre à zéro (`demonstrations.py`). Une ligne par
    espace, qui part avec lui ; `created_by` : qui l'a créé ou remis à zéro. Les espaces de
    `make demo` n'en ont pas."""

    class Profile(models.TextChoices):
        """Données d'exemple à y écrire (`demo.py`) : ≈ 150 ou ≈ 800 élèves."""

        SMALL = "small", _("Small school")
        LARGE = "large", _("Large school")

    class State(models.TextChoices):
        FILLING = "filling", _("Being filled")
        READY = "ready", _("Ready")
        FAILED = "failed", _("Failed")

    school = models.OneToOneField(
        School, on_delete=models.CASCADE, related_name="demonstration", verbose_name=_("school")
    )
    profile = models.CharField(_("profile"), max_length=10, choices=Profile.choices)
    # Bloc de numéros réservés de ses comptes (`DemoNumbers.block`), gardé à la remise à zéro.
    block = models.PositiveSmallIntegerField(_("block of numbers"), unique=True)
    # Mot de passe commun de ses comptes, chiffré (`core.crypto`) : la fiche d'accès le montre.
    password = models.TextField(_("password"))
    state = models.CharField(
        _("state"), max_length=10, choices=State.choices, default=State.FILLING
    )
    steps_done = models.PositiveSmallIntegerField(_("steps done"), default=0)
    steps_total = models.PositiveSmallIntegerField(_("steps"), default=0)
    # « Remettre à zéro » : la suppression en cours recrée l'espace au lieu de le laisser partir.
    reset_requested = models.BooleanField(_("reset requested"), default=False)

    class Meta:
        verbose_name = _("demonstration space")
        verbose_name_plural = _("demonstration spaces")

    def __str__(self) -> str:
        return f"{self.school} ({self.get_profile_display()})"


# Organisation scolaire (C1-C3, `docs/04-modele-de-donnees.md` § 2). Changée avec `classes.manage`
# par `organisation.py`, chaque changement noté dans le journal de l'école.


class AcademicYear(TenantModel):
    """Année scolaire [T] (« 2026-2027 »). Une seule année en cours par école : celle des
    inscriptions et des écrans par défaut."""

    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        # Clôture d'année (archivage, passage de classe) : avec la délibération (V1.2).
        CLOSED = "closed", _("Closed")

    name = models.CharField(_("name"), max_length=20)
    starts_on = models.DateField(_("start"))
    ends_on = models.DateField(_("end"))
    is_current = models.BooleanField(_("current year"), default=False)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.OPEN, editable=False
    )

    class Meta:
        ordering = ["-starts_on"]
        verbose_name = _("school year")
        verbose_name_plural = _("school years")
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="year_name_unique_per_school"),
            models.UniqueConstraint(
                fields=["school"],
                condition=models.Q(is_current=True),
                name="one_current_year_per_school",
            ),
            models.CheckConstraint(
                condition=models.Q(starts_on__lt=models.F("ends_on")), name="year_starts_first"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Term(TenantModel):
    """Découpage de l'année [T] : semestres ou trimestres, et leurs périodes et examens.

    `name` vide : l'interface affiche le nom traduit d'après le genre et la place (« 1re
    période », « Examens du 1er semestre ») ; l'école peut le renommer. Dates vides tant que
    l'école ne les a pas saisies."""

    class Kind(models.TextChoices):
        SEMESTER = "semester", _("Semester")
        TRIMESTER = "trimester", _("Term (trimester)")
        PERIOD = "period", _("Period")
        EXAM = "exam", _("Exams")

    # Genres qui regroupent des périodes et des examens.
    GROUPS = frozenset({Kind.SEMESTER, Kind.TRIMESTER})

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="terms", verbose_name=_("school year")
    )
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("semester or term"),
    )
    # Place dans l'année, tous niveaux confondus (semestre, puis ses périodes, puis le suivant).
    order = models.PositiveSmallIntegerField(_("order"))
    name = models.CharField(_("name"), max_length=60, blank=True)
    starts_on = models.DateField(_("start"), null=True, blank=True)
    ends_on = models.DateField(_("end"), null=True, blank=True)

    class Meta:
        ordering = ["order"]
        verbose_name = _("term")
        verbose_name_plural = _("terms")
        constraints = [
            # Vérifiée à la fin de la transaction : le découpage se réécrit d'un seul envoi.
            models.UniqueConstraint(
                fields=["academic_year", "order"],
                name="term_order_unique_per_year",
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.CheckConstraint(
                condition=models.Q(starts_on__isnull=True)
                | models.Q(ends_on__isnull=True)
                | models.Q(starts_on__lte=models.F("ends_on")),
                name="term_starts_first",
            ),
        ]
        indexes = [models.Index(fields=["school", "academic_year"], name="term_school_year")]

    def __str__(self) -> str:
        return self.name or self.get_kind_display()


class Level(TenantModel):
    """Niveau [T] (« 7e EB », « 3e »), dans l'ordre choisi par l'école."""

    class Cycle(models.TextChoices):
        PRIMARY = "primary", _("Primary")
        BASIC = "basic", _("Basic education (7th-8th)")
        SECONDARY_GENERAL = "secondary_general", _("General secondary")
        SECONDARY_TECHNICAL = "secondary_technical", _("Technical and vocational secondary")
        HIGHER = "higher", _("Higher education")
        VOCATIONAL = "vocational", _("Short vocational training")

    name = models.CharField(_("name"), max_length=40)
    cycle = models.CharField(_("cycle"), max_length=20, choices=Cycle.choices)
    order = models.PositiveSmallIntegerField(_("order"), default=0)
    # Texte complet du titre du bulletin (« 3ème Humanité Technique »), que l'école écrit ; vide :
    # le bulletin reprend le nom du niveau (« 3HT »).
    report_title = models.CharField(_("report card title"), max_length=80, blank=True)
    # Dernière année avant l'Examen d'État : le bulletin en reprend le bloc (8.3.3).
    has_state_exam = models.BooleanField(
        _("ends with the state exam"),
        default=False,
        help_text=_("The report card shows the state exam block instead of the resit exam."),
    )

    # Règles de réussite propres au niveau (8.4.1) : seulement les champs qui diffèrent de ceux de
    # l'école (`pass_rules.py`) ; vide : celles de l'école.
    pass_rules = models.JSONField(_("passing rules"), default=dict, blank=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("level")
        verbose_name_plural = _("levels")
        constraints = [
            models.UniqueConstraint(
                models.F("school"), Lower("name"), name="level_name_unique_per_school"
            )
        ]

    def __str__(self) -> str:
        return self.name


TRACK_CODE_PATTERN = r"^[A-Z0-9]{1,10}$"


class Track(TenantModel):
    """Option des humanités [T] (« Électricité », code `ELEC` pour le matricule)."""

    name = models.CharField(_("name"), max_length=80)
    code = models.CharField(
        _("code"),
        max_length=10,
        validators=[
            RegexValidator(
                TRACK_CODE_PATTERN, _("1 to 10 capital letters or digits."), code="invalid_code"
            )
        ],
        help_text=_("Used in the student number ({OPT}), e.g. ELEC."),
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("track")
        verbose_name_plural = _("tracks")
        constraints = [
            models.UniqueConstraint(
                models.F("school"), Lower("name"), name="track_name_unique_per_school"
            ),
            models.UniqueConstraint(fields=["school", "code"], name="track_code_unique_per_school"),
            models.CheckConstraint(
                condition=models.Q(code__regex=TRACK_CODE_PATTERN), name="track_code_format"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ClassGroup(TenantModel):
    """Classe d'une année [T] : niveau, option éventuelle, section (« 3e Électricité A »).

    Supprimée seulement si elle n'a aucun élève (les inscriptions la protègent, 2.1)."""

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="class_groups",
        verbose_name=_("school year"),
    )
    level = models.ForeignKey(
        Level, on_delete=models.PROTECT, related_name="class_groups", verbose_name=_("level")
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="class_groups",
        verbose_name=_("track"),
    )
    section = models.CharField(_("section"), max_length=10, blank=True)
    capacity = models.PositiveSmallIntegerField(
        _("capacity"), null=True, blank=True, validators=[MinValueValidator(1)]
    )
    # Une personne du personnel actif de l'école (vérifié par `organisation.py`).
    homeroom_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("homeroom teacher"),
    )

    class Meta:
        ordering = ["level__order", "level__name", "track__name", "section"]
        verbose_name = _("class")
        verbose_name_plural = _("classes")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "level", "track", "section"],
                nulls_distinct=False,
                name="class_group_unique_per_year",
            )
        ]
        indexes = [models.Index(fields=["school", "academic_year"], name="class_school_year")]

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        """« 3HT ÉLECTRICITÉ A » : en majuscules, comme sur les documents de l'école."""
        parts = [self.level.name, self.track.name if self.track else "", self.section]
        return " ".join(part for part in parts if part).upper()

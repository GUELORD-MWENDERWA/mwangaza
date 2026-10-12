from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, TenantModel
from apps.notifications.attachments import attachment_path
from apps.schools.models import ClassGroup, School
from apps.students.models import Family, Student


class Announcement(TenantModel):
    """Annonce de l'école aux familles (H4), lue dans le portail, ou à son personnel (5.7), lue
    dans la Gestion. Publiée dès sa création et jamais modifiée ensuite (elle a peut-être été
    lue) : on l'archive et on en publie une autre. Une annonce archivée ne s'affiche plus."""

    class Audience(models.TextChoices):
        ALL_FAMILIES = "all_families", _("All families")
        CLASS_GROUPS = "class_groups", _("Some classes")
        # Tout le personnel de l'école ; jamais montrée dans le portail (5.7).
        STAFF = "staff", _("Staff")

    title = models.CharField(_("title"), max_length=120)
    body = models.TextField(_("message"), max_length=4000)
    audience = models.CharField(_("recipients"), max_length=20, choices=Audience.choices)
    # Familles des élèves inscrits dans ces classes (année en cours) ; vide pour toutes.
    class_groups = models.ManyToManyField(
        ClassGroup, blank=True, related_name="announcements", verbose_name=_("classes")
    )
    attachment = models.FileField(_("attachment"), upload_to=attachment_path, blank=True)
    published_at = models.DateTimeField(_("published at"))
    archived_at = models.DateTimeField(_("archived at"), null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("archived by"),
    )

    class Meta:
        ordering = ["-published_at", "-id"]
        verbose_name = _("announcement")
        verbose_name_plural = _("announcements")
        indexes = [
            models.Index(fields=["school", "-published_at"], name="announcement_school_date")
        ]

    def __str__(self) -> str:
        return self.title


class AnnouncementRead(TenantModel):
    """Annonce lue par une famille dans le portail (une fois par famille, même si plusieurs de
    ses enfants sont visés) : « lue par N familles » dans la Gestion. `created_at` : lue le."""

    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="reads", verbose_name=_("announcement")
    )
    family = models.ForeignKey(
        Family, on_delete=models.CASCADE, related_name="+", verbose_name=_("family")
    )

    class Meta:
        verbose_name = _("announcement read")
        verbose_name_plural = _("announcements read")
        constraints = [
            models.UniqueConstraint(
                fields=["announcement", "family"], name="announcement_read_once"
            )
        ]


class SchoolEvent(TenantModel):
    """Événement du calendrier de l'école (5.7) : congé, examens, réunion de parents, activité.
    Lu par tout le personnel dans la Gestion et, s'il est pour tous, par les familles dans le
    portail. Une journée : `ends_on` = `starts_on`. Corrigeable et supprimable (ce n'est ni de
    l'argent ni une note)."""

    class Kind(models.TextChoices):
        HOLIDAY = "holiday", _("Holiday")
        EXAM = "exam", _("Exams")
        MEETING = "meeting", _("Meeting")
        ACTIVITY = "activity", _("Activity")
        OTHER = "other", _("Other")

    class Audience(models.TextChoices):
        EVERYONE = "everyone", _("Families and staff")
        STAFF = "staff", _("Staff only")

    title = models.CharField(_("title"), max_length=120)
    description = models.TextField(_("details"), max_length=1000, blank=True)
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices, default=Kind.OTHER)
    audience = models.CharField(
        _("shown to"), max_length=10, choices=Audience.choices, default=Audience.EVERYONE
    )
    starts_on = models.DateField(_("start"))
    ends_on = models.DateField(_("end"))
    # Heure de début (réunion à 9 h) ; vide : toute la journée.
    start_time = models.TimeField(_("time"), null=True, blank=True)

    class Meta:
        ordering = ["starts_on", "start_time", "id"]
        verbose_name = _("calendar event")
        verbose_name_plural = _("calendar events")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_on__lte=models.F("ends_on")),
                name="school_event_starts_first",
            )
        ]
        indexes = [models.Index(fields=["school", "ends_on"], name="school_event_school_end")]

    def __str__(self) -> str:
        return self.title


class Summons(TenantModel):
    """Convocation des parents d'un élève (5.7) : motif, jour et heure, personne à voir. Lettre
    PDF à remettre à l'élève ; le parent la voit aussi dans le portail (`seen_at`). Jamais
    modifiée (elle est peut-être imprimée ou lue) : on l'annule et on en fait une autre."""

    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="summons", verbose_name=_("student")
    )
    # Classe de l'élève le jour de la convocation (« 3e Électricité A »), telle qu'imprimée.
    class_name = models.CharField(_("class"), max_length=120)
    reason = models.TextField(_("reason"), max_length=500)
    meeting_at = models.DateTimeField(_("date and time"))
    # Personne ou bureau où se présenter : « Préfet des études », « Direction ».
    meet_with = models.CharField(_("person to see"), max_length=120)
    seen_at = models.DateTimeField(_("seen by the parent at"), null=True, blank=True)
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cancelled by"),
    )

    class Meta:
        ordering = ["-meeting_at", "-id"]
        verbose_name = _("summons")
        verbose_name_plural = _("summonses")
        indexes = [
            models.Index(fields=["school", "-meeting_at"], name="summons_school_date"),
            models.Index(fields=["student", "-meeting_at"], name="summons_student_date"),
        ]

    def __str__(self) -> str:
        return f"{self.student} — {self.meeting_at:%d/%m/%Y}"


class PlatformAnnouncement(BaseModel):
    """Annonce de la plateforme aux écoles [G] (5.4.3) : rédigée par le super-admin dans la
    console, lue par le personnel dans la Gestion (bandeau, liste). Comme une annonce d'école :
    publiée dès sa création, jamais modifiée, seulement archivée (retirée de la Gestion)."""

    class Audience(models.TextChoices):
        ALL_SCHOOLS = "all_schools", _("All schools")
        SCHOOLS = "schools", _("Some schools")

    title = models.CharField(_("title"), max_length=120)
    body = models.TextField(_("message"), max_length=2000)
    audience = models.CharField(_("recipients"), max_length=20, choices=Audience.choices)
    # Écoles visées ; vide pour toutes (une école créée ensuite ne reçoit pas les anciennes).
    schools = models.ManyToManyField(
        School, blank=True, related_name="+", verbose_name=_("schools")
    )
    published_at = models.DateTimeField(_("published at"))
    archived_at = models.DateTimeField(_("archived at"), null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("archived by"),
    )

    class Meta:
        ordering = ["-published_at", "-id"]
        verbose_name = _("platform announcement")
        verbose_name_plural = _("platform announcements")

    def __str__(self) -> str:
        return self.title


class PlatformAnnouncementRead(BaseModel):
    """Annonce de la plateforme lue par un compte [G] (bandeau fermé ou liste ouverte), une fois
    pour toutes ses écoles. `created_at` : lue le."""

    announcement = models.ForeignKey(
        PlatformAnnouncement,
        on_delete=models.CASCADE,
        related_name="reads",
        verbose_name=_("announcement"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("account"),
    )

    class Meta:
        verbose_name = _("platform announcement read")
        verbose_name_plural = _("platform announcements read")
        constraints = [
            models.UniqueConstraint(
                fields=["announcement", "user"], name="platform_announcement_read_once"
            )
        ]


class Notification(TenantModel):
    """Notification d'un compte dans une école (5.5) : gardée au centre de notifications de son
    application (Gestion ou Portail) et, sauf sorte coupée dans ses préférences, montrée sur
    l'écran de ses navigateurs abonnés (Web Push), même application fermée. Texte écrit à la
    création : dans la langue du destinataire pour les événements de l'école (`events.py`), dans
    celle de la requête pour la notification d'essai."""

    class App(models.TextChoices):
        GESTION = "gestion", _("Management app")
        PORTAIL = "portail", _("Parent portal")

    class Kind(models.TextChoices):
        TEST = "test", _("Test notification")
        PLATFORM_NEWS = "platform_news", _("Platform announcement")
        # Événements de l'école (5.6.1) : parent, puis personnel selon ses droits.
        PAYMENT_RECEIVED = "payment_received", _("Payment received")
        ANNOUNCEMENT = "announcement", _("School announcement")
        CANCELLATION_REQUEST = "cancellation_request", _("Cancellation to approve")
        CASH_DIFFERENCE = "cash_difference", _("Cash difference")
        # À heure fixe (5.6.2, `scheduled.py`) : relances au parent, alerte au personnel.
        PAYMENT_DUE = "payment_due", _("Payment due soon")
        PAYMENT_OVERDUE = "payment_overdue", _("Late payment")
        REGISTER_OPEN = "register_open", _("Register still open")
        # Communication (5.7) : annonce de l'école à son personnel, convocation au parent.
        STAFF_ANNOUNCEMENT = "staff_announcement", _("Announcement to the staff")
        SUMMONS = "summons", _("Summons")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("account"),
    )
    app = models.CharField(_("app"), max_length=10, choices=App.choices)
    kind = models.CharField(_("kind"), max_length=30, choices=Kind.choices)
    title = models.CharField(_("title"), max_length=120)
    body = models.CharField(_("message"), max_length=300, blank=True)
    # Écran à ouvrir dans l'application (adresse du routeur, ex. `/platform-news`).
    url = models.CharField(_("link"), max_length=300, blank=True)
    read_at = models.DateTimeField(_("read at"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        indexes = [
            models.Index(fields=["school", "user", "app", "-created_at"], name="notification_inbox")
        ]

    def __str__(self) -> str:
        return self.title


class ScheduledRun(TenantModel):
    """Passage du planificateur fait pour une école (5.6.2, `scheduled.py`) : une ligne par
    sorte de travail et par jour de l'école, écrite dans la transaction de ses notifications —
    rien ne part deux fois le même jour, même si un passage est rejoué. Purgée avec les vieilles
    notifications."""

    class Job(models.TextChoices):
        REMINDERS = "reminders", _("Reminders to parents")
        OPEN_REGISTERS = "open_registers", _("Registers still open")

    job = models.CharField(_("job"), max_length=20, choices=Job.choices)
    day = models.DateField(_("day"))

    class Meta:
        verbose_name = _("scheduled run")
        verbose_name_plural = _("scheduled runs")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "job", "day"], name="scheduled_run_once_a_day"
            )
        ]
        indexes = [models.Index(fields=["day"], name="scheduled_run_day")]

    def __str__(self) -> str:
        return f"{self.job} {self.day}"


class PushSubscription(BaseModel):
    """Navigateur abonné aux notifications sur l'écran d'un compte [G] (Web Push). Gestion :
    chaque adresse d'école a son service worker, donc son abonnement (`school`) ; Portail : une
    seule adresse, sans école. Supprimé quand le service de notifications le dit expiré."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name=_("account"),
    )
    app = models.CharField(_("app"), max_length=10, choices=Notification.App.choices)
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("school"),
    )
    endpoint = models.URLField(_("endpoint"), max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(_("browser"), max_length=300, blank=True)

    class Meta:
        verbose_name = _("push subscription")
        verbose_name_plural = _("push subscriptions")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(app="gestion", school__isnull=False)
                | models.Q(app="portail", school__isnull=True),
                name="push_subscription_school_for_gestion",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.app}"


class NotificationPreference(BaseModel):
    """Préférences de notification d'un compte [G], pour toutes ses écoles : sortes dont l'envoi
    sur l'écran est coupé (elles restent au centre de notifications)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
        verbose_name=_("account"),
    )
    muted = models.JSONField(_("muted kinds"), default=list, blank=True)

    class Meta:
        verbose_name = _("notification preferences")
        verbose_name_plural = _("notification preferences")

    def __str__(self) -> str:
        return str(self.user)

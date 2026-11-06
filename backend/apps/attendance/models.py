"""Cartes et présences [T] (lot 10, `docs/04` § Présences).

Une carte (`IdCard`) est une clé d'identité : son QR porte un jeton aléatoire que le serveur ne
garde jamais, seulement son empreinte. Un passage (`AttendanceRecord`) n'est jamais modifié ni
supprimé ; la séance « entrée » d'un jour (`AttendanceSession`) naît au premier passage. Les
lecteurs et l'appel en classe (lot 16) ajouteront leurs séances aux mêmes tables."""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel

# Une carte est celle d'un élève ou d'un membre du personnel, jamais des deux.
ONE_HOLDER = Q(student__isnull=False, member__isnull=True) | Q(
    student__isnull=True, member__isnull=False
)


class IdCard(TenantModel):
    """Carte d'élève ou du personnel (6.1). `token_hash` : empreinte SHA-256 du jeton du QR, que
    seul le PDF imprimé à l'émission contient ; `last4` : ses 4 derniers signes, montrés pour
    reconnaître la carte. Jamais modifiée sauf sa révocation (perdue, remplacée, départ) ; une
    seule carte active par personne."""

    class RevokeReason(models.TextChoices):
        LOST = "lost", _("Lost")
        REPLACED = "replaced", _("Replaced by a new card")
        LEFT = "left", _("Left the school")

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cards",
        verbose_name=_("student"),
    )
    member = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cards",
        verbose_name=_("staff member"),
    )
    # N° imprimé sur la carte, séquentiel par école (registre des cartes délivrées), jamais le
    # jeton du QR.
    number = models.PositiveIntegerField(_("card number"), editable=False)
    token_hash = models.CharField(_("token fingerprint"), max_length=64, unique=True)
    # Empreinte de ce que la carte imprime de la personne (noms, naissance, classe, matricule,
    # photo…) : différente aujourd'hui = carte « à réimprimer » (`cards.face_fingerprint`).
    face_hash = models.CharField(_("printed data fingerprint"), max_length=16, blank=True)
    last4 = models.CharField(_("last signs of the token"), max_length=4)
    valid_until = models.DateField(_("valid until"))
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("revoked by"),
    )
    revoke_reason = models.CharField(
        _("reason"), max_length=10, choices=RevokeReason.choices, blank=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("card")
        verbose_name_plural = _("cards")
        constraints = [
            models.CheckConstraint(condition=ONE_HOLDER, name="idcard_one_holder"),
            models.UniqueConstraint(fields=["school", "number"], name="idcard_number_per_school"),
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(revoked_at__isnull=True, student__isnull=False),
                name="idcard_one_active_per_student",
            ),
            models.UniqueConstraint(
                fields=["member"],
                condition=Q(revoked_at__isnull=True, member__isnull=False),
                name="idcard_one_active_per_member",
            ),
        ]
        indexes = [
            models.Index(
                fields=["school", "created_at"],
                condition=Q(revoked_at__isnull=True),
                name="idcard_active",
            )
        ]

    def __str__(self) -> str:
        return f"N° {self.number:04d}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class AttendanceSession(TenantModel):
    """Séance de présence : l'entrée d'un jour (`entrance`), une par école et par jour, créée au
    premier passage. L'appel en classe et les lecteurs de salle (lot 16) ajouteront leurs
    séances (cours, salle, heures)."""

    class Kind(models.TextChoices):
        ENTRANCE = "entrance", _("Entrance")

    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    date = models.DateField(_("date"))

    class Meta:
        ordering = ["-date"]
        verbose_name = _("attendance session")
        verbose_name_plural = _("attendance sessions")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "date"],
                condition=Q(kind="entrance"),
                name="attendance_one_entrance_per_day",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.date:%d/%m/%Y}"


class AttendanceRecord(TenantModel):
    """Passage d'une personne à une séance (6.3) : jamais modifié ni supprimé, une correction est
    une ligne à part. `id` : UUID v7 donné par l'appareil ; `seen_at` : heure de l'appareil. Une
    personne passe une fois par séance (« déjà passé » ensuite)."""

    class Method(models.TextChoices):
        QR = "qr", _("Card (QR code)")
        MANUAL = "manual", _("Student number typed")

    class Status(models.TextChoices):
        PRESENT = "present", _("Arrived")
        LATE = "late", _("Late")

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.PROTECT,
        related_name="records",
        verbose_name=_("session"),
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name=_("student"),
    )
    member = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name=_("staff member"),
    )
    card = models.ForeignKey(
        IdCard,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="records",
        verbose_name=_("card"),
    )
    device = models.ForeignKey(
        "sync.Device",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name=_("device"),
    )
    seen_at = models.DateTimeField(_("seen at"))
    method = models.CharField(_("method"), max_length=10, choices=Method.choices)
    status = models.CharField(_("status"), max_length=10, choices=Status.choices)

    class Meta:
        ordering = ["seen_at"]
        verbose_name = _("attendance record")
        verbose_name_plural = _("attendance records")
        constraints = [
            models.CheckConstraint(condition=ONE_HOLDER, name="attendance_record_one_holder"),
            models.UniqueConstraint(
                fields=["session", "student"],
                condition=Q(student__isnull=False),
                name="attendance_once_per_student",
            ),
            models.UniqueConstraint(
                fields=["session", "member"],
                condition=Q(member__isnull=False),
                name="attendance_once_per_member",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.session} · {self.seen_at:%H:%M}"


class AttendanceCorrection(TenantModel):
    """Correction d'une présence au journal (6.5) : « présent en classe, carte oubliée », retard
    excusé, passage d'un autre… Jamais modifiée ni effacée ; la plus récente d'une personne pour
    un jour l'emporte sur le passage (`record`, vide s'il n'y en a pas). Toujours au journal
    d'audit."""

    class Status(models.TextChoices):
        PRESENT = "present", _("Arrived")
        LATE = "late", _("Late")
        ABSENT = "absent", _("Absent")

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.PROTECT,
        related_name="corrections",
        verbose_name=_("session"),
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_corrections",
        verbose_name=_("student"),
    )
    member = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_corrections",
        verbose_name=_("staff member"),
    )
    record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrections",
        verbose_name=_("corrected record"),
    )
    status = models.CharField(_("status"), max_length=10, choices=Status.choices)
    previous_status = models.CharField(_("status before"), max_length=10, choices=Status.choices)
    reason = models.CharField(_("reason"), max_length=200)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("attendance correction")
        verbose_name_plural = _("attendance corrections")
        constraints = [
            models.CheckConstraint(condition=ONE_HOLDER, name="attendance_correction_one_holder")
        ]
        indexes = [models.Index(fields=["session", "created_at"], name="attendance_corr_session")]

    def __str__(self) -> str:
        return f"{self.session} · {self.get_status_display()}"


def justification_path(justification, filename: str) -> str:
    return f"attendance/{justification.school_id}/{justification.pk}/{filename}"


class AbsenceJustification(TenantModel):
    """Justification d'une absence (6.6), du `starts_on` au `ends_on` : envoyée par le parent
    depuis le Portail (en attente), ou notée par l'école (acceptée d'emblée). Seule sa décision
    change, une fois (acceptée ou refusée, au journal d'audit). `document` : certificat privé,
    photo ré-encodée ou PDF de 5 Mo au plus."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        REFUSED = "refused", _("Refused")

    class Source(models.TextChoices):
        PORTAL = "portal", _("Sent by the parent")
        SCHOOL = "school", _("Recorded by the school")

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="absence_justifications",
        verbose_name=_("student"),
    )
    starts_on = models.DateField(_("from"))
    ends_on = models.DateField(_("to"))
    reason = models.CharField(_("reason"), max_length=300)
    document = models.FileField(_("certificate"), upload_to=justification_path, blank=True)
    source = models.CharField(_("sent by"), max_length=10, choices=Source.choices)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    decided_at = models.DateTimeField(_("decided at"), null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("decided by"),
    )
    decision_note = models.CharField(_("answer to the parent"), max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("absence justification")
        verbose_name_plural = _("absence justifications")
        constraints = [
            models.CheckConstraint(
                condition=Q(starts_on__lte=models.F("ends_on")), name="justification_starts_first"
            )
        ]
        indexes = [
            models.Index(fields=["school", "status", "created_at"], name="justification_status"),
            models.Index(fields=["student", "ends_on"], name="justification_student_end"),
        ]

    def __str__(self) -> str:
        return f"{self.student} · {self.starts_on:%d/%m/%Y}"

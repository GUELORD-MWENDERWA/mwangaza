"""Élèves et familles (`docs/04-modele-de-donnees.md` § 3).

Chaque école a sa propre copie de l'élève et de sa famille (décision Q10) : une école ne voit
jamais qu'un élève ou une famille existe aussi ailleurs. Changés par `services.py` seulement,
chaque changement noté au journal (domaine `students`)."""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.phone import PhoneNumberField
from apps.core.models import TenantModel
from apps.schools.models import AcademicYear, ClassGroup
from apps.students.photos import photo_path

# Code famille : sans 0, O, 1, I ni L, qu'un parent confond en le recopiant.
FAMILY_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
FAMILY_CODE_LENGTH = 8


class Family(TenantModel):
    """Famille d'élèves d'une école [T]. Son code, remis aux parents, active le portail."""

    # Unique sur toute la plateforme : le portail retrouve la famille sans connaître l'école.
    code = models.CharField(_("family code"), max_length=FAMILY_CODE_LENGTH, unique=True)
    # Compte parent relié à l'activation du portail (V1.0 : H1).
    primary_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("parent account"),
    )
    activated_at = models.DateTimeField(_("activated at"), null=True, blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = _("family")
        verbose_name_plural = _("families")

    def __str__(self) -> str:
        return self.code


class Guardian(TenantModel):
    """Parent ou tuteur, contact d'une famille [T]."""

    class Relationship(models.TextChoices):
        FATHER = "father", _("Father")
        MOTHER = "mother", _("Mother")
        GUARDIAN = "guardian", _("Guardian")
        GRANDPARENT = "grandparent", _("Grandparent")
        SIBLING = "sibling", _("Brother or sister")
        OTHER = "other", _("Other")

    family = models.ForeignKey(
        Family, on_delete=models.CASCADE, related_name="guardians", verbose_name=_("family")
    )
    full_name = models.CharField(_("full name"), max_length=150)
    relationship = models.CharField(_("relationship"), max_length=20, choices=Relationship.choices)
    phone = PhoneNumberField(_("phone"), blank=True)
    email = models.EmailField(_("email"), blank=True)
    is_primary = models.BooleanField(_("main contact"), default=False)
    is_emergency_contact = models.BooleanField(_("emergency contact"), default=False)

    class Meta:
        ordering = ["-is_primary", "full_name"]
        verbose_name = _("guardian")
        verbose_name_plural = _("guardians")

    def __str__(self) -> str:
        return self.full_name


class Student(TenantModel):
    """Élève d'une école [T].

    Le matricule est donné à sa première inscription dans l'école et gardé toute sa scolarité
    (décision du 2026-09-27) ; vide tant qu'il n'est pas inscrit."""

    class Sex(models.TextChoices):
        MALE = "M", _("Male")
        FEMALE = "F", _("Female")

    family = models.ForeignKey(
        Family, on_delete=models.PROTECT, related_name="students", verbose_name=_("family")
    )
    matricule = models.CharField(_("student number"), max_length=60, blank=True)
    last_name = models.CharField(_("last name"), max_length=80)
    middle_name = models.CharField(_("middle name"), max_length=80, blank=True)
    first_name = models.CharField(_("first name"), max_length=80, blank=True)
    sex = models.CharField(_("sex"), max_length=1, choices=Sex.choices)
    birth_date = models.DateField(_("date of birth"), null=True, blank=True)
    birth_place = models.CharField(_("place of birth"), max_length=120, blank=True)
    nationality = models.CharField(_("nationality"), max_length=60, blank=True)
    origin_province = models.CharField(_("province of origin"), max_length=60, blank=True)
    origin_territory = models.CharField(_("territory of origin"), max_length=80, blank=True)
    # Commune, quartier, avenue, numéro.
    address = models.JSONField(_("address"), default=dict, blank=True)
    photo = models.FileField(_("photo"), upload_to=photo_path, blank=True)
    photo_consent = models.BooleanField(_("photo consent"), default=False)
    previous_school = models.CharField(_("previous school"), max_length=200, blank=True)

    class Meta:
        ordering = ["last_name", "middle_name", "first_name"]
        verbose_name = _("student")
        verbose_name_plural = _("students")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "matricule"],
                condition=~Q(matricule=""),
                name="student_matricule_unique_per_school",
            )
        ]
        indexes = [
            models.Index(fields=["school", "last_name", "first_name"], name="student_school_name")
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        """« KASEREKA Muhindo Jean » : nom, post-nom, prénom, comme sur les listes de classe."""
        parts = [self.last_name, self.middle_name, self.first_name]
        return " ".join(part for part in parts if part)


class Enrollment(TenantModel):
    """Inscription d'un élève pour une année scolaire [T] : une par élève et par année.

    Protège la classe : une classe qui a des élèves ne se supprime pas (C2)."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        TRANSFERRED = "transferred", _("Transferred")
        DROPPED = "dropped", _("Dropped out")
        EXCLUDED = "excluded", _("Excluded")
        GRADUATED = "graduated", _("Graduated")

    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="enrollments", verbose_name=_("student")
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name=_("school year"),
    )
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.PROTECT, related_name="enrollments", verbose_name=_("class")
    )
    status = models.CharField(
        _("status"), max_length=12, choices=Status.choices, default=Status.ACTIVE
    )
    enrolled_on = models.DateField(_("enrolled on"), default=timezone.localdate)
    left_on = models.DateField(_("left on"), null=True, blank=True)

    class Meta:
        ordering = ["-academic_year__starts_on"]
        verbose_name = _("enrollment")
        verbose_name_plural = _("enrollments")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "academic_year"],
                name="enrollment_unique_per_year",
            )
        ]
        indexes = [
            models.Index(fields=["school", "class_group", "status"], name="enrollment_class_status")
        ]

    def __str__(self) -> str:
        return f"{self.student} — {self.academic_year}"


class MatriculeSequence(TenantModel):
    """Dernier numéro de matricule donné dans une année [T] (séquence par école et par année).
    Ligne verrouillée pendant l'inscription : deux inscriptions simultanées n'ont jamais le même
    numéro."""

    academic_year = models.OneToOneField(
        AcademicYear, on_delete=models.CASCADE, related_name="+", verbose_name=_("school year")
    )
    last_number = models.PositiveIntegerField(_("last number"), default=0)

    class Meta:
        verbose_name = _("student number sequence")
        verbose_name_plural = _("student number sequences")

    def __str__(self) -> str:
        return f"{self.academic_year} : {self.last_number}"

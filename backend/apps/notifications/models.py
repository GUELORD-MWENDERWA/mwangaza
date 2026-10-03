from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, TenantModel
from apps.notifications.attachments import attachment_path
from apps.schools.models import ClassGroup, School
from apps.students.models import Family


class Announcement(TenantModel):
    """Annonce de l'école aux familles (H4), lue dans le portail. Publiée dès sa création et
    jamais modifiée ensuite (des familles l'ont peut-être lue) : on l'archive et on en publie une
    autre. Une annonce archivée ne s'affiche plus dans le portail."""

    class Audience(models.TextChoices):
        ALL_FAMILIES = "all_families", _("All families")
        CLASS_GROUPS = "class_groups", _("Some classes")

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

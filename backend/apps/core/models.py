"""Modèles de base : identifiant UUID v7, dates, auteur, et lien obligatoire à une école
(`TenantModel`)."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.phone import PhoneNumberField
from apps.core import platform
from apps.core.ids import uuid7
from apps.core.tenancy import (
    AllSchoolsManager,
    CrossSchoolError,
    SchoolNotSetError,
    TenantManager,
    get_current_school,
)


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    # Rempli par les services ; vide pour ce que crée le système (migrations, `make demo`).
    # Un compte n'est jamais supprimé (on le désactive) : PROTECT garde l'auteur.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
        verbose_name=_("created by"),
    )

    class Meta:
        abstract = True


class TenantModel(BaseModel):
    """Donnée d'une école [T]. Lecture : `objects` ne voit que l'école courante et lève une erreur
    sans école. Écriture : l'école est remplie depuis l'école courante ; toute écriture ou
    suppression qui toucherait une autre école lève `CrossSchoolError`."""

    # Pas d'accès inverse depuis l'école (`school.note_set`) : on lit toujours depuis le modèle.
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
        verbose_name=_("school"),
    )

    objects = TenantManager()
    all_schools = AllSchoolsManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.check_school()
        super().save(*args, **kwargs)
        self._school_id_in_db = self.school_id

    def delete(self, *args, **kwargs):
        self._check_current_school()
        return super().delete(*args, **kwargs)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # École en base au chargement : une ligne ne change jamais d'école.
        instance._school_id_in_db = instance.__dict__.get("school_id")
        return instance

    def check_school(self) -> None:
        """Contrôles faits avant chaque écriture (`save`, `bulk_create`)."""
        if self.school_id is None:
            current = get_current_school()
            if current is None:
                raise SchoolNotSetError("Ligne sans école et aucune école courante.")
            self.school = current
        self._check_current_school()
        school_id_in_db = getattr(self, "_school_id_in_db", None)
        if school_id_in_db is not None and school_id_in_db != self.school_id:
            raise CrossSchoolError(
                "Une ligne ne change jamais d'école : un transfert est une copie (décision Q10)."
            )
        self._check_links()

    def _check_current_school(self) -> None:
        current = get_current_school()
        if current is not None and self.school_id != current.pk:
            raise CrossSchoolError(
                f"{type(self).__name__} appartient à une autre école que l'école courante."
            )

    def _check_links(self) -> None:
        """Refuse un lien (clé étrangère) vers une ligne d'une autre école."""
        for field in self._meta.concrete_fields:
            if not isinstance(field, models.ForeignKey) or field.name == "school":
                continue
            if not issubclass(field.related_model, TenantModel):
                continue
            value = getattr(self, field.attname)
            if value is None:
                continue
            if field.is_cached(self):
                related = field.get_cached_value(self)
                related_school_id = getattr(related, "school_id", None)
                if related_school_id is None:
                    continue
            else:
                related_school_id = (
                    field.related_model.all_schools.filter(**{field.target_field.attname: value})
                    .values_list("school_id", flat=True)
                    .first()
                )
                # Ligne invisible : absente, ou d'une autre école que la base cache (S.6). La
                # vérification de la clé étrangère par PostgreSQL, elle, ne voit pas ces règles.
                if related_school_id is None:
                    raise CrossSchoolError(
                        f"{type(self).__name__}.{field.name} pointe vers une ligne introuvable."
                    )
            if related_school_id != self.school_id:
                raise CrossSchoolError(
                    f"{type(self).__name__}.{field.name} pointe vers une ligne d'une autre école."
                )


class PlatformSettings(models.Model):
    """Identité de la plateforme (5.1) : une seule ligne, lue partout (Gestion, Portail, PDF,
    administration, manifestes des applications). Les valeurs par défaut ci-dessous sont celles
    du départ, le seul endroit du code où figure le nom : ensuite, on les change sans code."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(_("name"), max_length=60, default="Mwangaza")
    short_name = models.CharField(
        _("short name"),
        max_length=20,
        default="Mwangaza",
        help_text=_("Under the application icon on the home screen (12 characters is best)."),
    )
    # Le nom seul (« Mwangaza », mot swahili très répandu) se perd dans les résultats : le site
    # public, ses aperçus partagés et l'espace parents prennent ce nom complet (WEB.1c).
    site_name = models.CharField(
        _("name in search results"),
        max_length=60,
        default="Mwangaza School",
        help_text=_(
            "Titles of the public site, search results, previews shared on WhatsApp. A common "
            "name gets lost in the results: add a word to it."
        ),
    )
    logo = models.FileField(
        _("logo"),
        upload_to=platform.logo_path,
        blank=True,
        validators=[platform.validate_logo],
        help_text=_(
            "PNG, JPEG or SVG, 1 MB at most. Without it: the default symbol (M and flame)."
        ),
    )
    icon = models.FileField(
        _("application icon"),
        upload_to=platform.icon_path,
        blank=True,
        validators=[platform.validate_icon],
        help_text=_("Square PNG of at least 512 x 512 pixels. Without it: the default symbol."),
    )
    primary_color = models.CharField(
        _("main colour"),
        max_length=7,
        default="#0B5FCC",
        validators=[platform.validate_primary_color],
        help_text=_("Buttons and links of the interface."),
    )
    accent_color = models.CharField(
        _("accent colour"),
        max_length=7,
        default="#F2B632",
        validators=[platform.validate_accent_color],
        help_text=_("Mark and highlights on the dark menu."),
    )
    support_phone = PhoneNumberField(_("support phone"), blank=True)
    support_email = models.EmailField(_("support email"), blank=True)
    legal_notice = models.TextField(_("legal notice"), blank=True)
    # Adresse et réseaux (WEB.1d) : pied de page et page Démonstration du site, données
    # structurées (`address`, `sameAs`). Vides : rien d'affiché. Pays : la RDC.
    address = models.CharField(
        _("address"), max_length=120, blank=True, help_text=_("Street, number, district.")
    )
    city = models.CharField(_("town"), max_length=60, blank=True, default="Goma")
    region = models.CharField(_("province"), max_length=60, blank=True, default="Nord-Kivu")
    whatsapp_url = models.URLField(
        "WhatsApp", blank=True, validators=[platform.SocialLinkValidator("whatsapp_url")]
    )
    facebook_url = models.URLField(
        "Facebook", blank=True, validators=[platform.SocialLinkValidator("facebook_url")]
    )
    instagram_url = models.URLField(
        "Instagram", blank=True, validators=[platform.SocialLinkValidator("instagram_url")]
    )
    linkedin_url = models.URLField(
        "LinkedIn", blank=True, validators=[platform.SocialLinkValidator("linkedin_url")]
    )
    youtube_url = models.URLField(
        "YouTube", blank=True, validators=[platform.SocialLinkValidator("youtube_url")]
    )
    tiktok_url = models.URLField(
        "TikTok", blank=True, validators=[platform.SocialLinkValidator("tiktok_url")]
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("platform identity")
        verbose_name_plural = _("platform identity")
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="platform_settings_single_row")
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.primary_color = self.primary_color.upper()
        self.accent_color = self.accent_color.upper()
        super().save(*args, **kwargs)

    @property
    def logo_url(self) -> str | None:
        return platform.file_url(self.logo, "logo")

    @property
    def icon_url(self) -> str | None:
        return platform.file_url(self.icon, "icon")

    @classmethod
    def load(cls) -> "PlatformSettings":
        """La ligne de la plateforme, créée avec les valeurs de départ si elle manque."""
        return cls.objects.get_or_create(pk=1)[0]

    def social_links(self) -> list[tuple[str, str]]:
        """(Nom du réseau, lien) des réseaux remplis, dans l'ordre de l'identité."""
        return [
            (str(self._meta.get_field(field).verbose_name), getattr(self, field))
            for field in platform.SOCIAL_HOSTS
            if getattr(self, field)
        ]


class DemoRequest(models.Model):
    """Demande de démonstration envoyée par le site public (WEB.1d). Donnée de la plateforme, pas
    d'une école (aucune n'existe encore) : lue par le super-admin dans la console seulement.
    Aucune adresse IP gardée ; effacée un an après son envoi (`demo_requests.purge`)."""

    class Role(models.TextChoices):
        PREFECT = "prefect", _("Prefect of studies")
        PROMOTER = "promoter", _("Promoter")
        HEAD = "head", _("Head teacher")
        ACCOUNTANT = "accountant", _("Accountant")
        OTHER = "other", _("Other")

    class Size(models.TextChoices):
        SMALL = "lt300", _("Fewer than 300")
        MEDIUM = "300-800", _("300 to 800")
        LARGE = "800-1500", _("800 to 1,500")
        XLARGE = "gt1500", _("More than 1,500")

    class Status(models.TextChoices):
        NEW = "new", _("New")
        CALLED = "called", _("Called back")
        TRIAL = "trial", _("Trial space opened")
        DROPPED = "dropped", _("No follow-up")

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    created_at = models.DateTimeField(_("received at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    name = models.CharField(_("full name"), max_length=120)
    role = models.CharField(_("role"), max_length=12, choices=Role.choices)
    school_name = models.CharField(_("school"), max_length=120)
    town = models.CharField(_("town"), max_length=60)
    phone = PhoneNumberField(_("phone"))
    size = models.CharField(_("number of pupils"), max_length=8, choices=Size.choices, blank=True)
    email = models.EmailField(_("email"), blank=True)
    message = models.TextField(_("message"), max_length=1000, blank=True)
    language = models.CharField(_("language"), max_length=2, default="fr")
    status = models.CharField(
        _("follow-up"), max_length=8, choices=Status.choices, default=Status.NEW
    )
    notes = models.TextField(_("internal note"), max_length=2000, blank=True)

    class Meta:
        verbose_name = _("demo request")
        verbose_name_plural = _("demo requests")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"], name="demorequest_status")]

    def __str__(self) -> str:
        return f"{self.school_name} — {self.name}"


def print_path(job: "PrintJob", filename: str) -> str:
    return f"print/{job.school_id}/{job.pk}-{filename}"


class PrintJob(TenantModel):
    """Document lourd en cours de fabrication ou prêt (PERF.1) : un PDF de plusieurs dizaines de
    pages ne se fait jamais dans la requête web. La requête dépose le document (`source`), un
    travailleur à part le met en PDF par paquets, et la même adresse rend le PDF une fois prêt.
    Propre à la personne qui l'a demandé (`created_by`) ; effacé au bout d'un jour."""

    class Status(models.TextChoices):
        QUEUED = "queued", _("Queued")
        RUNNING = "running", _("Running")
        DONE = "done", _("Done")
        FAILED = "failed", _("Failed")

    # Empreinte de la demande (personne, école, adresse et filtres) : recharger l'adresse retrouve
    # le même travail au lieu d'en lancer un autre.
    key = models.CharField(max_length=64)
    name = models.CharField(_("file name"), max_length=120)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.QUEUED)
    pages = models.PositiveIntegerField(default=0)
    pages_done = models.PositiveIntegerField(default=0)
    source = models.FileField(upload_to=print_path, blank=True)
    pdf = models.FileField(upload_to=print_path, blank=True)
    error = models.CharField(max_length=200, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["school", "created_by", "key"], name="printjob_lookup")]

    def __str__(self) -> str:
        return self.name


def kept_path(document: "KeptDocument", filename: str) -> str:
    return f"kept/{document.school_id}/{document.pk}-{filename}"


class KeptDocument(TenantModel):
    """PDF d'une pièce (un bulletin) gardé pour être servi sans nouveau calcul (PERF.2). `key` est
    l'empreinte de tout ce qui fait le document (notes, élève, gabarit, réglages de l'école) : si
    l'un d'eux change, la clé change et l'ancien fichier (même `subject` et `variant`) est effacé
    à la fabrication du nouveau. Un fichier non relu depuis longtemps est purgé."""

    kind = models.CharField(max_length=24)
    subject = models.UUIDField()  # l'inscription du bulletin
    variant = models.CharField(max_length=24, blank=True)
    key = models.CharField(max_length=64)
    file = models.FileField(upload_to=kept_path)
    size = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "key"], name="kept_key_unique")]
        indexes = [
            models.Index(fields=["school", "kind", "subject", "variant"], name="kept_subject")
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.subject}"

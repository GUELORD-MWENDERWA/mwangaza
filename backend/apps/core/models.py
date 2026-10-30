"""Modèles de base : identifiant UUID v7, dates, auteur, et lien obligatoire à une école
(`TenantModel`)."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.phone import PhoneNumberField
from apps.core import platform
from apps.core.ids import uuid7
from apps.core.money import Currency
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
        help_text=_("PNG, JPEG or SVG, 1 MB at most. Without it: the default symbol and the name."),
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
        default="#1A2F80",
        validators=[platform.validate_primary_color],
        help_text=_("Menus, buttons and links of the interface."),
    )
    accent_color = models.CharField(
        _("accent colour"),
        max_length=7,
        default="#FFA81E",
        validators=[platform.validate_accent_color],
        help_text=_("Sun of the symbol and highlights on the menu (rarely)."),
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

    def clean(self) -> None:
        platform.check_colors(self.primary_color, self.accent_color)

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


class SiteEntry(BaseModel):
    """Contenu du site public tenu dans la console par la communication (SITE.1a) : question de
    l'accueil ou des parents, fonction « Prochainement ». Titre et texte en français, et en
    anglais (vide : la page anglaise montre le français) ; texte simple, toujours échappé. Aucune
    école : c'est la plateforme. Lu par le site à travers le cache de `site_content.py`."""

    class Kind(models.TextChoices):
        HOME_QUESTION = "home_question", _("Home page question")
        PARENT_QUESTION = "parent_question", _("Parents page question")
        UPCOMING = "upcoming", _("Coming soon")

    MAX_PER_KIND = 20  # liste courte : pas de pagination, et un site qui reste lisible

    kind = models.CharField(_("kind"), max_length=20, choices=Kind.choices)
    title_fr = models.CharField(_("title in French"), max_length=160)
    title_en = models.CharField(_("title in English"), max_length=160, blank=True)
    text_fr = models.TextField(_("text in French"), max_length=1500)
    text_en = models.TextField(_("text in English"), max_length=1500, blank=True)
    position = models.PositiveSmallIntegerField(_("position"), default=0)
    published = models.BooleanField(_("published"), default=False)

    class Meta:
        ordering = ["kind", "position", "created_at"]
        verbose_name = _("site content")
        verbose_name_plural = _("site contents")

    def __str__(self) -> str:
        return self.title_fr


class SiteBanner(models.Model):
    """Bandeau d'annonce du site public (SITE.1a), au-dessus de l'en-tête de chaque page : une
    seule ligne (clé 1). Affiché s'il est actif, entre `starts_on` et `ends_on` (bornes
    comprises, facultatives). Lien : une page du site (`/…`) ou une adresse `https://`."""

    text_fr = models.CharField(_("text in French"), max_length=160, blank=True)
    text_en = models.CharField(_("text in English"), max_length=160, blank=True)
    link = models.CharField(_("link"), max_length=300, blank=True)
    starts_on = models.DateField(_("from"), null=True, blank=True)
    ends_on = models.DateField(_("until"), null=True, blank=True)
    active = models.BooleanField(_("shown"), default=False)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("site banner")
        verbose_name_plural = _("site banner")
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="site_banner_single_row")
        ]

    def __str__(self) -> str:
        return self.text_fr

    @classmethod
    def load(cls) -> "SiteBanner":
        return cls.objects.get_or_create(pk=1)[0]

    def state(self, today) -> str:
        """`shown`, `scheduled` (pas encore), `ended` (passé) ou `hidden`."""
        if not (self.active and self.text_fr):
            return "hidden"
        if self.starts_on and today < self.starts_on:
            return "scheduled"
        if self.ends_on and today > self.ends_on:
            return "ended"
        return "shown"


def site_consent_path(item, filename: str) -> str:
    """Accord écrit (témoignage, photo d'élève) : stockage privé, jamais servi par le site."""
    return f"site/consents/{item.pk}-{filename}"


def site_photo_path(photo: "SitePhoto", filename: str) -> str:
    """Nom fixé par le service (`<id>-1600.webp`, `<id>-600.webp`) : l'adresse publique
    `/photos/<nom>` le lit sans passer par la base."""
    return f"site/photos/{filename}"


class SitePhoto(BaseModel):
    """Photo de la photothèque du site public (SITE.3) : ré-encodée à l'envoi en WebP de deux
    largeurs (`large` 1 600 px, `small` 600 px), sans métadonnées, l'original jeté. Une photo où
    l'on reconnaît un élève, ou prise avec un accord écrit, n'existe qu'avec cet accord déposé
    (`consent`, privé) : toute photo de la photothèque peut donc être montrée. Le crédit
    (`credit`, `license`, `source_url`) est repris dans les mentions légales."""

    class License(models.TextChoices):
        CC0 = "cc0", "CC0"
        PUBLIC_DOMAIN = "public_domain", _("Public domain")
        CC_BY = "cc_by", "CC BY"
        CC_BY_SA = "cc_by_sa", "CC BY-SA"
        CONSENT = "consent", _("Written consent")

    large = models.FileField(upload_to=site_photo_path)
    small = models.FileField(upload_to=site_photo_path)
    width = models.PositiveSmallIntegerField(_("width"))
    height = models.PositiveSmallIntegerField(_("height"))
    alt_fr = models.CharField(_("alternative text in French"), max_length=200)
    alt_en = models.CharField(_("alternative text in English"), max_length=200)
    credit = models.CharField(_("author or source"), max_length=120)
    source_url = models.URLField(_("source page"), blank=True)
    license = models.CharField(_("licence"), max_length=16, choices=License.choices)
    recognizable = models.BooleanField(_("a pupil can be recognised"), default=False)
    consent = models.FileField(_("written consent"), upload_to=site_consent_path, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("site photo")
        verbose_name_plural = _("site photos")
        constraints = [
            models.CheckConstraint(
                condition=~(models.Q(recognizable=True) | models.Q(license="consent"))
                | ~models.Q(consent=""),
                name="site_photo_consent_filed",
            )
        ]

    def __str__(self) -> str:
        return self.alt_fr

    def needs_consent(self) -> bool:
        return self.recognizable or self.license == self.License.CONSENT


class SitePage(models.Model):
    """Réglages d'une page publique (SITE.1b, SITE.3) : titre et description pour les moteurs de
    recherche (vides : le texte du logiciel) et, pour l'accueil, les écoles et les parents, la
    photo du haut (vide : celle du site par défaut). Une ligne par page, créée au premier
    réglage."""

    class Key(models.TextChoices):
        HOME = "home", _("Home")
        SCHOOLS = "schools", _("Schools")
        PARENTS = "parents", _("Parents")
        NEWS = "news", _("News")
        CONTACT = "contact", _("Demo")

    PHOTO_PAGES = frozenset({Key.HOME, Key.SCHOOLS, Key.PARENTS})
    PHOTO_MIN_WIDTH = 1200  # en haut d'une page, sur un grand écran

    key = models.CharField(_("page"), max_length=12, primary_key=True, choices=Key.choices)
    title_fr = models.CharField(_("search title in French"), max_length=60, blank=True)
    title_en = models.CharField(_("search title in English"), max_length=60, blank=True)
    description_fr = models.CharField(_("search description in French"), max_length=160, blank=True)
    description_en = models.CharField(
        _("search description in English"), max_length=160, blank=True
    )
    photo = models.ForeignKey(
        SitePhoto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pages",
        verbose_name=_("photo"),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("site page")
        verbose_name_plural = _("site pages")

    def __str__(self) -> str:
        return self.key


class Testimonial(BaseModel):
    """Témoignage du site public (SITE.1b) : les mots d'une personne d'une école. Publié seulement
    avec l'accord écrit de la personne et de l'école déposé (`consent`, privé), sauf un texte
    d'exemple (`is_example`, étiqueté dans la console) tenu en place avant les premiers vrais.
    Anglais vide : la citation française."""

    MAX = 6

    name = models.CharField(_("name"), max_length=80)
    role = models.CharField(_("position"), max_length=80)
    school_name = models.CharField(_("school"), max_length=120)
    town = models.CharField(_("town"), max_length=60)
    quote_fr = models.TextField(_("quote in French"), max_length=400)
    quote_en = models.TextField(_("quote in English"), max_length=400, blank=True)
    consent = models.FileField(_("written consent"), upload_to=site_consent_path, blank=True)
    logo = models.ForeignKey(
        SitePhoto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="testimonials",
        verbose_name=_("school logo"),
    )
    is_example = models.BooleanField(_("example"), default=False)
    position = models.PositiveSmallIntegerField(_("position"), default=0)
    published = models.BooleanField(_("published"), default=False)

    class Meta:
        ordering = ["position", "created_at"]
        verbose_name = _("testimonial")
        verbose_name_plural = _("testimonials")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(published=False)
                | models.Q(is_example=True)
                | ~models.Q(consent=""),
                name="testimonial_published_with_consent",
            )
        ]

    def __str__(self) -> str:
        return self.name


class ReferenceSchool(BaseModel):
    """École de référence du site public (SITE.1b) : nom, ville, nombre d'élèves (tapé par la
    communication, il doit être vrai), logo, lien. Publiée seulement avec la date de l'accord de
    l'école (`consent_on`), sauf une école d'exemple (`is_example`, étiquetée dans la console) qui
    ne sert qu'aux chiffres du site tant que les vraies écoles sont peu nombreuses."""

    MAX = 8

    name = models.CharField(_("school"), max_length=120)
    town = models.CharField(_("town"), max_length=60)
    pupils = models.PositiveIntegerField(_("pupils"))
    link = models.URLField(_("link"), blank=True)
    logo = models.ForeignKey(
        SitePhoto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reference_schools",
        verbose_name=_("logo"),
    )
    consent_on = models.DateField(_("school's consent given on"), null=True, blank=True)
    is_example = models.BooleanField(_("example"), default=False)
    position = models.PositiveSmallIntegerField(_("position"), default=0)
    published = models.BooleanField(_("published"), default=False)

    class Meta:
        ordering = ["position", "created_at"]
        verbose_name = _("reference school")
        verbose_name_plural = _("reference schools")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(published=False)
                | models.Q(is_example=True)
                | models.Q(consent_on__isnull=False),
                name="reference_school_published_with_consent",
            )
        ]

    def __str__(self) -> str:
        return self.name


class SitePlan(BaseModel):
    """Formule d'abonnement montrée sur la page des prix (demande du 2026-10-30) : nom, prix par
    mois ou par an en entiers (centimes) avec sa devise, ce qu'elle comprend (une ligne par
    point). Sans prix : « sur devis ». Le contrat et la facture sont ceux du lot 3."""

    MAX = 4

    class Period(models.TextChoices):
        MONTH = "month", _("per month")
        YEAR = "year", _("per year")

    name_fr = models.CharField(_("name in French"), max_length=40)
    name_en = models.CharField(_("name in English"), max_length=40, blank=True)
    tagline_fr = models.CharField(_("tagline in French"), max_length=120)
    tagline_en = models.CharField(_("tagline in English"), max_length=120, blank=True)
    price = models.PositiveIntegerField(_("price"), null=True, blank=True)
    currency = models.CharField(
        _("currency"), max_length=3, choices=Currency.choices, default="USD"
    )
    period = models.CharField(_("period"), max_length=5, choices=Period.choices, default="month")
    features_fr = models.TextField(_("included, one per line, in French"), max_length=800)
    features_en = models.TextField(
        _("included, one per line, in English"), max_length=800, blank=True
    )
    highlighted = models.BooleanField(_("highlighted"), default=False)
    is_example = models.BooleanField(_("example"), default=False)
    position = models.PositiveSmallIntegerField(_("position"), default=0)
    published = models.BooleanField(_("published"), default=False)

    class Meta:
        ordering = ["position", "created_at"]
        verbose_name = _("plan")
        verbose_name_plural = _("plans")

    def __str__(self) -> str:
        return self.name_fr


class Partner(BaseModel):
    """Partenaire montré dans la bande qui défile (demande du 2026-10-30) : nom, logo de la
    photothèque (sans logo : le nom en lettres), lien `https://` facultatif."""

    MAX = 8

    name = models.CharField(_("name"), max_length=80)
    link = models.URLField(_("link"), blank=True)
    logo = models.ForeignKey(
        SitePhoto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="partners",
        verbose_name=_("logo"),
    )
    position = models.PositiveSmallIntegerField(_("position"), default=0)
    published = models.BooleanField(_("published"), default=False)

    class Meta:
        ordering = ["position", "created_at"]
        verbose_name = _("partner")
        verbose_name_plural = _("partners")

    def __str__(self) -> str:
        return self.name


class Article(BaseModel):
    """Actualité du site public (SITE.2), dans une langue (la traduction est un autre article).
    Publiée à `published_at` : une date future la tient cachée jusque-là (« programmée » n'est pas
    un état enregistré, aucune tâche de fond). L'adresse (`slug`) est tirée du titre à la première
    publication, unique par langue, puis figée. Texte en petit Markdown (`markdown.py`)."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")

    class Language(models.TextChoices):
        FR = "fr", _("French")
        EN = "en", _("English")

    language = models.CharField(_("language"), max_length=2, choices=Language.choices)
    title = models.CharField(_("title"), max_length=120)
    slug = models.SlugField(_("address"), max_length=80, blank=True, editable=False)
    summary = models.CharField(_("summary"), max_length=200)
    body = models.TextField(_("text"), max_length=20000)
    photo = models.ForeignKey(
        SitePhoto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name=_("image"),
    )
    author_name = models.CharField(_("author shown"), max_length=80, blank=True)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    published_at = models.DateTimeField(_("publication date"), null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
        verbose_name=_("changed by"),
    )

    class Meta:
        ordering = [models.F("published_at").desc(nulls_first=True), "-created_at"]
        verbose_name = _("article")
        verbose_name_plural = _("articles")
        constraints = [
            models.UniqueConstraint(
                fields=["language", "slug"],
                condition=~models.Q(slug=""),
                name="article_slug_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(status="draft")
                | (models.Q(published_at__isnull=False) & ~models.Q(slug="")),
                name="article_published_has_date_and_address",
            ),
        ]
        indexes = [
            models.Index(fields=["language", "status", "published_at"], name="article_public")
        ]

    def __str__(self) -> str:
        return self.title


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

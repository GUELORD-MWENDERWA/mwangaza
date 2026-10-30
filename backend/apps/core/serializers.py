from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.serializers import PhoneField
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.audit.serializers import AuditActorSerializer
from apps.core import site_content
from apps.core.images import CleanedFileField, clean_site_photo, consent_extension
from apps.core.models import (
    Article,
    DemoRequest,
    Partner,
    PlatformSettings,
    ReferenceSchool,
    SiteBanner,
    SiteEntry,
    SitePage,
    SitePhoto,
    SitePlan,
    Testimonial,
)
from apps.core.platform import SOCIAL_HOSTS, check_colors, clean_icon, clean_logo

SOCIAL_FIELDS = tuple(SOCIAL_HOSTS)

PUBLIC_FIELDS = [
    "name",
    "short_name",
    "site_name",
    "logo",
    "icon",
    "primary_color",
    "accent_color",
    "support_phone",
    "support_email",
    "legal_notice",
    "address",
    "city",
    "region",
    "whatsapp_url",
    "facebook_url",
    "instagram_url",
    "linkedin_url",
    "youtube_url",
    "tiktok_url",
]


class PlatformSerializer(serializers.ModelSerializer):
    """Identité de la plateforme, publique : écrans de connexion, menus, documents."""

    logo = serializers.CharField(
        source="logo_url", allow_null=True, help_text="Adresse du logo ; vide : la lampe."
    )
    icon = serializers.CharField(
        source="icon_url",
        allow_null=True,
        help_text="Adresse de l'icône des applications ; vide : celle de l'application.",
    )

    class Meta:
        model = PlatformSettings
        fields = PUBLIC_FIELDS


class PlatformChangeSerializer(serializers.ModelSerializer):
    """Une modification de l'identité, dans le journal de la plateforme."""

    action = serializers.ChoiceField(choices=PlatformAction.choices, read_only=True)
    actor = AuditActorSerializer(read_only=True, allow_null=True)

    class Meta:
        model = PlatformAuditLog
        fields = ["id", "created_at", "action", "actor", "before", "after"]


class ConsolePlatformSerializer(PlatformSerializer):
    """Identité de la plateforme dans la console (5.2.2) : modifiable par le super-admin ;
    couleurs illisibles refusées (contraste 4,5 : 1). Logo et icône s'envoient à part."""

    HISTORY = 5

    logo = serializers.CharField(source="logo_url", read_only=True, allow_null=True)
    icon = serializers.CharField(source="icon_url", read_only=True, allow_null=True)
    support_phone = PhoneField(
        required=False, allow_blank=True, help_text="0970000000 ou +243970000000 ; vide : aucun."
    )
    updated_at = serializers.DateTimeField(read_only=True)
    history = serializers.SerializerMethodField(
        help_text="Les dernières modifications, de la plus récente à la plus ancienne."
    )

    class Meta(PlatformSerializer.Meta):
        fields = [*PUBLIC_FIELDS, "updated_at", "history"]

    def validate(self, attrs: dict) -> dict:
        current = self.instance or PlatformSettings()
        try:
            check_colors(
                attrs.get("primary_color", current.primary_color),
                attrs.get("accent_color", current.accent_color),
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(get_error_detail(error)) from None
        return attrs

    @extend_schema_field(PlatformChangeSerializer(many=True))
    def get_history(self, platform: PlatformSettings) -> list[dict]:
        changes = PlatformAuditLog.objects.filter(
            entity_type=platform._meta.label_lower, entity_id=str(platform.pk)
        ).select_related("actor")[: self.HISTORY]
        return PlatformChangeSerializer(changes, many=True).data


class PlatformLogoUploadSerializer(serializers.Serializer):
    logo = CleanedFileField(
        clean=clean_logo,
        help_text="PNG ou JPEG (1 Mo et 2 048 pixels de côté au plus), ou SVG sans script.",
    )


class PlatformIconUploadSerializer(serializers.Serializer):
    icon = CleanedFileField(
        clean=clean_icon, help_text="PNG carré de 512 à 2 048 pixels de côté, 1 Mo au plus."
    )


class ConsoleDemoRequestSerializer(serializers.ModelSerializer):
    """Demande de démonstration du site (WEB.1d), dans la console : seuls le suivi et la note
    interne se modifient. Fonction, taille et langue : codes, traduits par la console."""

    class Meta:
        model = DemoRequest
        fields = [
            "id",
            "created_at",
            "source",
            "name",
            "role",
            "school_name",
            "town",
            "phone",
            "size",
            "email",
            "message",
            "language",
            "status",
            "notes",
            "updated_at",
        ]
        read_only_fields = [f for f in fields if f not in ("status", "notes")]


class ConsoleSiteEntrySerializer(serializers.ModelSerializer):
    """Question de l'accueil ou des parents, ou fonction « Prochainement » (SITE.1a). Français
    obligatoire, anglais facultatif (vide : le français) ; la sorte ne change plus après la
    création ; le rang se change par `move`."""

    class Meta:
        model = SiteEntry
        fields = [
            "id",
            "kind",
            "title_fr",
            "title_en",
            "text_fr",
            "text_en",
            "position",
            "published",
            "updated_at",
        ]
        read_only_fields = ["id", "position", "updated_at"]

    def validate_kind(self, kind: str) -> str:
        if self.instance is not None and kind != self.instance.kind:
            raise serializers.ValidationError(_("The kind of an entry cannot change."))
        if self.instance is None and SiteEntry.objects.filter(kind=kind).count() >= (
            SiteEntry.MAX_PER_KIND
        ):
            raise serializers.ValidationError(
                _("This list is full (%(max)s at most): delete an entry first.")
                % {"max": SiteEntry.MAX_PER_KIND}
            )
        return kind


class SiteEntryMoveSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=["up", "down"])


BANNER_STATES = ["shown", "scheduled", "ended", "hidden"]
HTTPS = URLValidator(schemes=["https"])


class ConsoleSiteBannerSerializer(serializers.ModelSerializer):
    """Bandeau d'annonce du site (SITE.1a). `state` : affiché, programmé, terminé ou caché."""

    state = serializers.SerializerMethodField()

    class Meta:
        model = SiteBanner
        fields = [
            "text_fr",
            "text_en",
            "link",
            "starts_on",
            "ends_on",
            "active",
            "state",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    @extend_schema_field(serializers.ChoiceField(choices=BANNER_STATES))
    def get_state(self, banner: SiteBanner) -> str:
        return banner.state(timezone.localdate())

    def validate_link(self, link: str) -> str:
        """Une page du site (`/demonstration/`) ou une adresse `https://` ; rien d'autre (ni
        `javascript:`, ni `//autre-site`)."""
        if not link:
            return link
        if link.startswith("/") and not link.startswith("//") and " " not in link:
            return link
        try:
            HTTPS(link)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                _("Give a page of the site (/demonstration/) or an address starting with https://.")
            ) from error
        return link

    def validate(self, attrs: dict) -> dict:
        merged = {
            field: attrs.get(field, getattr(self.instance, field, None))
            for field in ("text_fr", "starts_on", "ends_on", "active")
        }
        if merged["active"] and not merged["text_fr"]:
            raise serializers.ValidationError({"text_fr": _("Write the text to show.")})
        if merged["starts_on"] and merged["ends_on"] and merged["ends_on"] < merged["starts_on"]:
            raise serializers.ValidationError({"ends_on": _("The end comes before the start.")})
        return attrs


class ConsentField(serializers.FileField):
    """Accord écrit envoyé (lettre signée) : PDF, JPEG ou PNG de 5 Mo au plus, reconnu à ses
    premiers octets, renommé `accord.<extension>` (le nom donné par l'ordinateur ne suit pas).
    Jamais rendu : la console le télécharge par l'action `consent`."""

    def __init__(self, **kwargs):
        super().__init__(write_only=True, required=False, **kwargs)

    def to_internal_value(self, data):
        file = super().to_internal_value(data)
        try:
            file.name = f"accord.{consent_extension(file)}"
        except DjangoValidationError as exc:
            raise serializers.ValidationError(get_error_detail(exc)) from None
        return file


def _merged(serializer, attrs: dict, field: str):
    return attrs[field] if field in attrs else getattr(serializer.instance, field, None)


def _check_full(model, serializer) -> None:
    if serializer.instance is None and model.objects.count() >= model.MAX:
        raise serializers.ValidationError(
            _("This list is full (%(max)s at most): delete an entry first.") % {"max": model.MAX}
        )


def _only_leave_example(serializer, value: bool) -> bool:
    """« Exemple » ne se pose pas depuis la console : un texte d'exemple se remplace (la case
    se décoche), il ne sert pas à publier sans accord."""
    if value and not getattr(serializer.instance, "is_example", False):
        raise serializers.ValidationError(
            _("Only the examples that came with the site are marked.")
        )
    return value


class ConsoleTestimonialSerializer(serializers.ModelSerializer):
    """Témoignage (SITE.1b) : les mots d'une personne, mot pour mot. « Publié » refusé sans
    l'accord écrit déposé (`consent`, privé : seulement `has_consent` est rendu). Six au plus ;
    le rang se change par `move`."""

    consent = ConsentField()
    has_consent = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = [
            "id",
            "name",
            "role",
            "school_name",
            "town",
            "quote_fr",
            "quote_en",
            "consent",
            "has_consent",
            "logo",
            "is_example",
            "position",
            "published",
            "updated_at",
        ]
        read_only_fields = ["id", "position", "updated_at"]

    def validate_is_example(self, value: bool) -> bool:
        return _only_leave_example(self, value)

    def get_has_consent(self, testimonial: Testimonial) -> bool:
        return bool(testimonial.consent)

    def validate(self, attrs: dict) -> dict:
        _check_full(Testimonial, self)
        if (
            _merged(self, attrs, "published")
            and not _merged(self, attrs, "consent")
            and not _merged(self, attrs, "is_example")
        ):
            raise serializers.ValidationError(
                {"published": _("File the written consent before publishing.")}
            )
        return attrs


HTTPS_ONLY = URLValidator(schemes=["https"])


class ConsoleReferenceSchoolSerializer(serializers.ModelSerializer):
    """École de référence (SITE.1b). « Publiée » refusée sans la date de l'accord de l'école ;
    lien `https://` seulement. Huit au plus ; le rang se change par `move`."""

    link = serializers.URLField(required=False, allow_blank=True, validators=[HTTPS_ONLY])

    class Meta:
        model = ReferenceSchool
        fields = [
            "id",
            "name",
            "town",
            "pupils",
            "link",
            "logo",
            "consent_on",
            "is_example",
            "position",
            "published",
            "updated_at",
        ]
        read_only_fields = ["id", "position", "updated_at"]

    def validate_is_example(self, value: bool) -> bool:
        return _only_leave_example(self, value)

    def validate_consent_on(self, consent_on):
        if consent_on and consent_on > timezone.localdate():
            raise serializers.ValidationError(_("This date has not come yet."))
        return consent_on

    def validate(self, attrs: dict) -> dict:
        _check_full(ReferenceSchool, self)
        if (
            _merged(self, attrs, "published")
            and not _merged(self, attrs, "consent_on")
            and not _merged(self, attrs, "is_example")
        ):
            raise serializers.ValidationError(
                {"consent_on": _("Give the date the school agreed before publishing.")}
            )
        return attrs


class ConsolePlanSerializer(serializers.ModelSerializer):
    """Formule d'abonnement (page des prix). Prix en entiers (centimes) avec sa devise, vide :
    « sur devis » ; au plus huit points par langue. Quatre formules au plus ; le rang se change
    par `move`."""

    class Meta:
        model = SitePlan
        fields = [
            "id",
            "name_fr",
            "name_en",
            "tagline_fr",
            "tagline_en",
            "price",
            "currency",
            "period",
            "features_fr",
            "features_en",
            "highlighted",
            "is_example",
            "position",
            "published",
            "updated_at",
        ]
        read_only_fields = ["id", "position", "updated_at"]

    def validate_is_example(self, value: bool) -> bool:
        return _only_leave_example(self, value)

    def validate(self, attrs: dict) -> dict:
        _check_full(SitePlan, self)
        for field in ("features_fr", "features_en"):
            lines = [line for line in attrs.get(field, "").splitlines() if line.strip()]
            if len(lines) > 8:
                raise serializers.ValidationError({field: _("Eight points at most.")})
        return attrs


class ConsolePartnerSerializer(serializers.ModelSerializer):
    """Partenaire de la bande du site : nom, logo de la photothèque (sans logo : le nom en
    lettres), lien `https://` seulement. Huit au plus ; le rang se change par `move`."""

    link = serializers.URLField(required=False, allow_blank=True, validators=[HTTPS_ONLY])

    class Meta:
        model = Partner
        fields = ["id", "name", "link", "logo", "position", "published", "updated_at"]
        read_only_fields = ["id", "position", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        _check_full(Partner, self)
        return attrs


class ConsoleSitePageSerializer(serializers.ModelSerializer):
    """Réglages d'une page publique (SITE.1b, SITE.3) : titre (60) et description (160) de
    recherche par langue, vides = le texte du logiciel ; photo du haut (accueil, écoles, parents
    seulement ; 1 200 px de large au moins), vide = celle du site."""

    has_photo_slot = serializers.SerializerMethodField()

    class Meta:
        model = SitePage
        fields = [
            "key",
            "title_fr",
            "title_en",
            "description_fr",
            "description_en",
            "photo",
            "has_photo_slot",
            "updated_at",
        ]
        read_only_fields = ["key", "updated_at"]

    def get_has_photo_slot(self, page: SitePage) -> bool:
        return page.key in SitePage.PHOTO_PAGES

    def validate_photo(self, photo: SitePhoto | None) -> SitePhoto | None:
        if photo is None:
            return photo
        if self.instance.key not in SitePage.PHOTO_PAGES:
            raise serializers.ValidationError(_("This page has no photo."))
        if photo.width < SitePage.PHOTO_MIN_WIDTH:
            raise serializers.ValidationError(
                _("This photo is too small for the top of a page (%(width)s pixels at least).")
                % {"width": SitePage.PHOTO_MIN_WIDTH}
            )
        return photo


ARTICLE_STATES = ["draft", "scheduled", "published"]


def article_state(article: Article, now=None) -> str:
    if article.status == Article.Status.DRAFT:
        return "draft"
    return "scheduled" if article.published_at > (now or timezone.now()) else "published"


class ConsoleArticleSerializer(serializers.ModelSerializer):
    """Actualité (SITE.2). `state` : brouillon, programmé (publié, date future : il paraît seul
    à sa date) ou publié. Publier sans date : maintenant. L'adresse (`slug`, `url`) naît à la
    première publication, puis ne change plus, ni la langue."""

    state = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    updated_by = AuditActorSerializer(read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "language",
            "title",
            "slug",
            "url",
            "summary",
            "body",
            "photo",
            "author_name",
            "status",
            "published_at",
            "state",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "updated_at"]

    @extend_schema_field(serializers.ChoiceField(choices=ARTICLE_STATES))
    def get_state(self, article: Article) -> str:
        return article_state(article)

    def get_url(self, article: Article) -> str | None:
        return site_content.article_path(article.language, article.slug) if article.slug else None

    def validate_language(self, language: str) -> str:
        if self.instance is not None and self.instance.slug and language != self.instance.language:
            raise serializers.ValidationError(_("The language of a published article is fixed."))
        return language


class ArticleCountsSerializer(serializers.Serializer):
    all = serializers.IntegerField()
    draft = serializers.IntegerField()
    scheduled = serializers.IntegerField()
    published = serializers.IntegerField()


class ArticlePreviewSerializer(serializers.Serializer):
    """Texte à mettre en forme comme sur le site (aucun HTML accepté : tout est échappé)."""

    body = serializers.CharField(max_length=20000, allow_blank=True, trim_whitespace=False)
    html = serializers.CharField(read_only=True)
    minutes = serializers.IntegerField(read_only=True)


class ConsoleSitePhotoSerializer(serializers.ModelSerializer):
    """Photo de la photothèque (SITE.3). À l'envoi (`image`) : JPEG, PNG ou WebP de 10 Mo au plus
    et 600 px de large au moins, ré-encodée en WebP 1 600 et 600 px sans métadonnées. Licence de
    la liste (jamais NC ni ND) ; un élève reconnaissable ou une licence « accord écrit » exigent
    l'accord déposé. `uses` : pages, articles, témoignages et écoles qui la montrent (la
    suppression est refusée tant qu'il y en a)."""

    image = serializers.FileField(write_only=True)
    consent = ConsentField()
    has_consent = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    small_url = serializers.SerializerMethodField()
    uses = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = SitePhoto
        fields = [
            "id",
            "image",
            "url",
            "small_url",
            "width",
            "height",
            "alt_fr",
            "alt_en",
            "credit",
            "source_url",
            "license",
            "recognizable",
            "consent",
            "has_consent",
            "uses",
            "created_at",
        ]
        read_only_fields = ["id", "width", "height", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None and not isinstance(self.instance, list | tuple):
            # Une photo envoyée ne se remplace pas : on en envoie une autre.
            self.fields.pop("image")

    def get_has_consent(self, photo: SitePhoto) -> bool:
        return bool(photo.consent)

    def get_url(self, photo: SitePhoto) -> str:
        return site_content.photo_url(photo.pk)

    def get_small_url(self, photo: SitePhoto) -> str:
        return site_content.photo_url(photo.pk, 600)

    def validate_image(self, image):
        try:
            return clean_site_photo(image)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(get_error_detail(exc)) from None

    def validate_source_url(self, url: str) -> str:
        if url:
            HTTPS_ONLY(url)
        return url

    def validate(self, attrs: dict) -> dict:
        needs = _merged(self, attrs, "recognizable") or (
            _merged(self, attrs, "license") == SitePhoto.License.CONSENT
        )
        if needs and not _merged(self, attrs, "consent"):
            raise serializers.ValidationError(
                {"consent": _("File the written consent of the parents and the school.")}
            )
        return attrs


class ConsoleSocialLinksSerializer(serializers.ModelSerializer):
    """Réseaux sociaux de la plateforme (SITE.5) : les champs de l'identité (WEB.1d), tenus par
    la communication. Chaque lien mène au réseau attendu, en https ; vide : absent du site."""

    class Meta:
        model = PlatformSettings
        fields = list(SOCIAL_FIELDS)

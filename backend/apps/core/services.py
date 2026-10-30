"""Identité de la plateforme (5.1), modifiée par le super-admin dans la console (5.2.2). Chaque
changement va dans le journal de la plateforme (`PlatformAuditLog`)."""

from functools import partial

from django.db import models, transaction
from django.db.models import Max
from django.db.models.fields.files import FieldFile
from django.utils import timezone
from django.utils.text import slugify

from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.core import site_content
from apps.core.models import (
    Article,
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

TEXT_FIELDS = (
    "name",
    "short_name",
    "site_name",
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
)
FILE_ACTIONS = {
    "logo": PlatformAction.PLATFORM_LOGO_CHANGED,
    "icon": PlatformAction.PLATFORM_ICON_CHANGED,
}


def _identity(platform: PlatformSettings) -> dict:
    return {field: str(getattr(platform, field)) for field in TEXT_FIELDS}


def update_platform(*, actor, **fields) -> PlatformSettings:
    """Champs déjà vérifiés (serializers de la console) ; `logo=None` ou `icon=None` retire le
    fichier (la lampe revient). L'ancien fichier est effacé une fois la transaction faite."""
    PlatformSettings.load()
    with transaction.atomic():
        platform = PlatformSettings.objects.select_for_update().get(pk=1)
        before = _identity(platform)
        files = {field: getattr(platform, field).name for field in FILE_ACTIONS}
        for field, value in fields.items():
            setattr(platform, field, "" if field in FILE_ACTIONS and value is None else value)
        platform.save()
        old, new = audit.changes(before, _identity(platform))
        if new:
            audit.record_platform(
                PlatformAction.PLATFORM_UPDATED, platform, actor=actor, before=old, after=new
            )
        for field, action in FILE_ACTIONS.items():
            file = getattr(platform, field)
            if files[field] == file.name:
                continue
            audit.record_platform(action, platform, actor=actor, after={field: bool(file)})
            if files[field]:
                transaction.on_commit(partial(file.storage.delete, files[field]))
    return platform


# Contenus du site public (SITE.1a à SITE.3) : chaque changement au journal de la plateforme, puis
# le cache du site vidé une fois la transaction faite (la page suivante relit la base).
ENTRY_FIELDS = ("kind", "title_fr", "title_en", "text_fr", "text_en", "published")
BANNER_FIELDS = ("text_fr", "text_en", "link", "starts_on", "ends_on", "active")
TESTIMONIAL_FIELDS = (
    "name",
    "role",
    "school_name",
    "town",
    "quote_fr",
    "quote_en",
    "consent",
    "logo",
    "is_example",
    "published",
)
REFERENCE_FIELDS = (
    "name",
    "town",
    "pupils",
    "link",
    "logo",
    "consent_on",
    "is_example",
    "published",
)
PLAN_FIELDS = (
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
    "published",
)
PARTNER_FIELDS = ("name", "link", "logo", "published")
PAGE_FIELDS = ("title_fr", "title_en", "description_fr", "description_en", "photo")
ARTICLE_FIELDS = (
    "language",
    "title",
    "slug",
    "summary",
    "body",
    "photo",
    "author_name",
    "status",
    "published_at",
)
PHOTO_FIELDS = ("alt_fr", "alt_en", "credit", "source_url", "license", "recognizable", "consent")
ORDERED = {
    SiteEntry: (
        ENTRY_FIELDS,
        PlatformAction.SITE_ENTRY_CREATED,
        PlatformAction.SITE_ENTRY_UPDATED,
        PlatformAction.SITE_ENTRY_MOVED,
        PlatformAction.SITE_ENTRY_DELETED,
    ),
    Testimonial: (
        TESTIMONIAL_FIELDS,
        PlatformAction.SITE_TESTIMONIAL_CREATED,
        PlatformAction.SITE_TESTIMONIAL_UPDATED,
        PlatformAction.SITE_TESTIMONIAL_MOVED,
        PlatformAction.SITE_TESTIMONIAL_DELETED,
    ),
    ReferenceSchool: (
        REFERENCE_FIELDS,
        PlatformAction.SITE_REFERENCE_CREATED,
        PlatformAction.SITE_REFERENCE_UPDATED,
        PlatformAction.SITE_REFERENCE_MOVED,
        PlatformAction.SITE_REFERENCE_DELETED,
    ),
    SitePlan: (
        PLAN_FIELDS,
        PlatformAction.SITE_PLAN_CREATED,
        PlatformAction.SITE_PLAN_UPDATED,
        PlatformAction.SITE_PLAN_MOVED,
        PlatformAction.SITE_PLAN_DELETED,
    ),
    Partner: (
        PARTNER_FIELDS,
        PlatformAction.SITE_PARTNER_CREATED,
        PlatformAction.SITE_PARTNER_UPDATED,
        PlatformAction.SITE_PARTNER_MOVED,
        PlatformAction.SITE_PARTNER_DELETED,
    ),
}


def _value(value):
    """Ce que le journal garde d'un champ : l'identifiant d'un lien, la présence d'un fichier."""
    if isinstance(value, FieldFile):
        return bool(value)
    if isinstance(value, models.Model):
        return str(value.pk)
    return value


def _values(item, fields) -> dict:
    return {field: _value(getattr(item, field)) for field in fields}


def _site_changed() -> None:
    transaction.on_commit(site_content.clear)


def _drop_old_files(item, fields: tuple[str, ...], before: dict[str, str]) -> None:
    """Fichier remplacé (accord écrit) : l'ancien est effacé une fois la transaction faite."""
    for field in fields:
        old = before[field]
        if old and getattr(item, field).name != old:
            transaction.on_commit(partial(getattr(item, field).storage.delete, old))


def ordered_siblings(item):
    """La liste ordonnée de l'élément : les questions d'une même sorte, ou tous les témoignages,
    écoles de référence, formules, partenaires."""
    items = type(item).objects.all()
    return items.filter(kind=item.kind) if isinstance(item, SiteEntry) else items


def create_ordered(model, *, actor, **fields):
    """Question, témoignage ou école de référence, à la fin de sa liste."""
    logged, created, *_rest = ORDERED[model]
    with transaction.atomic():
        item = model(created_by=actor, **fields)
        last = ordered_siblings(item).aggregate(last=Max("position"))["last"]
        item.position = (last or 0) + 1
        item.save()
        audit.record_platform(created, item, actor=actor, after=_values(item, logged))
        _site_changed()
    return item


def update_ordered(item, *, actor, **fields):
    logged, _created, updated, *_rest = ORDERED[type(item)]
    with transaction.atomic():
        before = _values(item, logged)
        files = {field: item.consent.name for field in ("consent",) if hasattr(item, field)}
        for field, value in fields.items():
            setattr(item, field, value)
        item.save()
        old, new = audit.changes(before, _values(item, logged))
        if new:
            audit.record_platform(updated, item, actor=actor, before=old, after=new)
            _site_changed()
        _drop_old_files(item, tuple(files), files)
    return item


def move_ordered(item, *, actor, up: bool) -> None:
    """Échange l'élément avec son voisin du dessus (ou du dessous) ; la liste est renumérotée
    1, 2, 3… (20 lignes au plus). En haut (ou en bas) de la liste : rien ne change."""
    moved = ORDERED[type(item)][3]
    with transaction.atomic():
        siblings = list(
            ordered_siblings(item).select_for_update().order_by("position", "created_at")
        )
        here = next(i for i, sibling in enumerate(siblings) if sibling.pk == item.pk)
        there = here - 1 if up else here + 1
        if not 0 <= there < len(siblings):
            return
        siblings[here], siblings[there] = siblings[there], siblings[here]
        for position, sibling in enumerate(siblings, start=1):
            sibling.position = position
        type(item).objects.bulk_update(siblings, ["position"])
        audit.record_platform(
            moved, item, actor=actor, before={"position": here + 1}, after={"position": there + 1}
        )
        _site_changed()


def delete_ordered(item, *, actor) -> None:
    logged, *_rest, deleted = ORDERED[type(item)]
    with transaction.atomic():
        audit.record_platform(deleted, item, actor=actor, before=_values(item, logged))
        consent = getattr(item, "consent", None)
        item.delete()
        if consent:
            transaction.on_commit(partial(consent.storage.delete, consent.name))
        _site_changed()


def update_site_banner(*, actor, **fields) -> SiteBanner:
    SiteBanner.load()
    with transaction.atomic():
        banner = SiteBanner.objects.select_for_update().get(pk=1)
        before = _values(banner, BANNER_FIELDS)
        for field, value in fields.items():
            setattr(banner, field, value)
        banner.save()
        old, new = audit.changes(before, _values(banner, BANNER_FIELDS))
        if new:
            audit.record_platform(
                PlatformAction.SITE_BANNER_UPDATED, banner, actor=actor, before=old, after=new
            )
            _site_changed()
    return banner


class PhotoInUse(Exception):
    """Photo encore choisie par une page, un article, un témoignage ou une école."""


def update_site_page(key: str, *, actor, **fields) -> SitePage:
    """Titres de recherche et photo du haut d'une page ; la ligne naît au premier réglage."""
    with transaction.atomic():
        page = SitePage.objects.select_for_update().get_or_create(pk=key)[0]
        before = _values(page, PAGE_FIELDS)
        for field, value in fields.items():
            setattr(page, field, value)
        page.save()
        old, new = audit.changes(before, _values(page, PAGE_FIELDS))
        if new:
            audit.record_platform(
                PlatformAction.SITE_PAGE_UPDATED,
                page,
                actor=actor,
                before=old,
                after=new,
                label=page.get_key_display(),
            )
            _site_changed()
    return page


def _free_slug(language: str, title: str, exclude) -> str:
    """Adresse tirée du titre, unique dans sa langue (`-2`, `-3`… si elle est prise)."""
    base = slugify(title)[:72].strip("-") or "article"
    taken = set(
        Article.objects.filter(language=language, slug__startswith=base)
        .exclude(pk=exclude)
        .values_list("slug", flat=True)
    )
    slug, n = base, 1
    while slug in taken:
        n += 1
        slug = f"{base}-{n}"
    return slug


def _publish(article: Article) -> None:
    """À la publication : une date (maintenant si aucune) et, la première fois, l'adresse."""
    if article.status != Article.Status.PUBLISHED:
        return
    if article.published_at is None:
        article.published_at = timezone.now()
    if not article.slug:
        article.slug = _free_slug(article.language, article.title, article.pk)


def create_article(*, actor, **fields) -> Article:
    with transaction.atomic():
        article = Article(created_by=actor, updated_by=actor, **fields)
        _publish(article)
        article.save()
        audit.record_platform(
            PlatformAction.SITE_ARTICLE_CREATED,
            article,
            actor=actor,
            after=_values(article, ARTICLE_FIELDS),
            label=article.title,
        )
        _site_changed()
    return article


def update_article(article: Article, *, actor, **fields) -> Article:
    """La langue et l'adresse ne changent plus une fois l'article publié (un lien partagé ne
    casse pas)."""
    with transaction.atomic():
        before = _values(article, ARTICLE_FIELDS)
        for field, value in fields.items():
            setattr(article, field, value)
        _publish(article)
        article.updated_by = actor
        article.save()
        old, new = audit.changes(before, _values(article, ARTICLE_FIELDS))
        if new:
            published = new.get("status") == Article.Status.PUBLISHED
            action = (
                PlatformAction.SITE_ARTICLE_PUBLISHED
                if published
                else PlatformAction.SITE_ARTICLE_UPDATED
            )
            audit.record_platform(
                action, article, actor=actor, before=old, after=new, label=article.title
            )
            _site_changed()
    return article


def delete_article(article: Article, *, actor) -> None:
    with transaction.atomic():
        audit.record_platform(
            PlatformAction.SITE_ARTICLE_DELETED,
            article,
            actor=actor,
            before=_values(article, ARTICLE_FIELDS),
            label=article.title,
        )
        article.delete()
        _site_changed()


def add_site_photo(*, actor, sizes: dict, size: tuple[int, int], **fields) -> SitePhoto:
    """Photo déjà ré-encodée (`images.clean_site_photo`) : enregistrée sous `<id>-1600.webp` et
    `<id>-600.webp`. Fichiers écrits avant la ligne : si la transaction échoue, ils sont effacés."""
    photo = SitePhoto(created_by=actor, width=size[0], height=size[1], **fields)
    large, small = sizes[1600], sizes[600]
    photo.large.save(f"{photo.pk}-1600.webp", large, save=False)
    photo.small.save(f"{photo.pk}-600.webp", small, save=False)
    try:
        with transaction.atomic():
            photo.save()
            audit.record_platform(
                PlatformAction.SITE_PHOTO_ADDED,
                photo,
                actor=actor,
                after=_values(photo, PHOTO_FIELDS),
                label=photo.alt_fr,
            )
    except Exception:
        for file in (photo.large, photo.small, photo.consent):
            if file:
                file.storage.delete(file.name)
        raise
    return photo


def update_site_photo(photo: SitePhoto, *, actor, **fields) -> SitePhoto:
    with transaction.atomic():
        before = _values(photo, PHOTO_FIELDS)
        old_consent = photo.consent.name
        for field, value in fields.items():
            setattr(photo, field, value)
        photo.save()
        old, new = audit.changes(before, _values(photo, PHOTO_FIELDS))
        if new:
            audit.record_platform(
                PlatformAction.SITE_PHOTO_UPDATED,
                photo,
                actor=actor,
                before=old,
                after=new,
                label=photo.alt_fr,
            )
            _site_changed()
        _drop_old_files(photo, ("consent",), {"consent": old_consent})
    return photo


def photo_uses(photo: SitePhoto) -> int:
    return (
        photo.pages.count()
        + photo.articles.count()
        + photo.testimonials.count()
        + photo.reference_schools.count()
        + photo.partners.count()
    )


def delete_site_photo(photo: SitePhoto, *, actor) -> None:
    """Refusée (`PhotoInUse`) tant qu'une page, un article, un témoignage ou une école la
    montre ; les fichiers sont effacés une fois la transaction faite."""
    with transaction.atomic():
        photo = SitePhoto.objects.select_for_update().get(pk=photo.pk)
        if photo_uses(photo):
            raise PhotoInUse
        audit.record_platform(
            PlatformAction.SITE_PHOTO_DELETED,
            photo,
            actor=actor,
            before=_values(photo, PHOTO_FIELDS),
            label=photo.alt_fr,
        )
        files = [file for file in (photo.large, photo.small, photo.consent) if file]
        photo.delete()
        for file in files:
            transaction.on_commit(partial(file.storage.delete, file.name))
        _site_changed()

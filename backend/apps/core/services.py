"""Identité de la plateforme (5.1), modifiée par le super-admin dans la console (5.2.2). Chaque
changement va dans le journal de la plateforme (`PlatformAuditLog`)."""

from functools import partial

from django.db import transaction
from django.db.models import Max

from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.core import site_content
from apps.core.models import PlatformSettings, SiteBanner, SiteEntry

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


# Contenus du site public (SITE.1a) : chaque changement au journal de la plateforme, puis le cache
# du site vidé une fois la transaction faite (la page suivante relit la base).
ENTRY_FIELDS = ("kind", "title_fr", "title_en", "text_fr", "text_en", "published")
BANNER_FIELDS = ("text_fr", "text_en", "link", "starts_on", "ends_on", "active")


def _values(item, fields) -> dict:
    return {field: getattr(item, field) for field in fields}


def _site_changed() -> None:
    transaction.on_commit(site_content.clear)


def create_site_entry(*, actor, kind: str, **fields) -> SiteEntry:
    """Nouvelle entrée, à la fin de sa liste."""
    with transaction.atomic():
        last = SiteEntry.objects.filter(kind=kind).aggregate(last=Max("position"))["last"]
        entry = SiteEntry.objects.create(
            kind=kind, position=(last or 0) + 1, created_by=actor, **fields
        )
        audit.record_platform(
            PlatformAction.SITE_ENTRY_CREATED,
            entry,
            actor=actor,
            after=_values(entry, ENTRY_FIELDS),
        )
        _site_changed()
    return entry


def update_site_entry(entry: SiteEntry, *, actor, **fields) -> SiteEntry:
    with transaction.atomic():
        before = _values(entry, ENTRY_FIELDS)
        for field, value in fields.items():
            setattr(entry, field, value)
        entry.save()
        old, new = audit.changes(before, _values(entry, ENTRY_FIELDS))
        if new:
            audit.record_platform(
                PlatformAction.SITE_ENTRY_UPDATED, entry, actor=actor, before=old, after=new
            )
            _site_changed()
    return entry


def move_site_entry(entry: SiteEntry, *, actor, up: bool) -> None:
    """Échange l'entrée avec sa voisine du dessus (ou du dessous) ; la liste est renumérotée
    1, 2, 3… (au plus 20 lignes). En haut (ou en bas) de la liste : rien ne change."""
    with transaction.atomic():
        siblings = list(
            SiteEntry.objects.select_for_update()
            .filter(kind=entry.kind)
            .order_by("position", "created_at")
        )
        here = next(i for i, sibling in enumerate(siblings) if sibling.pk == entry.pk)
        there = here - 1 if up else here + 1
        if not 0 <= there < len(siblings):
            return
        siblings[here], siblings[there] = siblings[there], siblings[here]
        for position, sibling in enumerate(siblings, start=1):
            sibling.position = position
        SiteEntry.objects.bulk_update(siblings, ["position"])
        audit.record_platform(
            PlatformAction.SITE_ENTRY_MOVED,
            entry,
            actor=actor,
            before={"position": here + 1},
            after={"position": there + 1},
        )
        _site_changed()


def delete_site_entry(entry: SiteEntry, *, actor) -> None:
    with transaction.atomic():
        audit.record_platform(
            PlatformAction.SITE_ENTRY_DELETED,
            entry,
            actor=actor,
            before=_values(entry, ENTRY_FIELDS),
        )
        entry.delete()
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

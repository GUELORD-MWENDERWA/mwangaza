"""Identité de la plateforme (5.1), modifiée par le super-admin dans la console (5.2.2). Chaque
changement va dans le journal de la plateforme (`PlatformAuditLog`)."""

from functools import partial

from django.db import transaction

from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.core.models import PlatformSettings

TEXT_FIELDS = (
    "name",
    "short_name",
    "primary_color",
    "accent_color",
    "support_phone",
    "support_email",
    "legal_notice",
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

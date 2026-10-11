"""Écrire dans le journal d'audit (règle 5 de `CLAUDE.md`, I1).

Dans un service, **dans la transaction de l'action** : l'action annulée n'a pas d'entrée, l'action
faite a toujours la sienne.

    with transaction.atomic():
        before = {"name": role.name}
        role.name = name
        role.save()
        old, new = audit.changes(before, {"name": role.name})
        if new:
            audit.record(Action.ROLES_UPDATED, role, actor=actor, before=old, after=new)

L'entrée va dans le journal de l'école courante. Adresse IP et navigateur : ceux de la requête en
cours (`AuditMiddleware`) ; pendant une session support dans cette école (A3), `impersonated_by`
aussi.
"""

from django.db import models

from apps.audit.actions import Action, PlatformAction
from apps.audit.context import current_request_info
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.core.tenancy import get_current_school

_FROM_REQUEST = object()

# Jamais dans le journal (note de M6) : une action sur un mot de passe ou une double
# authentification est notée sans valeur.
SECRET_KEYS = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "temporary_password",
        "totp_secret",
        "secret",
        "otpauth_uri",
        "recovery_codes",
        "digest",
        "token",
    }
)


def record(
    action: str,
    entity: models.Model | None = None,
    *,
    actor,
    before: dict | None = None,
    after: dict | None = None,
    label: str | None = None,
    impersonated_by=_FROM_REQUEST,
    device_time=None,
) -> AuditLog:
    """Une entrée dans le journal de l'école courante. `label` : nom de l'objet au moment de
    l'action (par défaut `str(entity)`). `before` / `after` : seulement ce qui a changé
    (`changes`), sans aucun secret. `impersonated_by` : par défaut, le super-admin de la session
    support ouverte dans cette école (jamais dans le journal d'une autre). `device_time` : heure
    de l'appareil pour une action faite hors ligne (synchronisation)."""
    entry = _entry(
        action,
        entity,
        actor=actor,
        before=before,
        after=after,
        label=label,
        impersonated_by=impersonated_by,
        device_time=device_time,
    )
    entry.save()
    return entry


def record_many(
    action: str,
    entries: list[tuple[models.Model, dict]],
    *,
    actor,
    removed: bool = False,
    label=None,
) -> None:
    """Une entrée `(objet, après)` par objet, écrites d'un seul envoi (import de centaines
    d'élèves) ; mêmes règles que `record`. `removed` : objets effacés, `(objet, avant)`.
    `label` : fonction qui nomme chaque objet (par défaut `str(objet)`)."""
    field = "before" if removed else "after"
    AuditLog.objects.bulk_create(
        [
            _entry(
                action,
                entity,
                actor=actor,
                label=label(entity) if label else None,
                **{field: data},
            )
            for entity, data in entries
        ],
        batch_size=500,
    )


def _entry(
    action,
    entity,
    *,
    actor,
    before=None,
    after=None,
    label=None,
    impersonated_by=_FROM_REQUEST,
    device_time=None,
) -> AuditLog:
    if action not in Action.values:
        raise ValueError(f"Action inconnue du journal d'audit : {action!r} (apps/audit/actions.py)")
    _refuse_secrets(before)
    _refuse_secrets(after)
    if label is None:
        label = str(entity) if entity is not None else ""
    info = current_request_info()
    school = get_current_school()
    if impersonated_by is _FROM_REQUEST:
        in_support = school is not None and info.support_school_id == school.pk
        impersonated_by = info.impersonated_by if in_support else None
    return AuditLog(
        action=action,
        actor=actor,
        impersonated_by=impersonated_by,
        created_by=actor,
        entity_type=entity._meta.label_lower if entity is not None else "",
        entity_id=entity.pk if entity is not None else None,
        entity_label=label[:255],
        before=before,
        after=after,
        ip=info.ip,
        user_agent=info.user_agent,
        device_id=info.device_id if school and info.device_school_id == school.pk else None,
        device_time=device_time,
    )


def record_platform(
    action: str,
    entity: models.Model | None = None,
    *,
    actor,
    before: dict | None = None,
    after: dict | None = None,
    label: str | None = None,
) -> PlatformAuditLog:
    """Une entrée dans le journal de la plateforme (console du super-admin, sans école) ; mêmes
    règles que `record` : dans la transaction de l'action, seulement ce qui a changé, aucun
    secret."""
    if action not in PlatformAction.values:
        raise ValueError(f"Action inconnue du journal de la plateforme : {action!r}")
    _refuse_secrets(before)
    _refuse_secrets(after)
    if label is None:
        label = str(entity) if entity is not None else ""
    info = current_request_info()
    return PlatformAuditLog.objects.create(
        action=action,
        actor=actor,
        created_by=actor,
        entity_type=entity._meta.label_lower if entity is not None else "",
        entity_id=str(entity.pk) if entity is not None else "",
        entity_label=label[:255],
        before=before,
        after=after,
        ip=info.ip,
        user_agent=info.user_agent,
    )


def changes(before: dict, after: dict) -> tuple[dict, dict]:
    """Seulement les champs qui ont changé, avant et après ; `({}, {})` si rien n'a changé."""
    keys = [key for key in after if before.get(key) != after[key]]
    return {key: before.get(key) for key in keys}, {key: after[key] for key in keys}


def _refuse_secrets(value) -> None:
    if isinstance(value, dict):
        found = SECRET_KEYS & value.keys()
        if found:
            raise ValueError(f"Un secret ne va jamais dans le journal d'audit : {sorted(found)}")
        for item in value.values():
            _refuse_secrets(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _refuse_secrets(item)

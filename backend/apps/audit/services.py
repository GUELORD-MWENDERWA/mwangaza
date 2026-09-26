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
cours (`AuditMiddleware`).
"""

from django.db import models

from apps.audit.actions import Action
from apps.audit.context import current_request_info
from apps.audit.models import AuditLog

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
) -> AuditLog:
    """Une entrée dans le journal de l'école courante. `label` : nom de l'objet au moment de
    l'action (par défaut `str(entity)`). `before` / `after` : seulement ce qui a changé
    (`changes`), sans aucun secret."""
    if action not in Action.values:
        raise ValueError(f"Action inconnue du journal d'audit : {action!r} (apps/audit/actions.py)")
    _refuse_secrets(before)
    _refuse_secrets(after)
    if label is None:
        label = str(entity) if entity is not None else ""
    info = current_request_info()
    return AuditLog.objects.create(
        action=action,
        actor=actor,
        created_by=actor,
        entity_type=entity._meta.label_lower if entity is not None else "",
        entity_id=entity.pk if entity is not None else None,
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

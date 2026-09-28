"""Journal des changements descendus sur les appareils (`ChangeLog`, 3.3.2).

Deux entités : `enrollment` (l'élève, sa classe, ses frais dus et ses paiements de l'année) et
`config` (l'école et ce qui sert hors ligne : reçus, année, classes, frais, caisses, taux).
Chaque enregistrement ou suppression d'un modèle qui les compose est noté par un signal
(`signals.py`), dans la transaction du changement. Les écritures en masse (`bulk_create`,
`bulk_update`, `QuerySet.update`) n'envoient pas de signal : le service qui les fait appelle
`touch_enrollments` ou `touch_config`."""

from collections.abc import Iterable

from django.db import transaction
from django.db.models import Max

from apps.core.tenancy import require_current_school
from apps.schools.models import School
from apps.sync.models import ChangeLog

Entity = ChangeLog.Entity
Operation = ChangeLog.Operation


def touch_enrollments(ids: Iterable, *, school_id=None, operation: str = Operation.UPSERT) -> None:
    """Inscriptions à renvoyer aux appareils (école courante si `school_id` n'est pas donné)."""
    _touch(school_id or require_current_school().pk, Entity.ENROLLMENT, ids, operation)


def touch_config(school_id=None) -> None:
    """Configuration de l'école à renvoyer aux appareils."""
    school_id = school_id or require_current_school().pk
    _touch(school_id, Entity.CONFIG, [school_id], Operation.UPSERT)


def _touch(school_id, entity_type: str, ids: Iterable, operation: str) -> None:
    # Une ligne par entité, marquée en attente : `sequence` lui donne un numéro plus grand.
    # Triées : deux transactions verrouillent les mêmes lignes dans le même ordre.
    rows = [
        ChangeLog(
            school_id=school_id,
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            pending=True,
        )
        for entity_id in sorted(set(ids))
    ]
    if rows:
        ChangeLog.all_schools.bulk_create(
            rows,
            update_conflicts=True,
            unique_fields=["school", "entity_type", "entity_id"],
            update_fields=["pending", "operation", "updated_at"],
        )


def sequence() -> int:
    """Numérote dans l'ordre les changements validés de l'école courante en attente, puis
    renvoie son dernier numéro. Sous le verrou de l'école : deux lectures ne donnent jamais le
    même numéro, et un changement validé plus tard en reçoit un plus grand. Les lignes qu'une
    transaction en cours modifie encore (import…) sont laissées pour la prochaine lecture."""
    school = require_current_school()
    with transaction.atomic():
        list(School.objects.select_for_update().filter(pk=school.pk).values_list("pk"))
        last = ChangeLog.objects.aggregate(last=Max("seq"))["last"] or 0
        pending = list(
            ChangeLog.objects.filter(pending=True)
            .select_for_update(skip_locked=True)
            .order_by("updated_at", "id")
        )
        for row in pending:
            last += 1
            row.seq, row.pending = last, False
        ChangeLog.objects.bulk_update(pending, ["seq", "pending"], batch_size=1000)
    return last

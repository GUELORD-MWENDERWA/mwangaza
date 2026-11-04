"""Tâches de fond des écoles : suppression d'un espace d'essai ou de démonstration (4.16),
remplissage et remise à zéro d'un espace de démonstration (4.17.2)."""

from celery import shared_task

from apps.schools import deletion, demonstrations, exports, lifecycle
from apps.schools.models import SchoolExport


# Limites (secondes, PERF.5a) : une démonstration complète se crée en moins d'une minute.
@shared_task(ignore_result=True, soft_time_limit=540, time_limit=600)
def delete_space(school_id: str) -> None:
    """Remise à zéro demandée : l'espace est recréé à l'instant où sa ligne part, puis rempli
    par `fill_demonstration`."""
    deletion.run(school_id, then=demonstrations.recreation(school_id))


@shared_task(ignore_result=True, soft_time_limit=540, time_limit=600)
def fill_demonstration(school_id: str) -> None:
    demonstrations.fill(school_id)


# Un classeur de 1 200 élèves se fait en quelques secondes ; la file lourde garde la mémoire sous
# contrôle. L'e-mail de l'arrêt part une fois l'export prêt (il porte le lien).
@shared_task(ignore_result=True, soft_time_limit=540, time_limit=600)
def build_export(export_id: str, event: str = lifecycle.EXPORT, reason: str = "") -> None:
    export = SchoolExport.objects.select_related("school").filter(pk=export_id).first()
    if export is None or export.state != SchoolExport.State.PENDING:
        return
    exports.build(export)
    lifecycle.send(export.school_id, event, export.pk, reason)


@shared_task(
    ignore_result=True,
    autoretry_for=(OSError,),
    retry_backoff=60,
    max_retries=3,
    soft_time_limit=60,
    time_limit=90,
)
def email_school(school_id: str, event: str, reason: str = "") -> None:
    lifecycle.send(school_id, event, None, reason)


@shared_task(ignore_result=True, soft_time_limit=120, time_limit=150)
def purge_exports() -> None:
    exports.purge()

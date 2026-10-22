"""Tâche de fond de l'emploi du temps (EDT.3a) : le calcul automatique, dans la file `heavy`
(travailleur à un seul fil, mémoire plafonnée)."""

from celery import shared_task

from apps.timetable import runs
from apps.timetable.models import MAX_RUN_SECONDS


# `acks_late` : relancé après un arrêt du travailleur, il ne refait rien (`runs.execute` ne
# prend qu'un calcul encore « en attente »). Marge : préparation, seconde résolution, écriture.
@shared_task(
    ignore_result=True,
    acks_late=True,
    soft_time_limit=MAX_RUN_SECONDS + runs.EXPLAIN_SECONDS + 60,
    time_limit=MAX_RUN_SECONDS + runs.EXPLAIN_SECONDS + 90,
)
def run_timetable(run_id: str) -> None:
    runs.execute(run_id)

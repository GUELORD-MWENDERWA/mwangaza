"""Tâches de fond de l'IA (IA.1.1) : l'appel à l'API (file `ai`, deux à la fois) et la purge."""

from celery import shared_task

from apps.ai import services


# `acks_late` : repris après un arrêt du travailleur, il ne refait rien (`services.execute` ne
# démarre qu'un appel « en attente »). Limites : l'API répond en 100 s au plus (`client.TIMEOUT`).
@shared_task(ignore_result=True, acks_late=True, soft_time_limit=130, time_limit=150)
def run_call(call_id: str, school_id: str, payload: dict) -> None:
    services.execute(call_id, school_id, payload)


@shared_task(ignore_result=True, soft_time_limit=120, time_limit=150)
def purge() -> None:
    services.purge()

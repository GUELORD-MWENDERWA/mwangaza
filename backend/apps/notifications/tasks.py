"""Tâches de fond des notifications : envoi sur l'écran (5.5), alertes du super-admin (S.3.2) ;
passages du planificateur (5.6.2, `CELERY_BEAT_SCHEDULE`)."""

from celery import shared_task

from apps.core import health
from apps.notifications import console, push, scheduled


# Limites (secondes, PERF.5a) : douce puis dure. Un envoi de 200 notifications, un passage du
# planificateur sur toutes les écoles, une purge de nuit.
@shared_task(ignore_result=True, soft_time_limit=120, time_limit=150)
def deliver(notification_ids: list[str]) -> None:
    push.deliver(notification_ids)


@shared_task(ignore_result=True, soft_time_limit=60, time_limit=90)
def alert_console(action: str, entry_id: str, detail: str, concerned: str | None = None) -> None:
    console.deliver(action, entry_id, detail, concerned)


@shared_task(ignore_result=True, soft_time_limit=300, time_limit=360)
def tick() -> None:
    scheduled.tick()
    health.heartbeat()


@shared_task(ignore_result=True, soft_time_limit=300, time_limit=360)
def purge() -> None:
    scheduled.purge()

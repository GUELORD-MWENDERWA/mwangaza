"""Tâches de fond des notifications : envoi sur l'écran (5.5), alertes du super-admin (S.3.2) ;
passages du planificateur (5.6.2, `CELERY_BEAT_SCHEDULE`)."""

from celery import shared_task

from apps.core import health
from apps.notifications import console, push, scheduled


@shared_task(ignore_result=True)
def deliver(notification_ids: list[str]) -> None:
    push.deliver(notification_ids)


@shared_task(ignore_result=True)
def alert_console(action: str, entry_id: str, detail: str) -> None:
    console.deliver(action, entry_id, detail)


@shared_task(ignore_result=True)
def tick() -> None:
    scheduled.tick()
    health.heartbeat()


@shared_task(ignore_result=True)
def purge() -> None:
    scheduled.purge()
